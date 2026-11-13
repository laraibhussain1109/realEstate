"""Local, bounded suggestions for plot boundaries in raster site plans.

This module does not identify surveyed land, approvals, prices or availability.
It suggests only four-sided enclosed regions and rejects common road/background shapes.
Every result must be reviewed against the original plan before it is saved.
"""
from __future__ import annotations

import csv
import io
import math
import os
import re
import shutil
import subprocess
import time

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

# WSGI requests should not spawn a pool of native worker threads.
cv2.setNumThreads(1)

MAX_IMAGE_PIXELS = 40_000_000
MAX_PROCESSING_DIMENSION = 2000
MAX_CANDIDATES = 250
MAX_COMPONENTS = 12000


def _options(options):
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ValueError('Detection options must be an object.')
    result = {}
    for key, default, low, high in [
        ('max_dimension', 1800, 400, MAX_PROCESSING_DIMENSION),
        ('max_candidates', 200, 1, MAX_CANDIDATES),
        ('min_area', 0, 0, 10_000_000),
        ('max_area_ratio', .10, .001, .30),
        ('edge_threshold', 24, 8, 90),
        ('simplify', .004, .0005, .025),
    ]:
        value = options.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{key} must be a finite number between {low} and {high}.')
        result[key] = value
    result['max_dimension'] = int(result['max_dimension'])
    result['max_candidates'] = int(result['max_candidates'])
    if 'ocr' in options and not isinstance(options['ocr'], bool):
        raise ValueError('ocr must be true or false.')
    result['ocr'] = options.get('ocr', True)
    return result


def _prepare(image, options):
    try:
        if isinstance(image, Image.Image):
            original = image
        else:
            if hasattr(image, 'seek'):
                image.seek(0)
            original = Image.open(image)
        width, height = original.size
        if width < 20 or height < 20 or width * height > MAX_IMAGE_PIXELS:
            raise ValueError('Use a plan between 20 pixels and 40 megapixels.')
        # Keep the stored file's native coordinate system. Do not EXIF-rotate it:
        # existing SVG overlays use the original raster width and height.
        if original.mode in {'RGBA','LA'} or 'transparency' in original.info:
            rgba = original.convert('RGBA')
            canvas = Image.new('RGBA',original.size,'white')
            original = Image.alpha_composite(canvas,rgba).convert('RGB')
        else:
            original = original.convert('RGB')
        scale = min(1.0, options['max_dimension'] / max(width, height))
        working_size = (max(1, round(width*scale)), max(1, round(height*scale)))
        working = original.resize(working_size, Image.Resampling.LANCZOS) if scale < 1 else original
        rgb = np.asarray(working, dtype=np.uint8).copy()
        return rgb, width, height
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('The plan image could not be safely opened.') from exc
    finally:
        if hasattr(image, 'seek'):
            try:
                image.seek(0)
            except (ValueError, OSError):
                pass


def _segments(rgb, options):
    # LAB preserves boundaries between colors with similar grey intensity.
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    blurred = cv2.GaussianBlur(lab, (3, 3), 0)
    threshold = options['edge_threshold']
    edges = np.zeros(rgb.shape[:2], dtype=np.uint8)
    for channel in cv2.split(blurred):
        edges = cv2.bitwise_or(edges, cv2.Canny(channel, threshold, threshold * 2.5))
    # A one-pixel closing joins small scan/JPEG gaps without constructing a grid.
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    free = cv2.bitwise_not(edges)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(free, connectivity=4)
    return edges, labels, stats, centroids, count


def _four_corner_fit(contour):
    """Return a quadrilateral only when it follows the observed boundary.

    Raster stair steps and one/two-pixel scan artifacts may add vertices to a
    genuine straight edge. They can be removed, but a true extra corner cannot
    be replaced with the corners of its enclosing rectangle. Both enclosed area
    and the worst boundary deviation must agree with the original contour.
    """
    area=float(cv2.contourArea(contour))
    hull_area=float(cv2.contourArea(cv2.convexHull(contour)))
    if area<=0 or hull_area<=0:
        return None
    perimeter=cv2.arcLength(contour,True)
    # A one-pixel notch is a large percentage of a ten-pixel-high plot.
    # Bound missing hull area in pixel units as well as testing edge distance.
    if area/hull_area<.97 and hull_area-area>perimeter*1.25:
        return None
    _,_,w,h=cv2.boundingRect(contour)
    tolerance=max(1.5,min(2.5,math.hypot(w,h)*.007))
    fits=[]
    # Explore small simplifications, then check every observed boundary point.
    # The fit checks, rather than a permissive epsilon, decide acceptance.
    for fraction in [.001,.002,.003,.004,.006,.008,.012,.018,.025]:
        approximation=cv2.approxPolyDP(contour,max(.5,perimeter*fraction),True)
        if len(approximation)==4:
            fits.append(approximation.astype(np.float32))
    # A minimum-area rectangle is only a fit proposal. It receives the same
    # strict area and boundary checks as a trapezoid/parallelogram proposal.
    fits.append(cv2.boxPoints(cv2.minAreaRect(contour)).reshape((-1,1,2)))
    best=None
    for quad in fits:
        quad=quad.reshape((-1,1,2)).astype(np.float32)
        if not cv2.isContourConvex(quad):
            continue
        quad_area=float(cv2.contourArea(quad))
        allowed_area_error=max(.045,min(.30,perimeter/area))
        if abs(quad_area-area)/area>allowed_area_error:
            continue
        # Reject collapsed/sliver corners, including a triangle with a redundant
        # fourth point inserted along one of its edges.
        points=quad[:,0,:]
        if any(np.linalg.norm(points[i]-points[(i+1)%4])<3 for i in range(4)):
            continue
        worst=0.
        for point in contour[:,0,:]:
            worst=max(worst,abs(cv2.pointPolygonTest(quad,(float(point[0]),float(point[1])),True)))
            if worst>tolerance:
                break
        if worst>tolerance:
            continue
        for point in points:
            worst=max(worst,abs(cv2.pointPolygonTest(contour,(float(point[0]),float(point[1])),True)))
        if worst>tolerance:
            continue
        score=worst+abs(quad_area-area)/area
        if best is None or score<best[0]:
            best=(score,quad)
    return best[1] if best else None

def _region(labels, stats, index, rgb, width, height, options):
    x, y, w, h, pixels = [int(v) for v in stats[index]]
    working_h, working_w = labels.shape
    scale_x, scale_y = width/working_w, height/working_h
    # Noise/text holes are filtered before allocating contour masks.
    minimum = options['min_area']/(scale_x*scale_y) if options['min_area'] else max(90, working_w*working_h*.00010)
    if pixels < minimum or min(w, h) < 5:
        return None
    if x <= 1 or y <= 1 or x+w >= working_w-1 or y+h >= working_h-1:
        return None
    mask = np.asarray(labels[y:y+h,x:x+w] == index, dtype=np.uint8)*255
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours,key=cv2.contourArea)
    area = cv2.contourArea(contour)
    if area < minimum:
        return None
    perimeter = cv2.arcLength(contour,True)
    approximation = _four_corner_fit(contour)
    if approximation is None:
        return None
    hull_area = cv2.contourArea(cv2.convexHull(contour)) or 1
    solidity = area/hull_area
    extent = area/max(w*h,1)
    # Text leaves holes. Region color is estimated only from connected interior.
    sampled = rgb[y:y+h,x:x+w][mask != 0]
    color = np.median(sampled[::max(1,len(sampled)//3000)],axis=0).astype(np.uint8)
    hsv = cv2.cvtColor(color.reshape((1,1,3)),cv2.COLOR_RGB2HSV)[0,0]
    hue,saturation,value = [int(v) for v in hsv]
    aspect = max(w/h,h/w)
    ratio = area/(working_w*working_h)
    polygon = [[round((float(point[0][0])+x)*scale_x,2),round((float(point[0][1])+y)*scale_y,2)] for point in approximation]
    centroid = [round((x+w/2)*scale_x,2),round((y+h/2)*scale_y,2)]
    return {'polygon':polygon,'confidence':0.,'suggested_number':None,
            'reason':'Four-sided image boundary; verify its four corners and label.',
            'source':'closed_boundary','centroid':centroid,
            '_area':area,'_pixels':pixels,'_ratio':ratio,'_solidity':solidity,
            '_extent':extent,'_aspect':aspect,'_hue':hue,'_saturation':saturation,
            '_value':value,'_bbox':[x,y,w,h],'_index':index,
            '_occupancy':pixels/max(area,1),'_vertices':len(approximation),
            '_circularity':4*math.pi*area/max(perimeter*perimeter,1)}


def _classification(region, median_area, options):
    area,ratio = region['_area'],region['_ratio']
    aspect,extent = region['_aspect'],region['_extent']
    saturation,value = region['_saturation'],region['_value']
    low_sat = saturation < 135
    # Long neutral strips and branching neutral networks are usually roads.
    # A small, compact dark/blue plot is kept; fill color never means status.
    if low_sat and ((aspect > 6 and area > 120) or (extent < .42 and ratio > .003 and region['_solidity'] < .90)):
        return 'road','Long or branching neutral region resembles a road; excluded from plot suggestions.'
    if region['_occupancy'] < .38:
        return 'background','Mostly hollow linework or a frame, rather than an individual plot interior.'
    if ratio > options['max_area_ratio']:
        return 'background','Region is too large to confidently identify as one plot.'
    if low_sat and value < 185 and (aspect > 3.8 or (area > median_area*4 and region['_solidity'] < .65)):
        return 'road','Broad neutral connected strip resembles a road.'
    # Parks are commonly broad unpartitioned green regions; small green plots
    # remain eligible. This is a conservative heuristic, not land-use detection.
    if 30 <= region['_hue'] <= 95 and saturation > 15 and region['_vertices'] >= 6 and region['_extent'] < .85 and area < median_area*.3:
        return 'open_space','Small circular green symbol may represent a tree.'
    if 30 <= region['_hue'] <= 95 and saturation > 15 and area > median_area*3.2 and ratio > .008:
        return 'open_space','Large unpartitioned green region may be a park or open space.'
    if region['_vertices']>5 and area<median_area*.2 and (region['_solidity']<.8 or extent<.7):
        return 'background','Small complex mark resembles text rather than a plot boundary.'
    if aspect > 10 or region['_solidity'] < .35 or extent < .23:
        return 'background','Region is too narrow or fragmented to suggest as a plot.'
    if value > 247 and saturation < 12 and area > median_area*2.5:
        return 'background','Large plain white region may be a title, margin or legend.'
    return None,None


def _color_regions(rgb,width,height,options,deadline):
    """Recover fill interiors without closing text onto thin plot borders.

    Coarse HSV buckets tolerate JPEG noise. Neutral fills are grouped by value
    rather than unreliable low-saturation hue; this also handles white plots.
    """
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    hue,saturation,value=[channel.astype(np.int32) for channel in cv2.split(hsv)]
    neutral_code=np.where(value>=190,20,value//16)
    codes=np.where(saturation<45,neutral_code,32+(hue//12)*32+(saturation//64)*8+value//32).astype(np.int32)
    frequencies=np.bincount(codes.ravel())
    codes_to_try=np.argsort(frequencies)[::-1][:24]
    regions=[]
    minimum=max(50,rgb.shape[0]*rgb.shape[1]*.000055)
    for code in codes_to_try:
        if frequencies[code]<minimum or time.monotonic()>deadline:break
        mask=np.asarray(codes==code,dtype=np.uint8)*255
        count,labels,stats,_=cv2.connectedComponentsWithStats(mask,connectivity=4)
        indices=np.argsort(stats[1:,cv2.CC_STAT_AREA])[::-1][:300]+1
        for index in indices:
            region=_region(labels,stats,int(index),rgb,width,height,options)
            if region:
                region['source']='color_boundary'
                region['reason']='Connected fill inside a visible boundary; verify all corners.'
                regions.append(region)
            if len(regions)>=600 or time.monotonic()>deadline:return regions
    return regions


def _line_regions(edges,rgb,width,height,options):
    # A supplemental straight-line pass recovers narrow numbered cells where
    # printed text otherwise touches an edge. Irregular boundaries continue to
    # come from the general/color passes; no rectangular grid is generated.
    horizontal=cv2.morphologyEx(edges,cv2.MORPH_OPEN,np.ones((1,9),np.uint8))
    vertical=cv2.morphologyEx(edges,cv2.MORPH_OPEN,np.ones((9,1),np.uint8))
    lines=cv2.morphologyEx(cv2.bitwise_or(horizontal,vertical),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    _,labels,stats,_=cv2.connectedComponentsWithStats(cv2.bitwise_not(lines),connectivity=4)
    regions=[]
    for index in np.argsort(stats[1:,cv2.CC_STAT_AREA])[::-1][:600]+1:
        region=_region(labels,stats,int(index),rgb,width,height,options)
        if region and region['_solidity']>.94 and region['_extent']>.84:
            region['source']='line_boundary'
            region['reason']='Enclosed straight boundary with small printed marks removed; verify the outline.'
            regions.append(region)
    return regions

def _overlap(left,right):
    # Compare rasterized polygons, never their bounding boxes alone: irregular
    # neighbors can share overlapping boxes while having disjoint interiors.
    lp=np.asarray(left['polygon'],np.float32)
    rp=np.asarray(right['polygon'],np.float32)
    lx,ly,lw,lh=cv2.boundingRect(lp);rx,ry,rw,rh=cv2.boundingRect(rp)
    if lx+lw<rx or rx+rw<lx or ly+lh<ry or ry+rh<ly:return 0
    x,y=min(lx,rx),min(ly,ry)
    w,h=max(lx+lw,rx+rw)-x+1,max(ly+lh,ry+rh)-y+1
    scale=min(1.,500/max(w,h))
    size=(max(1,math.ceil(h*scale)),max(1,math.ceil(w*scale)))
    masks=[]
    for polygon in [lp,rp]:
        mask=np.zeros(size,np.uint8)
        cv2.fillPoly(mask,[np.rint((polygon-[x,y])*scale).astype(np.int32)],1)
        masks.append(mask)
    return float(np.count_nonzero(masks[0]&masks[1]))/max(1,min(np.count_nonzero(masks[0]),np.count_nonzero(masks[1])))

def _public(region):
    return {key:value for key,value in region.items() if not key.startswith('_')}


def _ocr(rgb,candidates,warnings,width,height):
    executable = shutil.which('tesseract')
    if executable is None:
        warnings.append('Automatic number reading is unavailable. Add or verify plot numbers during review.')
        return
    if not candidates:
        return
    # One bounded whole-image TSV pass. No subprocess per plot and no network.
    ocr_scale=min(2.,2800/max(rgb.shape[:2]))
    ocr_rgb=cv2.resize(rgb,None,fx=ocr_scale,fy=ocr_scale,interpolation=cv2.INTER_CUBIC) if ocr_scale>1 else rgb
    success,encoded = cv2.imencode('.png',cv2.cvtColor(ocr_rgb,cv2.COLOR_RGB2BGR))
    if not success:
        return
    try:
        completed = subprocess.run([executable,'stdin','stdout','--psm','11','tsv'],input=encoded.tobytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=6,check=False,env={**os.environ,'OMP_THREAD_LIMIT':'1','OMP_NUM_THREADS':'1'})
        if completed.returncode:
            warnings.append('Plot numbers could not be read automatically. Enter them during review.')
            return
        if len(completed.stdout) > 2_000_000:
            warnings.append('Number reading produced too much text. Enter plot numbers during review.')
            return
        rows = csv.DictReader(io.StringIO(completed.stdout.decode('utf-8','replace')),delimiter='\t')
        matches = {}
        sx,sy=width/ocr_rgb.shape[1],height/ocr_rgb.shape[0]
        for row in rows:
            text = row.get('text','').strip().replace('–','-').replace('—','-')
            # Never interpret dimensions, prices, road widths or area units.
            if re.fullmatch(r'\d+[xX]',text):
                continue
            if text.isdigit() and int(text)==0:
                continue
            if not re.fullmatch(r'(?:[A-Za-z]{1,3}[- ]?)?\d{1,4}[A-Za-z]?',text):
                continue
            try:
                confidence=float(row.get('conf','-1'))
                cx=(float(row['left'])+float(row['width'])/2)*sx
                cy=(float(row['top'])+float(row['height'])/2)*sy
            except (ValueError,KeyError):
                continue
            if confidence < 40:
                continue
            for index,candidate in enumerate(candidates):
                polygon=np.asarray(candidate['polygon'],np.float32)
                if cv2.pointPolygonTest(polygon,(cx,cy),False) >= 0:
                    center=candidate['centroid']
                    distance=math.hypot(cx-center[0],cy-center[1])
                    score=confidence-distance*.1
                    if index not in matches or score > matches[index][0]:
                        matches[index]=(score,re.sub(r'\s+','-',text),confidence)
                    break
        for index,(_,text,confidence) in matches.items():
            candidates[index]['suggested_number']=text
            candidates[index]['number_confidence']=round(confidence/100,2)
        numbers={}
        for index,candidate in enumerate(candidates):
            number=candidate.get('suggested_number')
            if number:numbers.setdefault(number,[]).append(index)
        for number,indexes in numbers.items():
            if len(indexes)>1:
                for index in indexes:
                    candidates[index]['suggested_number']=None
                    candidates[index].pop('number_confidence',None)
        warnings.append('Automatically read plot numbers are suggestions. Verify every number against the original plan.')
    except (subprocess.TimeoutExpired,OSError):
        warnings.append('Automatic number reading timed out or is unavailable. Enter plot numbers during review.')


def detect_plot_regions(image,options=None):
    """Find reviewable enclosed regions without creating records or statuses.

    ``image`` accepts a local path, binary file/FieldFile, or a PIL image.
    ``min_area`` is in original image pixels squared. Defaults adapt to image
    size. Colors never imply availability. Runtime is bounded by downsampling,
    component/candidate limits, and a single six-second optional OCR process.
    """
    started=time.monotonic()
    options=_options(options)
    rgb,width,height=_prepare(image,options)
    edges,labels,stats,centroids,count=_segments(rgb,options)
    warnings=['Only four-sided plots are suggested automatically. Review all four corners; image analysis cannot verify surveyed boundaries, plot ownership or availability.']
    regions=[]
    # Only bounded large components enter Python contour extraction.
    indices=np.argsort(stats[1:,cv2.CC_STAT_AREA])[::-1][:MAX_COMPONENTS]+1
    if count>MAX_COMPONENTS:
        warnings.append('This plan contains many small regions. Tiny or fragmented regions may be omitted.')
    for index in indices:
        region=_region(labels,stats,int(index),rgb,width,height,options)
        if region:regions.append(region)
        if time.monotonic()-started>8:
            warnings.append('Boundary analysis reached its time limit. Use click-to-add for missed regions.')
            break
    regions.extend(_line_regions(edges,rgb,width,height,options))
    regions.extend(_color_regions(rgb,width,height,options,started+8))
    compact=[r['_area'] for r in regions if r['_aspect']<4 and r['_solidity']>.7 and r['_ratio']<options['max_area_ratio'] and r['_area']>150]
    median=float(np.median(compact)) if compact else max(100,rgb.shape[0]*rgb.shape[1]*.002)
    candidates,excluded=[],[]
    for region in regions:
        kind,reason=_classification(region,median,options)
        if kind:
            excluded.append({'polygon':region['polygon'],'kind':kind,'reason':reason})
            continue
        region['confidence']=round(max(.35,min(.96,.55+.2*region['_solidity']+.15*region['_extent']-(.12 if region['_area']>median*4 else 0))),2)
        candidates.append(region)
    # Prefer intact fill contours to edge components split by tiny printed labels.
    candidates.sort(key=lambda r:({'line_boundary':0,'color_boundary':1,'closed_boundary':2}[r['source']],-r['confidence'],-r['_area']))
    unique=[]
    for region in candidates:
        if not any(_overlap(region,other)>.80 for other in unique):unique.append(region)
    candidates=unique
    # Isolated title/legend boxes are unlike neighboring plot partitions.
    if len(candidates)>5:
        retained=[]
        for region in candidates:
            x,y,w,h=region['_bbox']
            nearby=sum(1 for other in candidates if other is not region and
                       math.hypot(other['centroid'][0]-region['centroid'][0],other['centroid'][1]-region['centroid'][1]) < max(w,h)*2.2*(width/rgb.shape[1]))
            if nearby==0 and region['_value']>235 and region['_saturation']<35:
                excluded.append({'polygon':region['polygon'],'kind':'background','reason':'Isolated pale box may be a title or legend.'})
            else:retained.append(region)
        candidates=retained
    candidates.sort(key=lambda r:(round(r['centroid'][1]/20),r['centroid'][0]))
    if len(candidates)>options['max_candidates']:
        warnings.append(f'Only {options["max_candidates"]} candidates were returned. Review these, then use click-to-add for remaining regions.')
        candidates=candidates[:options['max_candidates']]
    candidates=[_public(region) for region in candidates]
    if options['ocr']:_ocr(rgb,candidates,warnings,width,height)
    if not candidates:warnings.append('No closed four-sided plot boundaries were found. Try a sharper plan or click inside a four-sided plot. Other shapes require the manual polygon tool.')
    return {'candidates':candidates,'excluded_regions':excluded[:100],'warnings':warnings,'width':width,'height':height,
            'processing_size':[rgb.shape[1],rgb.shape[0]],'elapsed_ms':round((time.monotonic()-started)*1000)}


def detect_region_at_point(image,x,y,options=None):
    """Recover an enclosed region under a click, retaining road/background checks."""
    options=_options(options)
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in [x,y]):
        raise ValueError('Choose a finite image coordinate.')
    rgb,width,height=_prepare(image,options)
    if not 0<=x<width or not 0<=y<height:
        raise ValueError('Click inside the plan image.')
    options['min_area']=min(options['min_area'],40) if options['min_area'] else 40
    edges,labels,stats,centroids,count=_segments(rgb,options)
    px,py=round(x*rgb.shape[1]/width),round(y*rgb.shape[0]/height)
    px=min(px,rgb.shape[1]-1);py=min(py,rgb.shape[0]-1)
    ids={int(labels[py,px])}
    # Clicking a printed number or boundary should select the surrounding region.
    for radius in [3,6,10]:
        for dx,dy in [(-radius,0),(radius,0),(0,-radius),(0,radius)]:
            ids.add(int(labels[min(max(py+dy,0),rgb.shape[0]-1),min(max(px+dx,0),rgb.shape[1]-1)]))
    regions=[]
    for index in ids:
        if index==0:continue
        region=_region(labels,stats,index,rgb,width,height,options)
        if region:regions.append(region)
    # Fill recovery makes tiny plots selectable even when a printed label
    # divides their edge component. Use the complete plan's size distribution
    # for park/road rejection, but return only the clicked local region.
    all_color=_color_regions(rgb,width,height,options,time.monotonic()+5)
    compact=[r['_area'] for r in all_color if r['_aspect']<4 and r['_solidity']>.7 and r['_ratio']<options['max_area_ratio'] and r['_area']>150]
    median=float(np.median(compact)) if compact else max(100,rgb.shape[0]*rgb.shape[1]*.002)
    for region in all_color:
        if cv2.pointPolygonTest(np.asarray(region['polygon'],np.float32),(float(x),float(y)),False)>=0:
            regions.append(region)
    regions.sort(key=lambda r:(cv2.pointPolygonTest(np.asarray(r['polygon'],np.float32),(float(x),float(y)),False)<0,r['source']!='color_boundary',r['_area']))
    warnings=['Review the suggested boundary against the original image before adding it. No availability or legal boundary has been inferred.']
    excluded=[]
    for region in regions:
        if cv2.pointPolygonTest(np.asarray(region['polygon'],np.float32),(float(x),float(y)),False)<0:
            continue
        kind,reason=_classification(region,median,options)
        if kind:
            excluded.append({'polygon':region['polygon'],'kind':kind,'reason':reason})
            continue
        region['confidence']=round(min(.90,.55+.2*region['_solidity']+.15*region['_extent']),2)
        candidate=_public(region)
        if options['ocr']:_ocr(rgb,[candidate],warnings,width,height)
        return {'candidates':[candidate],'excluded_regions':excluded,'warnings':warnings,'width':width,'height':height}
    warnings.append('No enclosed four-sided plot was found at this point. Other shapes, roads and open regions are excluded. Try the plot interior or use the manual polygon tool.')
    return {'candidates':[],'excluded_regions':excluded,'warnings':warnings,'width':width,'height':height}
