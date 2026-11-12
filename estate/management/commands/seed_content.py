"""Initialize editable content from the supplied company brochure, without fake claims."""
from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from estate.models import SiteSettings, Service, Page, HomepageSection
from estate.templatetags.cms import DEFAULT_HOMEPAGE_SECTIONS


class Command(BaseCommand):
    help = 'Initialize company information and services from the supplied brochure. Existing content is preserved.'

    @transaction.atomic
    def handle(self, *args, **options):
        assets = Path(settings.BASE_DIR) / 'estate/static/estate/images'
        company, created = SiteSettings.objects.get_or_create(pk=1, defaults={
            'mission': 'To provide exceptional real estate services through dedication, integrity and thoughtful innovation.',
            'vision': 'To be a trusted and respected real estate company, known for attentive service and lasting relationships.',
            'about': 'Plot Matrix helps families discover residential plots and explore planned communities. Our team offers personal guidance in residential sales, property management and real estate opportunities.',
            'hero_title': 'A place to belong.\nA future to build.',
            'hero_eyebrow': 'THOUGHTFULLY PLANNED. BEAUTIFULLY CONNECTED.',
            'hero_description': 'Discover residential plots and thoughtfully planned communities. Find the space to bring your future to life.',
        })
        for field, filename in [('logo', 'logo.png'), ('hero_image', 'hero.webp')]:
            path = assets / filename
            if not getattr(company, field) and path.is_file():
                with path.open('rb') as stream:
                    getattr(company, field).save(filename, File(stream), save=True)
        for order, title, description in [
            (0, 'Residential Plot Sales', 'Find a space to call your own, with personal guidance through your residential plot search.'),
            (1, 'Property Management', 'Thoughtful property support to help make ownership simpler.'),
            (2, 'Real Estate Investment Opportunities', 'Explore real estate opportunities with clear information and a conversation about your needs.'),
        ]:
            Service.objects.get_or_create(title=title, defaults={'description': description, 'display_order': order})
        for order, section in enumerate(DEFAULT_HOMEPAGE_SECTIONS):
            HomepageSection.objects.get_or_create(key=section['key'], defaults={
                'title': section['title'], 'body': section['body'],
                'display_order': order, 'enabled': True,
            })
        Page.objects.get_or_create(slug='privacy', defaults={
            'title': 'Privacy policy', 'published': True,
            'body': 'When you submit an enquiry or request a site visit, Plotmatrix Private Limited receives the contact details and message you provide. We use this information to respond to your request and arrange your requested follow-up.\nYou can contact info@plotmatrix.in to ask about the personal information you have provided, or request its correction or removal.\nThis website uses essential security and session cookies. Plot comparison and recently viewed choices may be stored in your browser. You can remove these through your browser settings.\nWhatsApp and map links open third-party services. Their own privacy policies apply when you choose to visit them. Do not include payment information or other sensitive data in an enquiry.\nFor privacy enquiries, write to info@plotmatrix.in or call +91 9250608786. The company administrator should review this policy before launching the website.'})
        Page.objects.get_or_create(slug='terms', defaults={
            'title': 'Terms of use', 'published': True,
            'body': 'Information on this website helps you explore residential developments and contact Plot Matrix. Availability, pricing, dimensions and project information should be confirmed directly with the sales team and checked against the relevant project documents.\nSubmitting an enquiry or a site visit request does not reserve, book or purchase a plot. Any transaction requires the separate confirmation and documentation agreed with the company.\nDemonstration projects and reconstructed plans are clearly marked. They are for exploring website functionality and must not be relied upon as genuine inventory, surveyed boundaries, approvals or offers for sale. Brochure imagery is illustrative unless specifically identified otherwise.\nMaps and third-party links are provided for convenience. Confirm the site location and appointment with the team before travelling.\nFor questions contact info@plotmatrix.in. The company administrator should review these terms before launching the website.'})
        self.stdout.write(self.style.SUCCESS('Company content initialized. Existing content preserved; no sales figures, endorsements, approvals or availability invented.'))
