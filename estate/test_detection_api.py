"""Real-image integration and access-control tests for boundary suggestions.

Computer vision output is a preview; only an explicit, authorized import may
create inventory. These tests use a generated plan image, not a detector mock.
"""
import io
import json
import tempfile

from PIL import Image, ImageDraw
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .models import Area, City, Plot, PlotStatusHistory, Project, ProjectLayout, State
from .validators import validate_polygon


def synthetic_plan():
    image = Image.new('RGB', (320, 240), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((20,20,100,100), fill='#16a34a', outline='black', width=3)
    draw.rectangle((130,20,220,100), fill='#facc15', outline='black', width=3)
    draw.polygon([(20,130),(100,130),(85,210),(20,210)], fill='#dc2626', outline='black', width=3)
    output = io.BytesIO()
    image.save(output, 'PNG')
    return SimpleUploadedFile('synthetic-plan.png', output.getvalue(), content_type='image/png')


class DetectionApiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory(prefix='plotmatrix-detection-tests-')
        cls.media_override = override_settings(MEDIA_ROOT=cls.media.name)
        cls.media_override.enable()
        try:
            super().setUpClass()
        except Exception:
            cls.media_override.disable()
            cls.media.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            super().tearDownClass()
        finally:
            cls.media_override.disable()
            cls.media.cleanup()

    @classmethod
    def setUpTestData(cls):
        state = State.objects.create(name='Detection Test State')
        city = City.objects.create(state=state,name='Detection Test City')
        area = Area.objects.create(city=city,name='Detection Test Area',slug='detection-area')
        cls.project = Project.objects.create(area=area,name='Detection Test Development',slug='detection-development',status='published')
        cls.layout = ProjectLayout.objects.create(project=cls.project,image=synthetic_plan(),active=True,is_draft=False)
        cls.draft_layout = ProjectLayout.objects.create(project=cls.project,image=synthetic_plan(),revision=2,active=False,is_draft=True)
        cls.admin = get_user_model().objects.create_superuser('detection-admin','admin@example.invalid','test-only-password')
        cls.staff = get_user_model().objects.create_user('detection-staff',password='test-only-password',is_staff=True)
        cls.add_only = get_user_model().objects.create_user('detection-add-only',is_staff=True)
        cls.add_only.user_permissions.add(Permission.objects.get(codename='add_plot',content_type__app_label='estate'))
        cls.change_only = get_user_model().objects.create_user('detection-change-only',is_staff=True)
        cls.change_only.user_permissions.add(Permission.objects.get(codename='change_plot',content_type__app_label='estate'))

    def endpoint(self,layout=None):
        return f'/api/layouts/{(layout or self.layout).pk}/detect/'

    def post(self,payload,client=None,layout=None):
        target = layout or self.layout
        client = client or self.client
        payload = payload.copy()
        if payload.get('action') in ('detect','point'):
            payload.setdefault('options',{'ocr':False})
        if payload.get('action') == 'import' and 'layout_signature' not in payload:
            signatures = getattr(self,'_signatures',{})
            if target.pk not in signatures:
                preview = client.post(self.endpoint(target),data=json.dumps({'action':'detect','options':{'ocr':False}}),content_type='application/json')
                if preview.status_code == 200:
                    signatures[target.pk] = preview.json()['layout_signature']
            if target.pk in signatures:
                payload['layout_signature'] = signatures[target.pk]
            self._signatures = signatures
        return client.post(self.endpoint(target),data=json.dumps(payload),content_type='application/json')

    def candidate(self,number='R-1',status='blocked',polygon=None,**extra):
        return {'number':number,'status':status,'polygon':polygon or [[20,20],[100,20],[100,100],[20,100]],**extra}

    def login(self):
        self.client.force_login(self.admin)

    def existing_plot(self):
        return Plot.objects.create(project=self.project,layout=self.layout,number='EXISTING',status='sold',polygon=[[240,150],[300,150],[300,220],[240,220]],internal_remarks='Private existing record')

    def test_anonymous_and_staff_without_both_permissions_cannot_detect_or_import(self):
        for user in (None,self.staff,self.add_only,self.change_only):
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            for action in ('detect','point','import'):
                payload = {'action':action,'x':50,'y':50,'candidates':[self.candidate()]}
                with self.subTest(user=user,action=action):
                    self.assertIn(self.post(payload).status_code,(302,403))
        self.assertFalse(Plot.objects.exists())

    def test_inactive_staff_cannot_access_detection(self):
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        self.client.force_login(self.admin)
        self.assertIn(self.post({'action':'detect'}).status_code,(302,403))

    def test_detection_and_import_require_post_and_csrf(self):
        self.login()
        self.assertEqual(self.client.get(self.endpoint()).status_code,405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        for action in ('detect','import'):
            with self.subTest(action=action):
                self.assertEqual(self.post({'action':action,'candidates':[self.candidate()]},client=csrf_client).status_code,403)
        self.assertFalse(Plot.objects.exists())

    def test_detect_returns_real_candidates_without_creating_public_inventory(self):
        self.login()
        response = self.post({'action':'detect'})
        self.assertEqual(response.status_code,200,response.content)
        candidates = response.json()['candidates']
        self.assertGreater(len(candidates),0)
        for candidate in candidates:
            validate_polygon(candidate['polygon'])
            self.assertTrue(all(0 <= x <= self.layout.width and 0 <= y <= self.layout.height for x,y in candidate['polygon']))
        self.assertFalse(Plot.objects.exists())
        self.assertFalse(PlotStatusHistory.objects.exists())
        public = self.client.get(f'/api/projects/{self.project.slug}/plots/').json()
        self.assertEqual(public['plots'],[])
        self.assertEqual(public['counts']['total'],0)

    def test_detect_leaves_existing_geometry_status_and_private_notes_unchanged(self):
        existing = self.existing_plot()
        before = {field:getattr(existing,field) for field in ('number','polygon','status','internal_remarks','updated_at')}
        self.login()
        response = self.post({'action':'detect'})
        self.assertEqual(response.status_code,200,response.content)
        existing.refresh_from_db()
        self.assertEqual(Plot.objects.count(),1)
        self.assertEqual({field:getattr(existing,field) for field in before},before)
        self.assertFalse(existing.status_history.exists())

    def test_staff_can_preview_draft_layout_without_exposing_it_publicly(self):
        self.login()
        response = self.post({'action':'detect'},layout=self.draft_layout)
        self.assertEqual(response.status_code,200,response.content)
        self.assertGreater(len(response.json()['candidates']),0)
        response = self.post({'action':'import','candidates':[self.candidate()]},layout=self.draft_layout)
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(Plot.objects.filter(layout=self.draft_layout).count(),1)
        self.assertEqual(self.client.get(f'/api/projects/{self.project.slug}/plots/').json()['plots'],[])

    def test_point_returns_boundary_suggestion_without_writing(self):
        self.login()
        response = self.post({'action':'point','x':50,'y':50})
        self.assertEqual(response.status_code,200,response.content)
        payload = response.json()
        candidate = payload.get('candidate') or payload.get('candidates',[None])[0]
        self.assertIsNotNone(candidate)
        validate_polygon(candidate['polygon'])
        self.assertFalse(Plot.objects.exists())
        self.assertFalse(PlotStatusHistory.objects.exists())

    def test_import_creates_validated_records_with_explicit_status_only(self):
        self.login()
        response = self.post({'action':'import','candidates':[self.candidate(status='booked')]})
        self.assertEqual(response.status_code,201,response.content)
        created = Plot.objects.get(number='R-1')
        self.assertEqual(created.status,'booked')
        self.assertEqual(created.layout_id,self.layout.pk)
        self.assertEqual(created.project_id,self.project.pk)
        audit = created.status_history.get()
        self.assertEqual((audit.previous_status,audit.new_status,audit.user_id),('new','booked',self.admin.pk))
        self.assertTrue(audit.note)
        public = self.client.get(f'/api/projects/{self.project.slug}/plots/').json()
        self.assertEqual(public['plots'][0]['status'],'booked')
        self.assertEqual(public['counts']['booked'],1)

    def test_import_cannot_update_existing_ids_or_inject_private_remarks(self):
        existing = self.existing_plot()
        self.login()
        response = self.post({'action':'import','candidates':[self.candidate(id=existing.pk,project=self.project.pk,layout=self.draft_layout.pk,internal_remarks='Injected note')]})
        self.assertEqual(response.status_code,400,response.content)
        existing.refresh_from_db()
        self.assertEqual(existing.number,'EXISTING')
        self.assertEqual(existing.status,'sold')
        self.assertEqual(existing.internal_remarks,'Private existing record')
        self.assertEqual(Plot.objects.count(),1)

    def test_duplicate_number_import_is_atomic(self):
        self.login()
        first = self.candidate(number='DUP')
        second = self.candidate(number='DUP',polygon=[[130,20],[220,20],[220,100],[130,100]])
        response = self.post({'action':'import','candidates':[first,second]})
        self.assertEqual(response.status_code,400,response.content)
        self.assertFalse(Plot.objects.exists())

    def test_existing_number_import_is_atomic_and_preserves_inventory(self):
        existing = self.existing_plot()
        self.login()
        response = self.post({'action':'import','candidates':[self.candidate(number='NEW'),self.candidate(number=existing.number,polygon=[[130,20],[220,20],[220,100],[130,100]])]})
        self.assertEqual(response.status_code,400,response.content)
        self.assertEqual(Plot.objects.count(),1)
        existing.refresh_from_db()
        self.assertEqual(existing.status,'sold')

    def test_invalid_geometry_aborts_entire_import(self):
        self.login()
        for polygon in ([[0,0],[9999,0],[10,30]],[[10,10],[20,20]],[[0,0],[100,80],[0,100],[100,0]],[[0,0],[True,80],[100,100]]):
            with self.subTest(polygon=polygon):
                response = self.post({'action':'import','candidates':[self.candidate(number='VALID'),self.candidate(number='INVALID',polygon=polygon)]})
                self.assertEqual(response.status_code,400,response.content)
                self.assertFalse(Plot.objects.exists())

    def test_import_rejects_missing_or_unsupported_status(self):
        self.login()
        for status in (None,'hidden','invented',''):
            item = self.candidate(status=status)
            if status is None:
                item.pop('status')
            with self.subTest(status=status):
                response = self.post({'action':'import','candidates':[item]})
                self.assertEqual(response.status_code,400,response.content)
                self.assertFalse(Plot.objects.exists())

    def test_import_rejects_blank_or_overlong_numbers_without_truncation(self):
        self.login()
        for number in ('','   ','N'*31):
            with self.subTest(number=number):
                response = self.post({'action':'import','candidates':[self.candidate(number=number)]})
                self.assertEqual(response.status_code,400,response.content)
                self.assertFalse(Plot.objects.exists())

    def test_separate_point_suggestions_have_distinct_region_keys(self):
        self.login()
        first = self.post({'action':'point','x':50,'y':50})
        second = self.post({'action':'point','x':170,'y':50})
        self.assertEqual(first.status_code,200,first.content)
        self.assertEqual(second.status_code,200,second.content)
        first_candidate = first.json()['candidates'][0]
        second_candidate = second.json()['candidates'][0]
        self.assertNotEqual(first_candidate['polygon'],second_candidate['polygon'])
        self.assertNotEqual(first_candidate['key'],second_candidate['key'])
        self.assertFalse(Plot.objects.exists())

    def test_region_key_is_stable_between_scan_and_single_region_review(self):
        from .detection_views import _review_result
        first = [[20,20],[100,20],[100,100],[20,100]]
        second = [[130,20],[220,20],[220,100],[130,100]]
        scan = _review_result(self.layout,{'candidates':[{'polygon':first},{'polygon':second}]})
        # A contour can start at a different corner or use opposite winding.
        same_region = list(reversed(second[1:]+second[:1]))
        point = _review_result(self.layout,{'candidates':[{'polygon':same_region}]})
        self.assertEqual(scan['candidates'][1]['key'],point['candidates'][0]['key'])
        self.assertNotEqual(scan['candidates'][0]['key'],point['candidates'][0]['key'])

    def test_import_rejects_ten_percent_interior_overlap_atomically(self):
        self.login()
        first = self.candidate(number='FIRST',polygon=[[10,10],[110,10],[110,110],[10,110]])
        second = self.candidate(number='OVERLAPPING',polygon=[[100,10],[200,10],[200,110],[100,110]])
        response = self.post({'action':'import','candidates':[first,second]})
        self.assertEqual(response.status_code,400,response.content)
        self.assertFalse(Plot.objects.exists())
        self.assertFalse(PlotStatusHistory.objects.exists())

    def test_import_allows_adjacent_plots_sharing_a_vertical_edge(self):
        self.login()
        first = self.candidate(number='FIRST',polygon=[[10,10],[110,10],[110,110],[10,110]])
        second = self.candidate(number='NEIGHBOUR',polygon=[[110,10],[210,10],[210,110],[110,110]])
        response = self.post({'action':'import','candidates':[first,second]})
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(Plot.objects.count(),2)

    def test_import_allows_adjacent_irregular_plots_sharing_a_diagonal(self):
        self.login()
        first = self.candidate(number='FIRST',polygon=[[10,10],[110,10],[110,110]])
        second = self.candidate(number='NEIGHBOUR',polygon=[[10,10],[110,110],[10,110]])
        response = self.post({'action':'import','candidates':[first,second]})
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(Plot.objects.count(),2)

    def test_import_rejects_existing_geometry_overlap(self):
        existing = self.existing_plot()
        self.login()
        response = self.post({'action':'import','candidates':[self.candidate(number='OVERLAP',polygon=existing.polygon)]})
        self.assertEqual(response.status_code,400,response.content)
        self.assertEqual(Plot.objects.count(),1)

    def test_import_enforces_batch_size_and_json_shape(self):
        self.login()
        for candidates in ([],{},'bad',[self.candidate(number=str(i)) for i in range(251)]):
            with self.subTest(kind=type(candidates).__name__,length=len(candidates)):
                response = self.post({'action':'import','candidates':candidates})
                self.assertEqual(response.status_code,400,response.content)
                self.assertFalse(Plot.objects.exists())
        response = self.client.post(self.endpoint(),data='not json',content_type='application/json')
        self.assertEqual(response.status_code,400)

    def test_import_requires_layout_signature_from_current_preview(self):
        self.login()
        response = self.client.post(self.endpoint(),data=json.dumps({'action':'import','candidates':[self.candidate()]}),content_type='application/json')
        self.assertIn(response.status_code,(400,409))
        response = self.post({'action':'import','layout_signature':'stale-source-image','candidates':[self.candidate()]})
        self.assertEqual(response.status_code,409,response.content)
        self.assertFalse(Plot.objects.exists())

    def test_import_rejects_preview_after_source_image_changes(self):
        self.login()
        preview = self.post({'action':'detect'}).json()
        image = Image.new('RGB',(320,240),'white')
        ImageDraw.Draw(image).rectangle((35,35,160,130),fill='blue',outline='black',width=3)
        output = io.BytesIO()
        image.save(output,'PNG')
        self.layout.image = SimpleUploadedFile('changed-plan.png',output.getvalue(),content_type='image/png')
        self.layout.save()
        response = self.post({'action':'import','layout_signature':preview['layout_signature'],'candidates':[self.candidate()]})
        self.assertEqual(response.status_code,409,response.content)
        self.assertFalse(Plot.objects.exists())

    def test_point_rejects_nonfinite_or_outside_image_coordinates(self):
        self.login()
        for x,y in ((-1,10),(321,10),(10,241),(float('nan'),10),('invalid',10),(True,10)):
            with self.subTest(x=x,y=y):
                response = self.post({'action':'point','x':x,'y':y})
                self.assertEqual(response.status_code,400,response.content)
                self.assertFalse(Plot.objects.exists())
