from .models import SiteSettings, Project, Area, Service, SocialLink, Announcement, Page

def site_context(request):
    return {'site': SiteSettings.load(), 'published_projects': Project.public.select_related('area__city')[:20], 'published_areas': Area.objects.filter(active=True, projects__status='published').distinct().select_related('city'), 'services': Service.objects.filter(published=True), 'social_links': SocialLink.objects.all(), 'announcements': Announcement.objects.filter(published=True), 'legal_pages': Page.objects.filter(published=True,slug__in=['privacy','privacy-policy','terms','terms-of-use'])}
