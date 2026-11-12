"""Opt-in, conspicuously labelled development inventory; never real offerings."""
import json
from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from estate.models import State, City, Area, Project, ProjectLayout, Plot, ProjectImage, GalleryCategory


class Command(BaseCommand):
    help = 'Create a clearly labelled DEMO project and 63 illustrative plots for local development only. Preserves existing records.'

    @transaction.atomic
    def handle(self, *args, **options):
        call_command('seed_content', verbosity=options['verbosity'])
        assets = Path(settings.BASE_DIR) / 'estate/static/estate/images'
        state, _ = State.objects.get_or_create(name='Uttar Pradesh')
        city, _ = City.objects.get_or_create(state=state, name='Ghaziabad')
        area, _ = Area.objects.get_or_create(slug='mandola-vihar', defaults={
            'city': city, 'name': 'Mandola Vihar',
            'description': 'Location named in the supplied Govindpuram Society reference. The current project inventory is a demonstration, not a verified offering.',
        })
        if not area.image:
            with (assets / 'hero.webp').open('rb') as stream:
                area.image.save('mandola-vihar-illustrative.webp', File(stream), save=True)
        project, created = Project.objects.get_or_create(slug='govindpuram-society-demo', defaults={
            'area': area, 'name': 'Govindpuram Society — DEMO', 'code': 'DEMO-GOV',
            'is_demo': True, 'status': 'published', 'featured': True,
            'short_description': 'Explore a reconstructed society plan and try interactive plot selection. Demonstration inventory only.',
            'description': 'A demonstration of the Plot Matrix master-plan experience, based on the supplied Govindpuram Society reference. Explore individual plots, compare options and try an enquiry. All plot availability, areas and orientations in this demo are sample values, not confirmed company inventory. The layout is a manually traced illustration and must be replaced by an administrator with the original verified plan before use for sales.',
            'address': 'Govindpuram Society, Mandola Vihar, Ghaziabad, Uttar Pradesh',
            'plot_size_range': '50–500 sq. yd. (supplied reference; verify with the team)',
            'road_widths': '14, 22, 25 and 60 ft (reference plan)',
            'disclaimer': 'DEMO ONLY. Plot availability, areas and orientations are sample data. This reconstructed plan is not a surveyed or approved layout and is not an offering for sale. Confirm all real project information directly with Plot Matrix.',
            'highlights': 'Interactive society master-plan preview\nIndividual plot information\nDirect contact with the Plot Matrix team',
        })
        if not created and not project.is_demo:
            self.stdout.write(self.style.WARNING('An existing non-demo project uses this slug. It was preserved; no demo data added.'))
            return
        if not project.cover_image:
            with (assets / 'hero.webp').open('rb') as stream:
                project.cover_image.save('govindpuram-illustrative.webp', File(stream), save=True)
        layout = project.layouts.filter(title='Demonstration reconstruction').first()
        if not layout:
            layout = ProjectLayout(project=project, title='Demonstration reconstruction', revision=1, active=True, is_draft=False)
            with (assets / 'govindpuram-plan.png').open('rb') as stream:
                layout.image.save('govindpuram-demo-plan.png', File(stream), save=False)
            layout.full_clean()
            layout.save()
        geometry = json.loads((assets / 'demo-geometry.json').read_text())
        added = 0
        for index, item in enumerate(geometry):
            _, was_added = Plot.objects.get_or_create(layout=layout, block='', number=item['number'], defaults={
                'project': project, 'polygon': item['polygon'],
                'label_x': item['label_position'][0], 'label_y': item['label_position'][1],
                'area': item['area'], 'area_unit': 'sqyd',
                'road_width': f"{item['road_width']} ft", 'facing': ['East', 'North', 'West', 'South'][index % 4],
                'status': 'sold' if index % 7 == 0 else 'booked' if index % 5 == 0 else 'available',
                'description': 'DEMO plot. Geometry, area, orientation and status are illustrative sample values only.',
                'public_remarks': 'Demonstration data — confirm real inventory with the sales team.',
                'display_order': index,
            })
            added += int(was_added)
        category, _ = GalleryCategory.objects.get_or_create(slug='brochure-imagery', defaults={'name': 'Brochure imagery'})
        for index, (filename, caption) in enumerate([
            ('hero.webp', 'Illustrative development aerial from the supplied company brochure.'),
            ('community.webp', 'Illustrative plotted community model from the supplied company brochure.'),
            ('development.webp', 'Illustrative residential architecture from the supplied company brochure.'),
            ('architecture.webp', 'Illustrative architectural imagery from the supplied company brochure.'),
        ]):
            if not ProjectImage.objects.filter(project=project, caption=caption).exists():
                image = ProjectImage(project=project, category=category, caption=caption, alt_text=caption, featured=True, display_order=index)
                with (assets / filename).open('rb') as stream:
                    image.image.save(filename, File(stream), save=True)
        self.stdout.write(self.style.SUCCESS(f'DEMO project prepared: {added} new sample plots; {layout.plots.count()} total. No real inventory or pricing represented.'))
