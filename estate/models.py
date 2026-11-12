from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.text import slugify
from .validators import validate_image, validate_pdf, validate_maps_url, safe_https_url, validate_polygon

class OrderedModel(models.Model):
    display_order = models.PositiveIntegerField(default=0)
    class Meta:
        abstract = True
        ordering = ('display_order', 'pk')

class SiteSettings(models.Model):
    company_name = models.CharField(max_length=160, default='Plotmatrix Private Limited')
    brand_name = models.CharField(max_length=80, default='Plot Matrix')
    tagline = models.CharField(max_length=120, default='Create Your Future')
    logo = models.ImageField(upload_to='brand/', blank=True, validators=[validate_image])
    hero_image = models.ImageField(upload_to='brand/', blank=True, validators=[validate_image])
    hero_title = models.CharField(max_length=200, default='A place to belong.\nA future to build.')
    hero_eyebrow = models.CharField(max_length=160, default='Thoughtfully planned. Beautifully connected.')
    hero_description = models.TextField(default='Discover residential plots and thoughtfully planned communities. Find the space to bring your future to life.')
    about = models.TextField(default='Plot Matrix helps families discover residential plots and explore thoughtfully planned communities, with clear information and personal guidance at every step.')
    mission = models.TextField(default='To help families find the right space to create their future through thoughtful planning, clear information and personal guidance.')
    vision = models.TextField(default='To create connected residential communities where people can build a place to belong.')
    phone = models.CharField(max_length=30, default='+91 9250608786')
    secondary_phone = models.CharField(max_length=30, default='+91 9355144004')
    whatsapp = models.CharField(max_length=20, default='919250608786')
    email = models.EmailField(default='info@plotmatrix.in')
    address = models.TextField(default='71, Radhey Shyam Park, Sahibabad, Ghaziabad, Uttar Pradesh – 201005')
    website = models.URLField(default='https://plotmatrix.in', validators=[safe_https_url])
    footer_text = models.TextField(default='Thoughtfully planned spaces. Meaningful beginnings.')
    seo_title = models.CharField(max_length=200, default='Plot Matrix — Create Your Future')
    seo_description = models.TextField(default='Explore Plot Matrix residential developments, society master plans and individual plots. Connect with our team to plan your site visit.')
    def __str__(self): return self.company_name
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
    @classmethod
    def load(cls):
        return cls.objects.filter(pk=1).first() or cls()
    class Meta:
        verbose_name_plural = 'Company settings'

class State(OrderedModel):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

class City(OrderedModel):
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name='cities')
    name = models.CharField(max_length=100)
    class Meta(OrderedModel.Meta):
        constraints = [models.UniqueConstraint(fields=['state','name'], name='unique_city_state')]
    def __str__(self): return self.name

class Area(OrderedModel):
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name='areas')
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='locations/', blank=True, validators=[validate_image])
    active = models.BooleanField(default=True)
    def __str__(self): return f'{self.name}, {self.city}'
    def get_absolute_url(self): return f'/locations/{self.slug}/'

class Amenity(OrderedModel):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=40, default='check', help_text='Icon name, not HTML.')
    def __str__(self): return self.name

class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='published', area__active=True)

class Project(OrderedModel):
    class Status(models.TextChoices):
        DRAFT='draft','Draft'; PUBLISHED='published','Published'; ARCHIVED='archived','Archived'
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name='projects')
    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    code = models.CharField(max_length=40, blank=True)
    short_description = models.TextField(blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    is_demo = models.BooleanField(default=False, help_text='Demo projects are prominently labelled and must not be treated as real offerings.')
    featured = models.BooleanField(default=False)
    cover_image = models.ImageField(upload_to='projects/', blank=True, validators=[validate_image])
    address = models.TextField(blank=True)
    project_type = models.CharField(max_length=100, default='Residential plotted development')
    development_status = models.CharField(max_length=100, blank=True)
    total_area = models.CharField(max_length=100, blank=True, help_text='Include unit, e.g. 47,000 sq. yd.')
    plot_size_range = models.CharField(max_length=100, blank=True)
    road_widths = models.CharField(max_length=160, blank=True)
    highlights = models.TextField(blank=True, help_text='One highlight per line.')
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='projects')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    maps_url = models.URLField(max_length=1000, blank=True, validators=[validate_maps_url])
    maps_embed_url = models.URLField(max_length=1000, blank=True, validators=[validate_maps_url])
    brochure = models.FileField(upload_to='documents/', blank=True, validators=[validate_pdf])
    approval_document = models.FileField(upload_to='documents/', blank=True, validators=[validate_pdf])
    promotional_video_url = models.URLField(blank=True, validators=[safe_https_url])
    rera_number = models.CharField(max_length=160, blank=True)
    regulatory_authority = models.CharField(max_length=200, blank=True)
    approval_details = models.TextField(blank=True)
    disclaimer = models.TextField(blank=True)
    completion_info = models.CharField(max_length=200, blank=True)
    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = models.Manager()
    public = PublishedManager()
    def __str__(self): return self.name
    def get_absolute_url(self): return f'/projects/{self.slug}/'
    def save(self,*args,**kwargs):
        old_slug = Project.objects.filter(pk=self.pk).values_list('slug',flat=True).first() if self.pk else None
        with transaction.atomic():
            super().save(*args,**kwargs)
            persisted_fields = kwargs.get('update_fields')
            slug_was_written = persisted_fields is None or 'slug' in persisted_fields
            if slug_was_written and old_slug and old_slug != self.slug:
                ProjectSlugHistory.objects.update_or_create(slug=old_slug,defaults={'project':self})
    @property
    def active_layout(self): return self.layouts.filter(active=True, is_draft=False).first()
    @property
    def availability(self):
        plots = self.plots.exclude(status='hidden')
        layout = self.active_layout
        plots = plots.filter(layout=layout) if layout else plots.none()
        return plots.aggregate(total=Count('pk'), available=Count('pk',filter=Q(status='available')), booked=Count('pk',filter=Q(status='booked')), sold=Count('pk',filter=Q(status='sold')))
    @property
    def highlight_list(self): return [line for line in self.highlights.splitlines() if line.strip()]

class ProjectLayout(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='layouts')
    title = models.CharField(max_length=140, default='Society master plan')
    image = models.ImageField(upload_to='layouts/', validators=[validate_image], width_field='width', height_field='height')
    width = models.PositiveIntegerField(default=1200)
    height = models.PositiveIntegerField(default=800)
    revision = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    is_draft = models.BooleanField(default=False, help_text='Draft layouts are visible only to staff.')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ('-revision',)
        constraints = [models.UniqueConstraint(fields=['project','revision'],name='unique_layout_revision'),models.UniqueConstraint(fields=['project'],condition=Q(active=True,is_draft=False),name='one_active_public_layout')]
    def __str__(self): return f'{self.project} — revision {self.revision}'
    def clean(self):
        super().clean()
        if self.pk:
            old = ProjectLayout.objects.filter(pk=self.pk).first()
            if old and self.plots.exists() and self.project_id != old.project_id:
                raise ValidationError({'project':'A layout with plots cannot be moved to another project.'})
            if old and self.plots.exists() and (self.image.name != old.image.name or getattr(self.image,'_committed',True) is False):
                raise ValidationError({'image':'This revision already has plots. Create a new layout revision before replacing its image.'})
    def save(self,*args,**kwargs):
        self.clean()
        super().save(*args,**kwargs)

class Plot(OrderedModel):
    class Status(models.TextChoices):
        AVAILABLE='available','Available'; BOOKED='booked','Booked'; SOLD='sold','Sold'; BLOCKED='blocked','Not for sale'; HIDDEN='hidden','Hidden'
    class AreaUnit(models.TextChoices):
        SQFT='sqft','sq. ft.'; SQYD='sqyd','sq. yd.'; SQM='sqm','sq. m.'
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='plots')
    layout = models.ForeignKey(ProjectLayout, on_delete=models.PROTECT, related_name='plots')
    number = models.CharField(max_length=30)
    block = models.CharField(max_length=40, blank=True)
    slug = models.SlugField(max_length=100, blank=True)
    area = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01'))])
    area_unit = models.CharField(max_length=5, choices=AreaUnit.choices, default=AreaUnit.SQYD)
    length = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01'))])
    width = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01'))])
    dimension_unit = models.CharField(max_length=3, choices=[('ft','ft'),('m','m')], default='ft')
    facing = models.CharField(max_length=30, blank=True)
    corner = models.BooleanField(default=False)
    park_facing = models.BooleanField(default=False)
    road_width = models.CharField(max_length=40, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    show_price = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    description = models.TextField(blank=True)
    public_remarks = models.TextField(blank=True)
    internal_remarks = models.TextField(blank=True)
    polygon = models.JSONField(default=list, validators=[validate_polygon])
    label_x = models.FloatField(null=True, blank=True)
    label_y = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta(OrderedModel.Meta):
        constraints=[models.UniqueConstraint(fields=['layout','block','number'],name='unique_plot_number_layout'),models.UniqueConstraint(fields=['project','slug','layout'],name='unique_plot_slug_layout')]
        indexes=[models.Index(fields=['project','status'])]
    def __str__(self): return f'{self.project} / {self.number}'
    def get_absolute_url(self): return f'/projects/{self.project.slug}/plots/{self.slug}/'
    @property
    def area_sqft(self):
        if self.area is None: return None
        return self.area * {'sqft':Decimal(1),'sqyd':Decimal(9),'sqm':Decimal('10.7639104167')}[self.area_unit]
    def clean(self):
        super().clean()
        validate_polygon(self.polygon)
        if self.status not in self.Status.values:
            raise ValidationError({'status':'Choose a valid plot availability status.'})
        if self.layout_id:
            layout = self.layout
            if layout.project_id != self.project_id:
                raise ValidationError({'layout':'The layout must belong to the selected project.'})
            if any(x > layout.width or y > layout.height for x,y in self.polygon):
                raise ValidationError({'polygon':'Plot coordinates must fit inside the layout image.'})
            import math
            for field,maximum in [('label_x',layout.width),('label_y',layout.height)]:
                value=getattr(self,field)
                if value is not None and (not math.isfinite(value) or not 0 <= value <= maximum):
                    raise ValidationError({field:'Label position must fit inside the layout.'})
    def save(self,*args,**kwargs):
        if not self.slug: self.slug = slugify(f'{self.block}-{self.number}'.strip('-'))
        self.clean()
        with transaction.atomic():
            previous = Plot.objects.select_for_update().filter(pk=self.pk).values_list('status',flat=True).first() if self.pk else None
            super().save(*args,**kwargs)
            persisted_fields = kwargs.get('update_fields')
            status_was_written = persisted_fields is None or 'status' in persisted_fields
            if status_was_written and previous is not None and previous != self.status:
                actor = getattr(self,'_actor',None)
                PlotStatusHistory.objects.create(plot=self,previous_status=previous,new_status=self.status,user=actor,note=getattr(self,'_status_note',''))
    def set_status(self,status,user,note=''):
        if status not in self.Status.values: raise ValidationError('Unknown availability status.')
        if not user or not user.is_active or not user.is_staff or not user.has_perm('estate.change_plot'):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        self.status=status; self._actor=user; self._status_note=note
        self.save(update_fields=['status','updated_at'])

class PlotStatusHistory(models.Model):
    plot = models.ForeignKey(Plot,on_delete=models.CASCADE,related_name='status_history')
    previous_status = models.CharField(max_length=12)
    new_status = models.CharField(max_length=12)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    class Meta: ordering=('-timestamp',); verbose_name_plural='Plot status history'
    def __str__(self): return f'{self.plot.number}: {self.previous_status} → {self.new_status}'

class GalleryCategory(OrderedModel):
    name = models.CharField(max_length=100,unique=True)
    slug = models.SlugField(unique=True)
    def __str__(self): return self.name

class ProjectImage(OrderedModel):
    project = models.ForeignKey(Project,on_delete=models.CASCADE,related_name='images')
    category = models.ForeignKey(GalleryCategory,on_delete=models.SET_NULL,null=True,blank=True,related_name='images')
    image = models.ImageField(upload_to='gallery/',validators=[validate_image])
    caption = models.CharField(max_length=240,blank=True)
    alt_text = models.CharField(max_length=240)
    published = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.caption or self.alt_text

class Testimonial(OrderedModel):
    name = models.CharField(max_length=100)
    quote = models.TextField()
    designation = models.CharField(max_length=120,blank=True)
    photo = models.ImageField(upload_to='testimonials/',blank=True,validators=[validate_image])
    published = models.BooleanField(default=False)
    consent_confirmed = models.BooleanField(default=False,help_text='Confirm permission to publish this genuine testimonial.')
    def clean(self):
        if self.published and not self.consent_confirmed:
            raise ValidationError({'consent_confirmed':'Confirm publication permission before publishing.'})
    def __str__(self): return self.name

class Enquiry(models.Model):
    class Kind(models.TextChoices):
        GENERAL='general','General enquiry'; PLOT='plot','Plot enquiry'; SITE_VISIT='site_visit','Site visit'
    class Status(models.TextChoices):
        NEW='new','New'; CONTACTED='contacted','Contacted'; CLOSED='closed','Closed'
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=25)
    message = models.TextField(blank=True)
    project = models.ForeignKey(Project,on_delete=models.SET_NULL,null=True,blank=True,related_name='enquiries')
    plot = models.ForeignKey(Plot,on_delete=models.SET_NULL,null=True,blank=True,related_name='enquiries')
    kind = models.CharField(max_length=15,choices=Kind.choices,default=Kind.GENERAL)
    preferred_date = models.DateField(null=True,blank=True)
    status = models.CharField(max_length=12,choices=Status.choices,default=Status.NEW)
    staff_notes = models.TextField(blank=True)
    consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering=('-created_at',)
    def __str__(self): return f'{self.name} — {self.get_kind_display()}'
    def clean(self):
        if self.plot_id and self.project_id != self.plot.project_id:
            raise ValidationError({'plot':'Plot must belong to the selected project.'})

class HeroBanner(OrderedModel):
    title = models.CharField(max_length=200)
    subtitle = models.TextField(blank=True)
    image = models.ImageField(upload_to='banners/',validators=[validate_image])
    published = models.BooleanField(default=False)
    def __str__(self): return self.title

class Announcement(OrderedModel):
    text = models.CharField(max_length=240)
    link = models.URLField(blank=True,validators=[safe_https_url])
    published = models.BooleanField(default=False)
    def __str__(self): return self.text

class Page(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    body = models.TextField(help_text='Plain text, one paragraph per line. HTML is safely escaped.')
    published = models.BooleanField(default=False)
    seo_description = models.TextField(blank=True)
    def __str__(self): return self.title
    def get_absolute_url(self): return f'/pages/{self.slug}/'

class Article(OrderedModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    summary = models.TextField(blank=True)
    body = models.TextField()
    image = models.ImageField(upload_to='articles/',blank=True,validators=[validate_image])
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.title
    def get_absolute_url(self): return f'/insights/{self.slug}/'

class SocialLink(OrderedModel):
    name = models.CharField(max_length=60)
    url = models.URLField(validators=[safe_https_url])
    def __str__(self): return self.name

class Service(OrderedModel):
    title = models.CharField(max_length=160)
    description = models.TextField()
    published = models.BooleanField(default=True)
    def __str__(self): return self.title

class HomepageSection(OrderedModel):
    key = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    def __str__(self): return self.title

class VerifiedStatistic(OrderedModel):
    label = models.CharField(max_length=100)
    value = models.PositiveIntegerField()
    suffix = models.CharField(max_length=20,blank=True)
    published = models.BooleanField(default=False)
    verification_note = models.TextField(help_text='Private source of this verified fact.')
    def __str__(self): return self.label

class ProjectSlugHistory(models.Model):
    project = models.ForeignKey(Project,on_delete=models.CASCADE,related_name='previous_slugs')
    slug = models.SlugField(unique=True)
    changed_at = models.DateTimeField(auto_now=True)
    def __str__(self):return self.slug

class ProjectDocument(OrderedModel):
    project = models.ForeignKey(Project,on_delete=models.CASCADE,related_name='documents')
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to='documents/',validators=[validate_pdf])
    published = models.BooleanField(default=False)
    def __str__(self):return self.title
