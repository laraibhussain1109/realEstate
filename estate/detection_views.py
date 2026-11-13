"""Staff-only boundary suggestions and explicit, atomic import of reviewed plots.

Image colours never imply availability. Detection never writes Plot records.
"""
import hashlib
import json
import math

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import Plot, PlotStatusHistory, ProjectLayout
from .views import _json_body, _validation_response, serialize_plot

MAX_IMPORT = 250
IMPORT_FIELDS = {
    'polygon', 'number', 'status', 'label_position', 'area', 'area_unit',
    'length', 'width', 'dimension_unit', 'facing', 'road_width', 'corner',
    'park_facing', 'price', 'price_visible', 'description', 'public_remarks',
}


def _layout_signature(layout):
    """Bind a review to the exact stored image, even before its first plot."""
    modified = ''
    try:
        modified = layout.image.storage.get_modified_time(layout.image.name).isoformat()
    except (AttributeError, NotImplementedError, OSError):
        pass
    identity = [layout.pk, layout.revision, layout.image.name, layout.width, layout.height, modified]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def _bbox(polygon):
    xs, ys = zip(*polygon)
    return min(xs), min(ys), max(xs), max(ys)


def _overlap(first, second):
    """Bounded raster overlap handles concave polygons and ignores shared edges."""
    a, b = _bbox(first), _bbox(second)
    if min(a[2], b[2]) <= max(a[0], b[0]) or min(a[3], b[3]) <= max(a[1], b[1]):
        return False
    import cv2
    import numpy as np
    left, top = min(a[0], b[0]), min(a[1], b[1])
    width, height = max(a[2], b[2])-left, max(a[3], b[3])-top
    scale = min(1.0, 384/max(width, height, 1))
    shape = (max(2, math.ceil(height*scale)+3), max(2, math.ceil(width*scale)+3))
    masks = []
    for polygon in (first, second):
        points = np.array([[(x-left)*scale+1, (y-top)*scale+1] for x,y in polygon], dtype=np.int32)
        mask = np.zeros(shape, dtype=np.uint8)
        cv2.fillPoly(mask, [points], 1)
        # Ignore rasterized shared boundary pixels, not genuine interior overlap.
        mask = cv2.erode(mask, np.ones((3, 3), dtype=np.uint8))
        masks.append(mask)
    shared = int(np.count_nonzero(masks[0] & masks[1]))
    smaller = min(int(np.count_nonzero(mask)) for mask in masks)
    return smaller > 0 and shared > 2 and shared / smaller > 0.005


def _review_result(layout, result):
    """Do not suggest drawing over inventory already annotated on this revision."""
    existing = list(layout.plots.values_list('polygon', flat=True))
    candidates, skipped, non_quadrilaterals = [], 0, 0
    for index, candidate in enumerate(result.get('candidates', [])):
        if len(candidate.get('polygon', [])) != 4:
            non_quadrilaterals += 1
            continue
        if any(_overlap(candidate['polygon'], polygon) for polygon in existing):
            skipped += 1
            continue
        geometry = sorted((round(x, 2), round(y, 2)) for x, y in candidate['polygon'])
        region_key = hashlib.sha256(json.dumps(geometry).encode()).hexdigest()[:20]
        candidates.append({**candidate, 'key': f'region-{region_key}'})
    warnings = list(result.get('warnings', []))
    if non_quadrilaterals:
        warnings.append(f'{non_quadrilaterals} region(s) without four clear corners were excluded. Automatic drawing supports four-sided plots only.')
    if skipped:
        warnings.append(f'{skipped} detected region(s) overlapping saved plots were excluded. Existing plots were preserved.')
    return {**result, 'ok': True, 'candidates': candidates, 'warnings': warnings,
            'layout_signature': _layout_signature(layout)}


def _candidate_plot(layout, values):
    if not isinstance(values, dict) or set(values)-IMPORT_FIELDS:
        raise ValueError('Each suggestion must contain only editable plot details; IDs and project references are not accepted.')
    if not isinstance(values.get('number'), str) or not values['number'].strip():
        raise ValueError('Give every included plot a number before importing.')
    if values.get('status') not in {'available', 'booked', 'sold', 'blocked'}:
        raise ValueError('Choose Available, Booked, Sold or Not for sale for every included plot. Image colours do not set availability.')
    plot = Plot(project=layout.project, layout=layout, number=values['number'].strip(),
                status=values['status'], polygon=values.get('polygon'))
    for field in IMPORT_FIELDS - {'number', 'status', 'polygon', 'label_position', 'price_visible'}:
        if field in values:
            value = values[field]
            if field in {'area','length','width','price'} and value == '':
                value = None
            if field in {'corner','park_facing'} and not isinstance(value, bool):
                raise ValueError(f'{field} must be true or false.')
            setattr(plot, field, value)
    if 'price_visible' in values:
        if not isinstance(values['price_visible'], bool):
            raise ValueError('Price visibility must be true or false.')
        plot.show_price = values['price_visible']
    position = values.get('label_position')
    if position is not None:
        if not isinstance(position, list) or len(position) != 2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) for v in position):
            raise ValueError('Label position must contain two numeric coordinates.')
        plot.label_x, plot.label_y = position
    plot.slug = slugify(plot.number)
    if not plot.slug:
        raise ValueError('Plot numbers must include a letter or number to create their public links.')
    plot.full_clean()
    if len(plot.polygon) != 4:
        raise ValueError('Automatic drawing accepts four-sided plots only. Each imported boundary must have exactly four corners.')
    for index, corner in enumerate(plot.polygon):
        previous, following = plot.polygon[index-1], plot.polygon[(index+1) % 4]
        incoming = (previous[0]-corner[0], previous[1]-corner[1])
        outgoing = (following[0]-corner[0], following[1]-corner[1])
        cross = incoming[0]*outgoing[1] - incoming[1]*outgoing[0]
        lengths = math.hypot(*incoming)*math.hypot(*outgoing)
        if abs(cross) <= max(1.0, lengths)*1e-8:
            raise ValueError('Automatic drawing requires four real corners. Three-sided boundaries with an extra point on an edge are not accepted.')
    return plot


@require_POST
@never_cache
def detection_api(request, pk):
    user = request.user
    if not user.is_authenticated or not user.is_active or not user.is_staff or not user.has_perms(['estate.add_plot','estate.change_plot']):
        return JsonResponse({'ok':False,'error':'Staff permission to add and change plots is required.'}, status=403)
    layout = get_object_or_404(ProjectLayout.objects.select_related('project'), pk=pk)
    try:
        data = _json_body(request)
        action = data.get('action')
        if action in {'detect', 'point'}:
            from .plot_detection import detect_plot_regions, detect_region_at_point
            options = data.get('options', {})
            if not isinstance(options, dict):
                raise ValueError('Detection options must be a JSON object.')
            if action == 'point':
                x, y = data.get('x'), data.get('y')
                if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (x,y)):
                    raise ValueError('Choose a point inside the plan image.')
                if not 0 <= x < layout.width or not 0 <= y < layout.height:
                    raise ValueError('Choose a point inside the plan image.')
                with layout.image.open('rb') as source:
                    result = detect_region_at_point(source, x, y, options)
            else:
                # Cache only suggestions, never availability or staff-saved inventory.
                fingerprint = _layout_signature(layout)
                key = 'plot-detection:v2:four-sided:' + hashlib.sha256((fingerprint+json.dumps(options,sort_keys=True)).encode()).hexdigest()
                result = cache.get(key)
                if result is None:
                    with layout.image.open('rb') as source:
                        result = detect_plot_regions(source, options)
                    cache.set(key, result, 300)
            return JsonResponse(_review_result(layout, result))
        if action != 'import':
            raise ValueError('Choose detect, point or import.')
        values = data.get('candidates')
        if not isinstance(values, list) or not 1 <= len(values) <= MAX_IMPORT:
            raise ValueError(f'Include between 1 and {MAX_IMPORT} reviewed plots per import.')
        with transaction.atomic():
            layout = ProjectLayout.objects.select_for_update().select_related('project').get(pk=pk)
            if data.get('layout_signature') != _layout_signature(layout):
                return JsonResponse({'ok':False,'error':'The source image changed or this review has expired. Detect boundaries again before importing.'},status=409)
            prepared = [_candidate_plot(layout, candidate) for candidate in values]
            numbers, slugs = [p.number for p in prepared], [p.slug for p in prepared]
            if len(set(numbers)) != len(numbers) or len(set(slugs)) != len(slugs):
                raise ValueError('Every included plot needs a unique number and identifier.')
            existing = list(layout.plots.all())
            for index, plot in enumerate(prepared):
                if any(_overlap(plot.polygon, other.polygon) for other in existing + prepared[:index]):
                    raise ValueError(f'Plot {plot.number} overlaps a saved or included plot. Exclude duplicates or adjust its boundary before importing.')
            for plot in prepared:
                plot._actor = user
                plot.save()
                PlotStatusHistory.objects.create(
                    plot=plot, previous_status='new', new_status=plot.status, user=user,
                    note='Created from a reviewed boundary suggestion. Availability explicitly assigned by staff.',
                )
        return JsonResponse({'ok':True, 'imported':len(prepared),
                             'plots':[serialize_plot(plot, staff=True) for plot in layout.plots.all()]},status=201)
    except ValidationError as exc:
        return _validation_response(exc)
    except (ValueError, TypeError, OverflowError) as exc:
        return JsonResponse({'ok':False,'error':str(exc)},status=400)
    except IntegrityError:
        return JsonResponse({'ok':False,'error':'A plot with this number already exists. Update the numbering and import again.'},status=400)
    except OperationalError:
        return JsonResponse({'ok':False,'error':'The layout is being updated by another request. Refresh it and retry.'},status=409)
    except (OSError, FileNotFoundError):
        return JsonResponse({'ok':False,'error':'The stored layout image could not be read. Check the image upload before retrying.'},status=400)
