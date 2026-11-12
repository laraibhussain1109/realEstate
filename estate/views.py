"""Public browsing and permission-checked layout management.

JSON payloads use explicit allowlists: internal remarks, staff notes and drafts
never cross the public API boundary.
"""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, DecimalField, F, Max, Q, Value, When
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .models import (
    Area, Article, City, Enquiry, GalleryCategory, HeroBanner, HomepageSection,
    Page, Plot, Project, ProjectImage, ProjectLayout, Service, SiteSettings,
    State, Testimonial, VerifiedStatistic, ProjectSlugHistory,
)


def _projects():
    return Project.public.select_related('area__city__state').prefetch_related('layouts')


def _areas():
    return Area.objects.filter(active=True).select_related('city__state').annotate(
        public_project_count=Count('projects', filter=Q(projects__status='published'), distinct=True)
    ).filter(public_project_count__gt=0)


def _public_images():
    return ProjectImage.objects.filter(
        published=True, project__status='published', project__area__active=True
    ).select_related('project__area__city', 'category')


def _public_testimonials():
    return Testimonial.objects.filter(published=True, consent_confirmed=True)


def _filter_projects(queryset, params):
    if params.get('area'):
        queryset = queryset.filter(area__slug=params['area'])
    if params.get('city'):
        queryset = queryset.filter(area__city__name__iexact=params['city'])
    if params.get('state'):
        queryset = queryset.filter(area__city__state__name__iexact=params['state'])
    public_plots = Plot.objects.filter(layout__active=True, layout__is_draft=False).exclude(status='hidden')
    search = params.get('q', '').strip()[:200]
    if search:
        matching_plots = public_plots.filter(number__icontains=search).values('project_id')
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(area__name__icontains=search) |
            Q(area__city__name__icontains=search) | Q(code__icontains=search) |
            Q(pk__in=matching_plots)
        )
    has_plot_filter = False
    selected_status = params.get('status') or params.get('availability')
    if selected_status in Plot.Status.values and selected_status != 'hidden':
        public_plots = public_plots.filter(status=selected_status)
        has_plot_filter = True
    # Search bounds are expressed in the requested unit (square yards by
    # default), rather than comparing unrelated raw area values.
    unit = params.get('area_unit', 'sqyd')
    factors = {'sqft': Decimal('1'), 'sqyd': Decimal('9'), 'sqm': Decimal('10.7639104167')}
    factor = factors.get(unit, factors['sqyd'])
    public_plots = public_plots.annotate(search_area_sqft=Case(
        When(area_unit='sqft', then=F('area')),
        When(area_unit='sqyd', then=F('area') * Value(factors['sqyd'])),
        When(area_unit='sqm', then=F('area') * Value(factors['sqm'])),
        output_field=DecimalField(max_digits=24, decimal_places=8),
    ))
    for key, lookup in [('min_area', 'search_area_sqft__gte'), ('max_area', 'search_area_sqft__lte')]:
        try:
            if params.get(key):
                value = Decimal(params[key])
                if value.is_finite() and 0 <= value <= Decimal('1000000000000'):
                    public_plots = public_plots.filter(**{lookup: value * factor})
                    has_plot_filter = True
        except (InvalidOperation, ValueError):
            pass
    if has_plot_filter:
        queryset = queryset.filter(pk__in=public_plots.values('project_id'))
    return queryset.distinct()


@require_GET
def home(request):
    projects = _projects()
    featured = projects.filter(featured=True)
    if not featured.exists():
        featured = projects
    return render(request, 'estate/home.html', {
        'projects': featured[:6], 'featured_projects': featured[:6],
        'featured_project': featured.first(), 'areas': _areas(),
        'project_count': projects.count(), 'area_count': _areas().count(),
        'gallery_images': _public_images().filter(featured=True)[:6],
        'testimonials': _public_testimonials(),
        'hero_banners': HeroBanner.objects.filter(published=True),
        'services': Service.objects.filter(published=True),
        'sections': HomepageSection.objects.filter(enabled=True),
        'statistics': VerifiedStatistic.objects.filter(published=True),
    })


@require_GET
def project_list(request):
    projects = _filter_projects(_projects(), request.GET)
    page_obj = Paginator(projects, 9).get_page(request.GET.get('page'))
    return render(request, 'estate/project_list.html', {
        'projects': page_obj.object_list, 'page_obj': page_obj, 'areas': _areas(),
        'selected_area': request.GET.get('area', ''), 'query': request.GET.get('q', ''),
        'project_count': projects.count(),
    })


def _project_context(project, selected_plot=None):
    layout = project.active_layout
    plots = layout.plots.exclude(status='hidden') if layout else Plot.objects.none()
    return {
        'project': project, 'layout': layout, 'plots': plots,
        'selected_plot': selected_plot, 'counts': project.availability,
        'gallery_images': _public_images().filter(project=project),
        'amenities': project.amenities.all(),
        'documents': project.documents.filter(published=True),
        'related_projects': _projects().filter(area=project.area).exclude(pk=project.pk)[:3],
    }


@require_GET
def project_detail(request, slug):
    preview = (
        request.GET.get('preview') == '1' and request.user.is_authenticated
        and request.user.is_active and request.user.is_staff
        and request.user.has_perm('estate.view_project')
    )
    project = (Project.objects if preview else _projects()).filter(slug=slug).first()
    if project is None:
        previous = get_object_or_404(ProjectSlugHistory.objects.select_related('project'), slug=slug, project__status='published', project__area__active=True)
        return redirect(previous.project.get_absolute_url(), permanent=True)
    context = _project_context(project)
    context['is_preview'] = preview
    response = render(request, 'estate/project_detail.html', context)
    if preview:
        add_never_cache_headers(response)
        response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@require_GET
def plot_detail(request, slug, plot_slug):
    project = _projects().filter(slug=slug).first()
    if project is None:
        previous = get_object_or_404(ProjectSlugHistory.objects.select_related('project'), slug=slug, project__status='published', project__area__active=True)
        return redirect(previous.project.get_absolute_url() + f'plots/{plot_slug}/', permanent=True)
    layout = project.active_layout
    if layout is None:
        raise Http404
    plot = get_object_or_404(layout.plots.exclude(status='hidden'), slug=plot_slug)
    return render(request, 'estate/project_detail.html', _project_context(project, plot))


@require_GET
def locations(request):
    return render(request, 'estate/locations.html', {'areas': _areas(), 'projects': _projects()})


@require_GET
def area_detail(request, slug):
    area = get_object_or_404(_areas(), slug=slug)
    projects = _projects().filter(area=area)
    page_obj = Paginator(projects, 9).get_page(request.GET.get('page'))
    return render(request, 'estate/project_list.html', {
        'area': area, 'projects': page_obj.object_list, 'areas': _areas(),
        'selected_area': area.slug, 'page_obj': page_obj, 'project_count': projects.count(),
    })


@require_GET
def gallery(request):
    images = _public_images()
    if request.GET.get('area'):
        images = images.filter(project__area__slug=request.GET['area'])
    if request.GET.get('project'):
        images = images.filter(project__slug=request.GET['project'])
    if request.GET.get('category'):
        images = images.filter(category__slug=request.GET['category'])
    page_obj = Paginator(images, 18).get_page(request.GET.get('page'))
    return render(request, 'estate/gallery.html', {
        'gallery_images': page_obj.object_list, 'page_obj': page_obj,
        'areas': _areas(), 'projects': _projects(),
        'categories': GalleryCategory.objects.filter(images__in=_public_images()).distinct(),
    })


@require_GET
def about(request):
    return render(request, 'estate/about.html', {'services': Service.objects.filter(published=True)})


@require_GET
def contact(request):
    return render(request, 'estate/contact.html', {'projects': _projects()})


@require_GET
def testimonials(request):
    return render(request, 'estate/testimonials.html', {'testimonials': _public_testimonials()})


@require_GET
def articles(request):
    page_obj = Paginator(Article.objects.filter(published=True), 9).get_page(request.GET.get('page'))
    return render(request, 'estate/article_list.html', {'articles': page_obj.object_list, 'page_obj': page_obj})


@require_GET
def article(request, slug):
    return render(request, 'estate/article.html', {'article': get_object_or_404(Article, published=True, slug=slug)})


@require_GET
def page(request, slug):
    return render(request, 'estate/page.html', {'page': get_object_or_404(Page, published=True, slug=slug)})


def _number(value):
    return str(value) if value is not None else None


def serialize_plot(plot, staff=False):
    """Deliberate allowlist. Never serialize a model's __dict__ or values()."""
    data = {
        'number': plot.number, 'block': plot.block, 'slug': plot.slug,
        'status': plot.status, 'polygon': plot.polygon,
        'label_position': [plot.label_x, plot.label_y] if plot.label_x is not None and plot.label_y is not None else None,
        'area': _number(plot.area), 'area_unit': plot.area_unit,
        'area_sqft': _number(plot.area_sqft),
        'length': _number(plot.length), 'width': _number(plot.width),
        'dimension_unit': plot.dimension_unit, 'facing': plot.facing,
        'corner': plot.corner, 'park_facing': plot.park_facing,
        'road_width': plot.road_width, 'price_visible': plot.show_price,
        'price': _number(plot.price) if plot.show_price or staff else None,
        'description': plot.description, 'public_remarks': plot.public_remarks,
        'url': plot.get_absolute_url(), 'updated_at': plot.updated_at.isoformat(),
    }
    if staff:
        data['id'] = plot.pk
        data['internal_remarks'] = plot.internal_remarks
    return data


def _layout_data(layout):
    if not layout:
        return None
    return {'id': layout.pk, 'image': layout.image.url if layout.image else '',
            'width': layout.width, 'height': layout.height, 'revision': layout.revision,
            'title': layout.title}


@require_GET
@never_cache
def project_api(request):
    projects = _filter_projects(_projects(), request.GET)[:100]
    return JsonResponse({'projects': [{
        'name': p.name, 'slug': p.slug, 'area': p.area.name, 'area_slug': p.area.slug,
        'city': p.area.city.name, 'url': p.get_absolute_url(), 'is_demo': p.is_demo,
        'description': p.short_description,
        'image': p.cover_image.url if p.cover_image else '',
        'counts': p.availability,
    } for p in projects], 'areas': [
        {'name': area.name, 'slug': area.slug, 'city': area.city.name,
         'project_count': area.public_project_count} for area in _areas()
    ]})


@require_GET
@never_cache
def plot_api(request, slug):
    project = get_object_or_404(_projects(), slug=slug)
    layout = project.active_layout
    plots = list(layout.plots.exclude(status='hidden')) if layout else []
    updated = max((plot.updated_at for plot in plots), default=project.updated_at)
    return JsonResponse({
        'project': {'name': project.name, 'slug': project.slug, 'is_demo': project.is_demo,
                    'whatsapp': SiteSettings.load().whatsapp},
        'layout': _layout_data(layout), 'plots': [serialize_plot(p) for p in plots],
        'counts': project.availability, 'updated_at': updated.isoformat(),
        'whatsapp': SiteSettings.load().whatsapp,
    })


def _json_body(request):
    if len(request.body) > 512 * 1024:
        raise ValueError('The request is too large.')
    try:
        data = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
        raise ValueError('Please send valid JSON.')
    if not isinstance(data, dict):
        raise ValueError('The request must be a JSON object.')
    return data


def _validation_response(exc):
    return JsonResponse({'ok': False, 'error': 'Please check the highlighted values.',
                         'errors': exc.message_dict if hasattr(exc, 'message_dict') else {'__all__': exc.messages}}, status=400)


@staff_member_required
@never_cache
def layout_editor(request, pk):
    if not request.user.has_perm('estate.change_plot'):
        raise PermissionDenied
    layout = get_object_or_404(ProjectLayout.objects.select_related('project'), pk=pk)
    return render(request, 'estate/editor.html', {
        'layout': layout, 'project': layout.project,
        'editor_config': {'api': reverse('editor_api', args=[layout.pk]),
                          'layout': _layout_data(layout),
                          'project': {'name': layout.project.name, 'slug': layout.project.slug},
                          'plots': [serialize_plot(p, staff=True) for p in layout.plots.all()]},
    })


@require_POST
@never_cache
def editor_api(request, pk):
    if not request.user.is_authenticated or not request.user.is_active or not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Staff access is required.'}, status=403)
    layout = get_object_or_404(ProjectLayout.objects.select_related('project'), pk=pk)
    try:
        data = _json_body(request)
        action = data.get('action')
        if action == 'save':
            values = data.get('plot')
            if not isinstance(values, dict):
                raise ValueError('A plot object is required.')
            editing = bool(values.get('id'))
            permission = 'estate.change_plot' if editing else 'estate.add_plot'
            if not request.user.has_perm(permission):
                raise PermissionDenied
            with transaction.atomic():
                if editing:
                    plot = get_object_or_404(Plot.objects.select_for_update(), pk=values['id'], layout=layout)
                else:
                    plot = Plot(project=layout.project, layout=layout)
                allowed_fields = (
                    'number', 'block', 'status', 'polygon', 'area', 'area_unit', 'length', 'width',
                    'dimension_unit', 'facing', 'corner', 'park_facing', 'road_width', 'price',
                    'description', 'public_remarks', 'internal_remarks',
                )
                for field in allowed_fields:
                    if field in values:
                        value = values[field]
                        if field in ('area', 'length', 'width', 'price') and value == '':
                            value = None
                        if field in ('corner', 'park_facing') and not isinstance(value, bool):
                            raise ValueError(f'{field} must be true or false.')
                        setattr(plot, field, value)
                if 'price_visible' in values:
                    if not isinstance(values['price_visible'], bool):
                        raise ValueError('Price visibility must be true or false.')
                    plot.show_price = values['price_visible']
                if 'label_position' in values:
                    position = values['label_position']
                    if position is None or position == []:
                        plot.label_x = plot.label_y = None
                    elif isinstance(position, list) and len(position) == 2:
                        plot.label_x, plot.label_y = position
                    else:
                        raise ValueError('Label position must contain two coordinates.')
                if not plot.slug:
                    from django.utils.text import slugify
                    plot.slug = slugify(f'{plot.block}-{plot.number}'.strip('-'))
                plot._actor = request.user
                plot._status_note = str(data.get('note', values.get('note', '')))[:2000]
                plot.full_clean()
                plot.save()
            return JsonResponse({'ok': True, 'plot': serialize_plot(plot, staff=True)})
        if action == 'delete':
            if not request.user.has_perm('estate.delete_plot'):
                raise PermissionDenied
            plot = get_object_or_404(Plot, pk=data.get('id'), layout=layout)
            plot.delete()
            return JsonResponse({'ok': True})
        if action == 'bulk':
            if not request.user.has_perm('estate.change_plot'):
                raise PermissionDenied
            ids = data.get('ids')
            status = data.get('status')
            if not isinstance(ids, list) or not ids or len(ids) > 500 or status not in Plot.Status.values:
                raise ValueError('Choose plots and a valid status; up to 500 plots per update.')
            if any(not isinstance(pk, int) for pk in ids):
                raise ValueError('Invalid plot identifiers.')
            with transaction.atomic():
                plots = list(Plot.objects.select_for_update().filter(pk__in=ids, layout=layout))
                if len(plots) != len(set(ids)):
                    raise Http404
                for plot in plots:
                    plot.set_status(status, request.user, str(data.get('note', ''))[:2000])
            return JsonResponse({'ok': True, 'plots': [serialize_plot(p, staff=True) for p in layout.plots.all()]})
        raise ValueError('Unknown editor action.')
    except ValidationError as exc:
        return _validation_response(exc)
    except (ValueError, TypeError, OverflowError) as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    except IntegrityError:
        return JsonResponse({'ok': False, 'error': 'A plot with this number or identifier already exists in this revision.'}, status=400)


@require_POST
@never_cache
def enquiry_api(request):
    from .forms import EnquiryForm
    try:
        data = _json_body(request) if request.content_type == 'application/json' else request.POST.copy()
        if data.get('website'):
            return JsonResponse({'ok': False, 'error': 'Unable to submit this request.'}, status=400)
        data = data.copy()
        project = None
        if data.get('project'):
            project = get_object_or_404(Project.public, slug=data['project'])
            data['project'] = project.pk
        if data.get('plot') or data.get('plot_slug'):
            if project is None or project.active_layout is None:
                raise ValueError('Please select the project for this plot.')
            visible_plots = project.active_layout.plots.exclude(status='hidden')
            if data.get('plot_slug'):
                plot = get_object_or_404(visible_plots, slug=data['plot_slug'])
            else:
                matches = list(visible_plots.filter(number=data['plot'])[:2])
                if len(matches) > 1:
                    raise ValueError('This plot number exists in more than one block. Please use its full plot identifier.')
                plot = matches[0] if matches else get_object_or_404(visible_plots, slug=data['plot'])
            data['plot'] = plot.pk
            if not data.get('kind') or data.get('kind') == 'enquiry':
                data['kind'] = Enquiry.Kind.PLOT
        if data.get('kind') == 'enquiry' or not data.get('kind'):
            data['kind'] = Enquiry.Kind.GENERAL
        if data.get('visit_date'):
            data['preferred_date'] = data['visit_date']
        form = EnquiryForm(data)
        if not form.is_valid():
            return JsonResponse({'ok': False, 'errors': form.errors.get_json_data(),
                                 'error': 'Please check the form and try again.'}, status=400)
        client = request.META.get('REMOTE_ADDR', '')
        fingerprint = hashlib.sha256((client + settings.SECRET_KEY).encode()).hexdigest()
        key = f'enquiry-rate:{fingerprint}'
        cache.add(key, 0, 600)
        count = cache.get(key, 0)
        if count >= 6:
            response = JsonResponse({'ok': False, 'error': 'Please wait a few minutes before sending another enquiry.'}, status=429)
            response['Retry-After'] = '600'
            return response
        form.save()
        cache.set(key, count + 1, 600)
        return JsonResponse({'ok': True, 'message': 'Thank you. Our team will contact you to confirm the details.'}, status=201)
    except (ValueError, TypeError) as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


@require_GET
def robots(request):
    return HttpResponse('User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /api/\nSitemap: ' + settings.SITE_URL + '/sitemap.xml' + '\n', content_type='text/plain')


@require_GET
def sitemap(request):
    paths = ['/', '/projects/', '/locations/', '/about/', '/contact/', '/gallery/', '/testimonials/']
    paths.extend(p.get_absolute_url() for p in Project.public.filter(is_demo=False))
    paths.extend(a.get_absolute_url() for a in _areas())
    paths.extend(p.get_absolute_url() for p in Page.objects.filter(published=True))
    paths.extend(p.get_absolute_url() for p in Article.objects.filter(published=True))
    urls = ''.join('<url><loc>' + escape(settings.SITE_URL + path) + '</loc></url>' for path in paths)
    return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + '</urlset>', content_type='application/xml')
