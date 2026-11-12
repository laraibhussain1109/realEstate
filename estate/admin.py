from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html
from .models import (SiteSettings, State, City, Area, Amenity, Project, ProjectLayout, Plot, PlotStatusHistory, GalleryCategory, ProjectImage, Testimonial, Enquiry, HeroBanner, Announcement, Page, Article, SocialLink, Service, HomepageSection, VerifiedStatistic, ProjectDocument, ProjectSlugHistory)

admin.site.site_header = 'Plot Matrix · Company administration'
admin.site.site_title = 'Plot Matrix admin'
admin.site.index_title = 'Your development overview'
admin.site.index_template = 'admin/plotmatrix_index.html'
_original_index = admin.site.index

def dashboard(request, extra_context=None):
    ctx = dict(extra_context or {})
    if request.user.has_perm('estate.view_project'):
        plots = Plot.objects.filter(layout__active=True,layout__is_draft=False).exclude(status='hidden')
        ctx['plotmatrix_metrics'] = {'Projects': Project.objects.filter(status='published').count(), 'Total plots':plots.count(), 'Available':plots.filter(status='available').count(), 'Booked':plots.filter(status='booked').count(), 'Sold':plots.filter(status='sold').count(), 'Gallery images':ProjectImage.objects.count(), 'Published testimonials':Testimonial.objects.filter(published=True).count()}
        ctx['recent_plots'] = plots.select_related('project').order_by('-updated_at')[:5]
    if request.user.has_perm('estate.view_enquiry'):
        ctx.setdefault('plotmatrix_metrics',{}).update({'Total enquiries':Enquiry.objects.count(),'New enquiries':Enquiry.objects.filter(status='new').count(),'Site visit requests':Enquiry.objects.filter(kind='site_visit').count()})
        ctx['recent_enquiries'] = Enquiry.objects.select_related('project').order_by('-created_at')[:5]
    return _original_index(request, extra_context=ctx)
admin.site.index = dashboard

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [('Identity',{'fields':('company_name','brand_name','tagline','logo','website')}),('Homepage',{'fields':('hero_image','hero_eyebrow','hero_title','hero_description')}),('About the company',{'fields':('about','mission','vision')}),('Contact',{'fields':('phone','secondary_phone','whatsapp','email','address')}),('Footer and SEO',{'fields':('footer_text','seo_title','seo_description')})]
    def has_add_permission(self,request): return super().has_add_permission(request) and not SiteSettings.objects.exists()
    def has_delete_permission(self,request,obj=None): return False

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display=('name','display_order'); search_fields=('name',)
@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display=('name','state','display_order'); list_filter=('state',); search_fields=('name',); autocomplete_fields=('state',)
@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display=('name','city','active','display_order'); list_filter=('active','city__state','city'); search_fields=('name','city__name'); prepopulated_fields={'slug':('name',)}; autocomplete_fields=('city',)

class ProjectImageInline(admin.TabularInline):
    model=ProjectImage; extra=0; fields=('image','alt_text','caption','category','published','featured','display_order')
class LayoutInline(admin.TabularInline):
    model=ProjectLayout; extra=0; fields=('title','image','revision','active','is_draft','editor_link'); readonly_fields=('editor_link',); show_change_link=True
    def editor_link(self,obj):
        if obj.pk: return format_html('<a href="/admin/estate/projectlayout/{}/editor/">Open visual editor →</a>',obj.pk)
        return 'Save to open editor'

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display=('name','area','status','is_demo','featured','availability_summary','preview'); list_filter=('status','is_demo','featured','area__city','area'); search_fields=('name','code','area__name','address'); prepopulated_fields={'slug':('name',)}; autocomplete_fields=('area',); filter_horizontal=('amenities',); inlines=(LayoutInline,ProjectImageInline)
    readonly_fields=('created_at','updated_at','availability_summary','preview')
    fieldsets=[('Project identity',{'fields':('name','slug','code','area','status','is_demo','featured','display_order')}),('Presentation',{'fields':('short_description','description','cover_image','project_type','development_status','highlights','amenities')}),('Location',{'fields':('address','latitude','longitude','maps_url','maps_embed_url')}),('Specifications',{'fields':('total_area','plot_size_range','road_widths','completion_info','availability_summary')}),('Documents and disclosures',{'fields':('brochure','approval_document','promotional_video_url','rera_number','regulatory_authority','approval_details','disclaimer')}),('SEO',{'fields':('seo_title','seo_description')}),('System',{'fields':('preview','created_at','updated_at')})]
    @admin.display(description='Availability')
    def availability_summary(self,obj):
        if not obj.pk:return 'Save the project first'
        stats=obj.availability
        return f"{stats['available']} available · {stats['booked']} booked · {stats['sold']} sold / {stats['total']} total"
    def preview(self,obj):
        if not obj.pk:return 'Save project first'
        return format_html('<a href="{}?preview=1" target="_blank" rel="noopener">Preview project ↗</a>',obj.get_absolute_url())

@admin.register(ProjectLayout)
class ProjectLayoutAdmin(admin.ModelAdmin):
    list_display=('project','title','revision','active','is_draft','editor_link'); list_filter=('active','is_draft','project'); search_fields=('project__name','title'); autocomplete_fields=('project',); readonly_fields=('width','height','created_at','editor_link')
    fieldsets=[(None,{'fields':('project','title','revision','image','width','height','active','is_draft','editor_link','created_at'),'description':'Create a NEW revision to replace an image with existing plot boundaries. Deactivate the old revision before publishing the new one. JPEG, PNG and WebP are supported; safely convert PDF to an image first.'})]
    def editor_link(self,obj):
        if not obj or not obj.pk:return 'Save this layout to open the editor.'
        return format_html('<a class="button" href="/admin/estate/projectlayout/{}/editor/">Draw and manage plot boundaries →</a>',obj.pk)

@admin.register(Plot)
class PlotAdmin(admin.ModelAdmin):
    list_display=('number','block','project','layout','area','area_unit','status','updated_at'); list_filter=('status','project','facing','corner','park_facing'); search_fields=('number','block','project__name'); autocomplete_fields=('project','layout'); readonly_fields=('created_at','updated_at'); actions=('mark_available','mark_booked','mark_sold')
    fieldsets=[('Identity',{'fields':('project','layout','number','block','slug','display_order')}),('Availability and price',{'fields':('status','price','show_price')}),('Measurements',{'fields':('area','area_unit','length','width','dimension_unit','facing','road_width','corner','park_facing')}),('Descriptions',{'fields':('description','public_remarks','internal_remarks')}),('Map geometry',{'fields':('polygon','label_x','label_y'),'description':'Use the visual layout editor to draw boundaries. Coordinates use the image width and height.'}),('System',{'fields':('created_at','updated_at')})]
    def save_model(self,request,obj,form,change):
        obj._actor=request.user
        super().save_model(request,obj,form,change)
    def _status_action(self,request,queryset,status):
        with transaction.atomic():
            selected = list(queryset.select_for_update())
            for plot in selected:plot.set_status(status,request.user,note='Bulk update from company admin')
        self.message_user(request,f'{len(selected)} plots updated. Changes have been recorded in the audit history.',messages.SUCCESS)
    @admin.action(description='Mark selected plots Available',permissions=['change'])
    def mark_available(self,request,queryset):self._status_action(request,queryset,'available')
    @admin.action(description='Mark selected plots Booked',permissions=['change'])
    def mark_booked(self,request,queryset):self._status_action(request,queryset,'booked')
    @admin.action(description='Mark selected plots Sold',permissions=['change'])
    def mark_sold(self,request,queryset):self._status_action(request,queryset,'sold')

@admin.register(PlotStatusHistory)
class PlotStatusHistoryAdmin(admin.ModelAdmin):
    list_display=('plot','previous_status','new_status','user','timestamp'); list_filter=('new_status','timestamp','user'); search_fields=('plot__number','plot__project__name'); readonly_fields=('plot','previous_status','new_status','user','timestamp','note')
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False

@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display=('name','phone','kind','project','plot','preferred_date','status','created_at'); list_filter=('status','kind','project','created_at'); search_fields=('name','email','phone','message'); autocomplete_fields=('project','plot'); readonly_fields=('created_at',); date_hierarchy='created_at'; actions=('mark_contacted','mark_closed')
    @admin.action(description='Mark as contacted',permissions=['change'])
    def mark_contacted(self,request,queryset):queryset.update(status='contacted')
    @admin.action(description='Mark as closed',permissions=['change'])
    def mark_closed(self,request,queryset):queryset.update(status='closed')

@admin.register(ProjectImage)
class ProjectImageAdmin(admin.ModelAdmin):
    list_display=('__str__','project','category','published','featured','display_order'); list_filter=('project','category','published','featured'); search_fields=('caption','alt_text','project__name'); autocomplete_fields=('project',)
@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display=('name','designation','published','consent_confirmed','display_order'); list_filter=('published','consent_confirmed'); search_fields=('name','quote')
@admin.register(GalleryCategory)
class GalleryCategoryAdmin(admin.ModelAdmin):
    list_display=('name','display_order'); prepopulated_fields={'slug':('name',)}
@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):list_display=('name','icon','display_order'); search_fields=('name',)
@admin.register(HeroBanner)
class HeroBannerAdmin(admin.ModelAdmin):list_display=('title','published','display_order')
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):list_display=('text','published','display_order')
@admin.register(Page)
class PageAdmin(admin.ModelAdmin):list_display=('title','slug','published'); prepopulated_fields={'slug':('title',)}; search_fields=('title','body')
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):list_display=('title','published','created_at'); prepopulated_fields={'slug':('title',)}; search_fields=('title','summary')
@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):list_display=('name','url','display_order')
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):list_display=('title','published','display_order')
@admin.register(HomepageSection)
class HomepageSectionAdmin(admin.ModelAdmin):list_display=('title','key','enabled','display_order')
@admin.register(VerifiedStatistic)
class VerifiedStatisticAdmin(admin.ModelAdmin):list_display=('label','value','suffix','published','display_order')

@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    list_display=('title','project','published','display_order');list_filter=('published','project');search_fields=('title','project__name');autocomplete_fields=('project',)
@admin.register(ProjectSlugHistory)
class ProjectSlugHistoryAdmin(admin.ModelAdmin):
    list_display=('slug','project','changed_at');readonly_fields=('slug','project','changed_at')
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
