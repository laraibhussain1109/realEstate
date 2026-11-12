"""Validation at upload time, never in public page requests."""
import math
from pathlib import Path
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 15 * 1024 * 1024

def validate_image(upload):
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError('Images must be no larger than 15 MB.')
    if Path(upload.name).suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
        raise ValidationError('Upload a JPEG, PNG or WebP image. Convert PDF layouts to a raster image before uploading.')
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValidationError('Unsupported image content.')
            if image.width * image.height > 40_000_000:
                raise ValidationError('Image exceeds 40 megapixels. Please resize first.')
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError('The image cannot be safely opened.') from exc
    finally:
        upload.seek(0)

def validate_pdf(upload):
    """Parse PDF structure and reject active content at upload time.

    This does not make a regulatory document verified, nor replace malware
    scanning and trusted staff review. PDFs remain separate from layout images.
    """
    from pypdf import PdfReader
    from pypdf.generic import DictionaryObject, ArrayObject, IndirectObject
    from pypdf.errors import PdfReadError
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError('Documents must be no larger than 15 MB.')
    upload.seek(0)
    signature = upload.read(5)
    upload.seek(0)
    if Path(upload.name).suffix.lower() != '.pdf' or signature != b'%PDF-':
        raise ValidationError('Upload a valid PDF document.')
    try:
        reader = PdfReader(upload, strict=True)
        if reader.is_encrypted:
            raise ValidationError('Encrypted PDFs cannot be published. Upload an unencrypted copy.')
        if not 1 <= len(reader.pages) <= 200:
            raise ValidationError('Documents must have between 1 and 200 pages.')
        forbidden = {'/JavaScript','/JS','/OpenAction','/AA','/EmbeddedFiles','/EF','/XFA','/RichMedia','/AcroForm'}
        actions = {'/JavaScript','/Launch','/SubmitForm','/ImportData','/GoToR','/GoToE','/RichMediaExecute','/Rendition'}
        visited = set()
        budget = [0]
        def inspect(obj, depth=0):
            budget[0] += 1
            if budget[0] > 50000 or depth > 100:
                raise ValidationError('The PDF structure is too complex. Please export a flattened copy.')
            if isinstance(obj, IndirectObject):
                key=(obj.idnum,obj.generation)
                if key in visited:return
                visited.add(key)
                obj=obj.get_object()
            if isinstance(obj, DictionaryObject):
                if forbidden.intersection(str(key) for key in obj.keys()) or str(obj.get('/S','')) in actions or str(obj.get('/Type','')) == '/EmbeddedFile':
                    raise ValidationError('Active PDF content, attachments and forms are not allowed. Export a flattened copy.')
                for value in obj.values():inspect(value,depth+1)
            elif isinstance(obj, (ArrayObject,list,tuple)):
                for value in obj:inspect(value,depth+1)
        inspect(reader.trailer.get('/Root'))
    except ValidationError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
        raise ValidationError('The PDF could not be safely parsed. Please export a new PDF copy.') from exc
    finally:
        upload.seek(0)

def safe_https_url(value):
    if value:
        URLValidator(schemes=['https'])(value)

def validate_maps_url(value):
    if not value:
        return
    from urllib.parse import urlparse
    safe_https_url(value)
    host = (urlparse(value).hostname or '').lower()
    if not (host in {'maps.app.goo.gl', 'goo.gl', 'google.com', 'www.google.com', 'maps.google.com'} or host.endswith('.google.com')):
        raise ValidationError('Use an HTTPS Google Maps URL.')

def validate_polygon(points):
    if not isinstance(points, list) or not 3 <= len(points) <= 200:
        raise ValidationError('A plot boundary must have between 3 and 200 vertices.')
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2 or any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or n < 0 for n in point):
            raise ValidationError('Each vertex must contain two finite, nonnegative coordinates.')
    if len(set(tuple(p) for p in points)) != len(points):
        raise ValidationError('Every plot vertex must be distinct; do not repeat the closing vertex.')
    area = sum(points[i][0] * points[(i+1) % len(points)][1] - points[(i+1) % len(points)][0] * points[i][1] for i in range(len(points)))
    if not math.isfinite(area) or abs(area) < 1:
        raise ValidationError('Plot boundary must enclose a finite area.')
    def orientation(a, b, c):
        return (b[0]-a[0]) * (c[1]-a[1]) - (b[1]-a[1]) * (c[0]-a[0])
    def on_segment(a, b, p):
        return min(a[0],b[0]) <= p[0] <= max(a[0],b[0]) and min(a[1],b[1]) <= p[1] <= max(a[1],b[1])
    def intersects(a,b,c,d):
        abc,abd,cda,cdb = orientation(a,b,c),orientation(a,b,d),orientation(c,d,a),orientation(c,d,b)
        if abc*abd < 0 and cda*cdb < 0:
            return True
        return ((abc == 0 and on_segment(a,b,c)) or (abd == 0 and on_segment(a,b,d)) or
                (cda == 0 and on_segment(c,d,a)) or (cdb == 0 and on_segment(c,d,b)))
    for i in range(len(points)):
        a, b = points[i], points[(i+1) % len(points)]
        for j in range(i+1, len(points)):
            if j == i+1 or (i == 0 and j == len(points)-1):
                continue
            c, d = points[j], points[(j+1) % len(points)]
            if intersects(a,b,c,d):
                raise ValidationError('Plot boundaries must not cross, overlap or touch themselves.')
