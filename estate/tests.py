"""Business, publication, geometry and permission regression tests.

All inventory and testimonials in these tests are synthetic and isolated in the
Django test database. No production credentials or live services are needed.
"""
import io
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from PIL import Image
from pypdf import PdfWriter
from pypdf.actions import JavaScript
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .forms import EnquiryForm
from .models import (
    Area, City, Enquiry, GalleryCategory, Plot, PlotStatusHistory, Project,
    ProjectImage, ProjectLayout, ProjectSlugHistory, State, Testimonial,
)
from .validators import validate_image, validate_maps_url, validate_pdf, validate_polygon


def raster(name='plan.png', size=(400, 300)):
    output = io.BytesIO()
    Image.new('RGB', size, '#e8edf0').save(output, 'PNG')
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')


class EstateFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.state = State.objects.create(name='Test State')
        cls.city = City.objects.create(state=cls.state, name='Test City')
        cls.area = Area.objects.create(city=cls.city, name='Test Area', slug='test-area')
        cls.other_area = Area.objects.create(city=cls.city, name='Other Area', slug='other-area')
        cls.project = Project.objects.create(area=cls.area, name='Public Test Development', slug='public-development', status='published')
        cls.draft = Project.objects.create(area=cls.area, name='Private Draft Development', slug='draft-development', status='draft')
        cls.archived = Project.objects.create(area=cls.area, name='Private Archived Development', slug='archived-development', status='archived')
        cls.other_project = Project.objects.create(area=cls.other_area, name='Other Test Development', slug='other-development', status='published')
        cls.layout = ProjectLayout.objects.create(project=cls.project, image='layouts/test-plan.png', width=400, height=300)
        cls.draft_layout = ProjectLayout.objects.create(project=cls.project, image='layouts/draft-plan.png', width=400, height=300, revision=2, active=False, is_draft=True)
        cls.plot = Plot.objects.create(project=cls.project, layout=cls.layout, number='A-1', polygon=[[10,10],[100,10],[90,80],[10,70]], area=150, internal_remarks='CONFIDENTIAL SALES NOTE', price=Decimal('1000000.00'), show_price=False)
        cls.booked = Plot.objects.create(project=cls.project, layout=cls.layout, number='A-2', status='booked', polygon=[[110,10],[200,10],[200,80],[110,80]])
        cls.sold = Plot.objects.create(project=cls.project, layout=cls.layout, number='A-3', status='sold', polygon=[[210,10],[290,10],[290,80],[210,80]])
        cls.hidden = Plot.objects.create(project=cls.project, layout=cls.layout, number='SECRET-4', status='hidden', polygon=[[10,100],[100,100],[100,180],[10,180]])
        cls.revision_plot = Plot.objects.create(project=cls.project, layout=cls.draft_layout, number='DRAFT-5', polygon=[[10,10],[100,10],[100,80],[10,80]])
        cls.admin = get_user_model().objects.create_superuser('testadmin', 'admin@example.com', 'test-password-only')
        cls.staff = get_user_model().objects.create_user('staff-no-rights', password='test-password-only', is_staff=True)

    def api(self):
        return f'/api/projects/{self.project.slug}/plots/'

    def editor_api(self):
        return f'/api/layouts/{self.layout.pk}/plots/'

    def post_json(self, path, payload, client=None):
        return (client or self.client).post(path, data=json.dumps(payload), content_type='application/json')


class PublicPublicationTests(EstateFixture):
    def test_published_project_is_public_without_login(self):
        response = self.client.get(self.project.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)

    def test_draft_and_archived_detail_and_api_are_not_public(self):
        for project in (self.draft, self.archived):
            with self.subTest(project=project.slug):
                self.assertEqual(self.client.get(project.get_absolute_url()).status_code, 404)
                self.assertEqual(self.client.get(f'/api/projects/{project.slug}/plots/').status_code, 404)

    def test_inactive_area_suppresses_project(self):
        self.area.active = False
        self.area.save()
        self.assertEqual(self.client.get(self.project.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(self.api()).status_code, 404)

    def test_area_filter_returns_only_published_matching_projects(self):
        response = self.client.get('/api/projects/', {'area': self.area.slug})
        self.assertEqual(response.status_code, 200)
        text = response.content.decode()
        self.assertIn(self.project.name, text)
        self.assertNotIn(self.other_project.name, text)
        self.assertNotIn(self.draft.name, text)
        self.assertNotIn(self.archived.name, text)

    def test_visible_plot_search_works_even_when_project_has_hidden_plots(self):
        response = self.client.get('/api/projects/', {'q': 'A-1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.project.name, response.content.decode())
        response = self.client.get('/api/projects/', {'q': 'SECRET-4'})
        self.assertNotIn(self.project.name, response.content.decode())

    def test_changed_project_slug_redirects_and_keeps_private_projects_hidden(self):
        old_path = self.project.get_absolute_url()
        self.project.slug = 'renamed-public-development'
        self.project.save()
        response = self.client.get(old_path)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], self.project.get_absolute_url())
        self.project.status = 'draft'
        self.project.save()
        self.assertEqual(self.client.get(old_path).status_code, 404)

    def test_availability_query_alias_filters_database_status(self):
        other_layout = ProjectLayout.objects.create(project=self.other_project, image='layouts/other.png', width=400, height=300)
        Plot.objects.create(project=self.other_project, layout=other_layout, number='S-1', status='sold', polygon=[[0,0],[20,0],[20,20]])
        response = self.client.get('/api/projects/', {'availability':'available'})
        self.assertEqual({p['slug'] for p in response.json()['projects']}, {self.project.slug})
        response = self.client.get('/api/projects/', {'availability':'sold'})
        self.assertEqual({p['slug'] for p in response.json()['projects']}, {self.project.slug,self.other_project.slug})

    def test_area_range_converts_mixed_units_instead_of_comparing_raw_numbers(self):
        self.plot.area = Decimal('100')
        self.plot.area_unit = 'sqyd'
        self.plot.save()
        feet_layout = ProjectLayout.objects.create(project=self.other_project, image='layouts/feet.png', width=400,height=300)
        Plot.objects.create(project=self.other_project, layout=feet_layout, number='F-1', area=Decimal('900'),area_unit='sqft',polygon=[[0,0],[20,0],[20,20]])
        metre_project = Project.objects.create(area=self.area,name='Metric Development',slug='metric-development',status='published')
        metre_layout = ProjectLayout.objects.create(project=metre_project,image='layouts/metres.png',width=400,height=300)
        Plot.objects.create(project=metre_project,layout=metre_layout,number='M-1',area=Decimal('83.61'),area_unit='sqm',polygon=[[0,0],[20,0],[20,20]])
        expected = {self.project.slug,self.other_project.slug,metre_project.slug}
        for bounds in ({'min_area':'99','max_area':'101'}, {'min_area':'899','max_area':'901','area_unit':'sqft'}, {'min_area':'83.5','max_area':'83.7','area_unit':'sqm'}):
            with self.subTest(bounds=bounds):
                response = self.client.get('/api/projects/',bounds)
                self.assertEqual({p['slug'] for p in response.json()['projects']},expected)
        response = self.client.get('/api/projects/',{'min_area':'110','area_unit':'sqyd'})
        self.assertEqual(response.json()['projects'], [])

    @override_settings(SITE_URL='https://canonical.example',ALLOWED_HOSTS=['untrusted.example','testserver'])
    def test_sitemap_and_robots_use_configured_canonical_domain(self):
        response = self.client.get('/sitemap.xml',HTTP_HOST='untrusted.example')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'https://canonical.example/projects/public-development/')
        self.assertNotContains(response,'untrusted.example')
        self.assertNotContains(response,self.draft.slug)
        self.assertNotContains(response,self.archived.slug)
        response = self.client.get('/robots.txt',HTTP_HOST='untrusted.example')
        self.assertContains(response,'Sitemap: https://canonical.example/sitemap.xml')
        self.assertNotContains(response,'untrusted.example')

    def test_draft_preview_requires_staff_permission_and_prevents_indexing(self):
        path = self.draft.get_absolute_url()+'?preview=1'
        self.assertEqual(self.client.get(path).status_code,404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(path).status_code,404)
        self.client.force_login(self.admin)
        response = self.client.get(path)
        self.assertEqual(response.status_code,200)
        self.assertIn('noindex',response.get('X-Robots-Tag',''))
        self.assertIn('no-store',response.get('Cache-Control',''))

    def test_partial_project_update_does_not_record_an_unwritten_slug_change(self):
        original = self.project.slug
        self.project.slug = 'not-written-to-database'
        self.project.description = 'Description only changed.'
        self.project.save(update_fields=['description'])
        self.project.refresh_from_db()
        self.assertEqual(self.project.slug,original)
        self.assertFalse(ProjectSlugHistory.objects.filter(project=self.project).exists())

    def test_status_counts_derive_from_public_active_layout(self):
        self.assertEqual(self.project.availability, {'total':3,'available':1,'booked':1,'sold':1})
        response = self.client.get(self.api())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['counts'], self.project.availability)

    def test_public_api_hides_private_fields_hidden_and_draft_geometry(self):
        response = self.client.get(self.api())
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual({p['number'] for p in payload['plots']}, {'A-1','A-2','A-3'})
        self.assertNotIn('CONFIDENTIAL SALES NOTE', response.content.decode())
        for plot in payload['plots']:
            self.assertNotIn('internal_remarks', plot)
            self.assertNotIn('staff_notes', plot)
        selected = next(p for p in payload['plots'] if p['number']=='A-1')
        self.assertFalse(selected.get('price'))

    def test_public_price_appears_only_when_staff_publish_it(self):
        self.plot.show_price = True
        self.plot.save()
        payload = self.client.get(self.api()).json()
        selected = next(p for p in payload['plots'] if p['number']=='A-1')
        self.assertEqual(Decimal(str(selected['price'])), Decimal('1000000.00'))

    def test_hidden_plot_share_page_returns_404(self):
        self.assertEqual(self.client.get(self.hidden.get_absolute_url()).status_code, 404)

    def test_plot_share_page_shows_current_database_status(self):
        self.plot.set_status('booked', self.admin)
        response = self.client.get(self.plot.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Booked')

    def test_public_endpoints_reject_mutation(self):
        for path in ('/api/projects/', self.api()):
            response = self.post_json(path, {'status':'sold'})
            self.assertEqual(response.status_code, 405)
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.status, 'available')


class GeometryTests(EstateFixture):
    def test_irregular_polygon_is_stored_without_normalizing_to_a_grid(self):
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.polygon, [[10,10],[100,10],[90,80],[10,70]])
        self.plot.full_clean()

    def test_polygon_rejects_invalid_or_degenerate_coordinates(self):
        invalid = [[], [[0,0],[1,1]], [[0,0],[10,10],[20,20]], [[0,0],[10,-1],[5,8]], [[0,0],[True,10],[10,0]], [[0,0],[float('nan'),10],[10,0]], [[0,0],[float('inf'),10],[10,0]], [[0,0],[0,0],[10,0],[0,10]], [[0,0],[100,80],[0,100],[100,0]], [[0,0],[100,0],[100,100],[50,50],[0,100],[50,50]], [[0,0],[100,0],[100,100],[50,0],[0,100]]]
        for polygon in invalid:
            with self.subTest(polygon=polygon):
                with self.assertRaises(ValidationError):
                    validate_polygon(polygon)

    def test_plot_cannot_exceed_layout_bounds(self):
        self.plot.polygon = [[0,0],[401,0],[300,200]]
        with self.assertRaises(ValidationError):
            self.plot.full_clean()

    def test_plot_cannot_belong_to_another_projects_layout(self):
        self.plot.project = self.other_project
        with self.assertRaises(ValidationError):
            self.plot.full_clean()

    def test_label_position_is_validated(self):
        for position in (-1, 500, float('nan')):
            self.plot.label_x = position
            with self.subTest(position=position), self.assertRaises(ValidationError):
                self.plot.full_clean()

    def test_duplicate_plot_number_cannot_be_created_in_same_layout_block(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Plot.objects.create(project=self.project, layout=self.layout, number='A-1', polygon=[[0,0],[20,0],[20,20]])

    def test_same_number_can_exist_in_new_revision(self):
        plot = Plot.objects.create(project=self.project, layout=self.draft_layout, number='A-1', polygon=[[0,0],[20,0],[20,20]])
        self.assertNotEqual(plot.pk, self.plot.pk)

    def test_area_conversion_uses_correct_units(self):
        self.plot.area = Decimal('150')
        self.plot.area_unit = 'sqyd'
        self.assertEqual(self.plot.area_sqft, Decimal('1350'))
        self.plot.area_unit = 'sqm'
        self.assertAlmostEqual(self.plot.area_sqft, Decimal('1614.586562505'), places=6)

    def test_image_replacement_cannot_silently_break_existing_geometry(self):
        self.layout.image = raster('different-plan.png')
        with self.assertRaises(ValidationError):
            self.layout.save()


class StaffAvailabilityTests(EstateFixture):
    def test_model_status_change_requires_authorized_staff(self):
        for user in (None, self.staff):
            with self.subTest(user=user), self.assertRaises(PermissionDenied):
                self.plot.set_status('sold', user)
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.status, 'available')

    def test_status_persists_updates_totals_and_records_actor(self):
        self.plot.set_status('booked', self.admin, 'Confirmed by sales team')
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.status, 'booked')
        history = PlotStatusHistory.objects.get(plot=self.plot)
        self.assertEqual((history.previous_status,history.new_status,history.user_id), ('available','booked',self.admin.pk))
        self.assertEqual(history.note, 'Confirmed by sales team')
        self.assertEqual(self.project.availability, {'total':3,'available':0,'booked':2,'sold':1})
        record = next(p for p in self.client.get(self.api()).json()['plots'] if p['number']=='A-1')
        self.assertEqual(record['status'], 'booked')

    def test_partial_plot_update_does_not_audit_an_unwritten_status_change(self):
        self.plot.status = 'sold'
        self.plot.description = 'Description only changed.'
        self.plot.save(update_fields=['description'])
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.status,'available')
        self.assertFalse(self.plot.status_history.exists())

    def test_unchanged_status_does_not_create_fake_history(self):
        self.plot.set_status('available', self.admin)
        self.assertFalse(PlotStatusHistory.objects.filter(plot=self.plot).exists())

    def test_sold_transition_updates_totals_and_appends_history(self):
        self.plot.set_status('booked', self.admin)
        self.plot.set_status('sold', self.admin)
        self.assertEqual(self.project.availability, {'total':3,'available':0,'booked':1,'sold':2})
        self.assertEqual(self.plot.status_history.count(), 2)
        self.assertEqual(self.plot.status_history.first().previous_status, 'booked')

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.plot.set_status('invented', self.admin)

    def test_anonymous_and_unprivileged_staff_cannot_write_layout(self):
        payload = {'action':'bulk','ids':[self.plot.pk],'status':'sold'}
        self.assertIn(self.post_json(self.editor_api(), payload).status_code, (302,403))
        self.client.force_login(self.staff)
        self.assertEqual(self.post_json(self.editor_api(), payload).status_code, 403)
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.status, 'available')

    def test_editor_page_requires_staff_authorization(self):
        path = f'/admin/estate/projectlayout/{self.layout.pk}/editor/'
        self.assertIn(self.client.get(path).status_code, (302,403))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(path).status_code, 403)

    def test_authenticated_admin_still_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        response = self.post_json(self.editor_api(), {'action':'bulk','ids':[self.plot.pk],'status':'sold'}, csrf_client)
        self.assertEqual(response.status_code, 403)
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.status, 'available')

    def test_staff_can_create_polygon_and_update_availability(self):
        self.client.force_login(self.admin)
        response = self.post_json(self.editor_api(), {'action':'save','plot':{'number':'B-9','status':'available','polygon':[[10,200],[100,200],[95,290],[10,280]],'area':'90','area_unit':'sqyd','label_position':[50,240]}})
        self.assertIn(response.status_code, (200,201), response.content)
        new_plot = Plot.objects.get(layout=self.layout, number='B-9')
        self.assertEqual(new_plot.area, Decimal('90'))
        response = self.post_json(self.editor_api(), {'action':'bulk','ids':[new_plot.pk],'status':'booked'})
        self.assertEqual(response.status_code, 200, response.content)
        new_plot.refresh_from_db()
        self.assertEqual(new_plot.status, 'booked')
        self.assertEqual(new_plot.status_history.get().user_id, self.admin.pk)

    def test_staff_api_rejects_geometry_outside_image(self):
        self.client.force_login(self.admin)
        response = self.post_json(self.editor_api(), {'action':'save','plot':{'number':'BAD','status':'available','polygon':[[0,0],[9999,0],[9999,500]]}})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Plot.objects.filter(number='BAD').exists())

    def test_staff_api_rejects_cross_layout_record_ids(self):
        self.client.force_login(self.admin)
        response = self.post_json(self.editor_api(), {'action':'delete','id':self.revision_plot.pk})
        self.assertIn(response.status_code, (400,404))
        self.assertTrue(Plot.objects.filter(pk=self.revision_plot.pk).exists())


class LeadTests(EstateFixture):
    def payload(self, **overrides):
        values = {'name':'Test Visitor','phone':'+91 9876543210','email':'visitor@example.com','message':'Please send information.','kind':'general','consent':True,'website':''}
        values.update(overrides)
        return values

    def test_valid_enquiry_saves_without_changing_availability(self):
        response = self.post_json('/api/enquiries/', self.payload(project=self.project.slug, plot=self.plot.number, kind='plot'))
        self.assertIn(response.status_code, (200,201), response.content)
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.project_id, self.project.pk)
        self.assertEqual(enquiry.plot_id, self.plot.pk)
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.status, 'available')

    def test_invalid_phone_and_missing_consent_do_not_save(self):
        for overrides in ({'phone':'12'},{'consent':False},{'name':'x'}):
            with self.subTest(overrides=overrides):
                response = self.post_json('/api/enquiries/', self.payload(**overrides))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_site_visit_requires_date_and_saves_preferred_date(self):
        response = self.post_json('/api/enquiries/', self.payload(kind='site_visit'))
        self.assertEqual(response.status_code, 400)
        visit_date = timezone.localdate() + timedelta(days=2)
        response = self.post_json('/api/enquiries/', self.payload(kind='site_visit',visit_date=visit_date.isoformat()))
        self.assertIn(response.status_code, (200,201), response.content)
        self.assertEqual(Enquiry.objects.get().preferred_date, visit_date)

    def test_past_site_visit_date_is_rejected(self):
        response = self.post_json('/api/enquiries/', self.payload(kind='site_visit',visit_date=(timezone.localdate()-timedelta(days=1)).isoformat()))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Enquiry.objects.exists())

    def test_private_project_and_cross_project_plot_are_rejected(self):
        for project,plot in ((self.draft.slug,None),(self.other_project.slug,self.plot.number)):
            response = self.post_json('/api/enquiries/', self.payload(project=project,plot=plot))
            self.assertIn(response.status_code, (400,404))
        self.assertFalse(Enquiry.objects.exists())

    def test_honeypot_cannot_create_a_lead(self):
        response = self.post_json('/api/enquiries/', self.payload(website='https://spam.example.com'))
        self.assertIn(response.status_code, (200,400))
        self.assertFalse(Enquiry.objects.exists())

    def test_enquiry_form_requires_plot_project_consistency(self):
        form = EnquiryForm(data=self.payload(project=self.other_project.pk,plot=self.plot.pk))
        self.assertFalse(form.is_valid())
        self.assertIn('plot', form.errors)


class GalleryTestimonialTests(EstateFixture):
    def test_gallery_filters_hide_private_and_unpublished_images(self):
        category = GalleryCategory.objects.create(name='Infrastructure',slug='infrastructure')
        ProjectImage.objects.create(project=self.project, category=category, image='gallery/public.png', alt_text='PUBLIC GALLERY CAPTION',caption='PUBLIC GALLERY CAPTION')
        ProjectImage.objects.create(project=self.project, image='gallery/hidden.png', alt_text='UNPUBLISHED GALLERY CAPTION',published=False)
        ProjectImage.objects.create(project=self.draft, image='gallery/draft.png', alt_text='DRAFT GALLERY CAPTION')
        ProjectImage.objects.create(project=self.other_project,image='gallery/other.png',alt_text='OTHER AREA GALLERY CAPTION')
        response = self.client.get('/gallery/', {'project':self.project.slug,'category':category.slug})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'PUBLIC GALLERY CAPTION')
        self.assertNotContains(response,'UNPUBLISHED GALLERY CAPTION')
        self.assertNotContains(response,'DRAFT GALLERY CAPTION')
        self.assertNotContains(response,'OTHER AREA GALLERY CAPTION')

    def test_only_approved_testimonials_are_public(self):
        Testimonial.objects.create(name='Approved Test Person',quote='VERIFIED TEST QUOTE',published=True,consent_confirmed=True)
        Testimonial.objects.create(name='Private Test Person',quote='PRIVATE TEST QUOTE',published=False)
        response = self.client.get('/testimonials/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'VERIFIED TEST QUOTE')
        self.assertNotContains(response,'PRIVATE TEST QUOTE')

    def test_published_testimonial_requires_consent(self):
        with self.assertRaises(ValidationError):
            Testimonial(name='No Consent',quote='Not approved',published=True,consent_confirmed=False).full_clean()


class UploadAndConfigurationTests(TestCase):
    def test_valid_raster_and_pdf_header_are_accepted(self):
        validate_image(raster())
        output = io.BytesIO()
        Image.new('RGB', (20,20), 'white').save(output, 'PDF')
        validate_pdf(SimpleUploadedFile('brochure.pdf',output.getvalue(),content_type='application/pdf'))

    def test_svg_and_fake_image_are_rejected(self):
        for upload in (SimpleUploadedFile('unsafe.svg',b'<svg><script>alert(1)</script></svg>'),SimpleUploadedFile('fake.png',b'not an image')):
            with self.subTest(name=upload.name), self.assertRaises(ValidationError):
                validate_image(upload)

    def test_mismatched_document_type_is_rejected(self):
        for upload in (SimpleUploadedFile('fake.pdf',b'<html>not pdf</html>'),SimpleUploadedFile('script.html',b'%PDF-1.4')):
            with self.subTest(name=upload.name), self.assertRaises(ValidationError):
                validate_pdf(upload)

    def test_pdf_prefix_without_a_document_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_pdf(SimpleUploadedFile('junk.pdf', b'%PDF-1.7\nnot a real PDF'))

    def test_pdf_active_content_attachments_and_encryption_are_rejected(self):
        for dangerous_feature in ('script','attachment','encryption'):
            writer = PdfWriter()
            writer.add_blank_page(width=100,height=100)
            if dangerous_feature == 'script':
                writer.add_open_action(JavaScript('app.alert("unsafe");'))
            elif dangerous_feature == 'attachment':
                writer.add_attachment('payload.txt', b'embedded document')
            else:
                writer.encrypt('test-password')
            output = io.BytesIO()
            writer.write(output)
            with self.subTest(feature=dangerous_feature), self.assertRaises(ValidationError):
                validate_pdf(SimpleUploadedFile('active.pdf', output.getvalue()))

    def test_maps_rejects_unsafe_or_unrelated_destinations(self):
        validate_maps_url('https://www.google.com/maps?q=Ghaziabad')
        for url in ('javascript:alert(1)','http://www.google.com/maps','https://evil.example.com/maps','https://google.com.evil.example.com/maps'):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                validate_maps_url(url)

    def test_static_and_media_are_separate_public_roots(self):
        self.assertEqual(settings.STATIC_URL,'/static/')
        self.assertEqual(settings.MEDIA_URL,'/media/')
        self.assertNotEqual(Path(settings.STATIC_ROOT),Path(settings.MEDIA_ROOT))
        self.assertNotEqual(Path(settings.MEDIA_ROOT),Path(settings.BASE_DIR))

    @override_settings(DEBUG=False,SECURE_SSL_REDIRECT=False)
    def test_production_does_not_use_development_media_or_expose_unknown_files(self):
        response = self.client.get('/media/.env')
        self.assertEqual(response.status_code,404)
