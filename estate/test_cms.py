from django.test import TestCase
from django.utils.safestring import mark_safe
from .models import HomepageSection
from .templatetags.cms import editorial_title, homepage_sections


class HomepageCMSTests(TestCase):
    def test_staff_content_controls_homepage_and_disabled_sections_stay_hidden(self):
        HomepageSection.objects.create(key='intro', title='An editable introduction', body='A real company message.', display_order=20)
        HomepageSection.objects.create(key='contact', title='Speak with us', body='Personal guidance.', display_order=10)
        HomepageSection.objects.create(key='approach', title='Hidden heading', enabled=False)
        response = self.client.get('/')
        self.assertContains(response, 'A real company message.')
        self.assertContains(response, 'Personal guidance.')
        self.assertNotContains(response, 'Hidden heading')
        html = response.content.decode()
        self.assertLess(html.index('Personal guidance.'), html.index('A real company message.'))

    def test_unknown_section_keys_cannot_select_templates(self):
        HomepageSection.objects.create(key='unknown-section', title='Unavailable')
        self.assertEqual(homepage_sections(), [])

    def test_editorial_markup_cannot_inject_active_html(self):
        output = str(editorial_title(mark_safe('<img src=x onerror=alert(1)>\n<script>alert(1)</script>')))
        self.assertNotIn('<img', output)
        self.assertNotIn('<script', output)
        self.assertIn('&lt;script&gt;', output)
        self.assertIn('<em>', output)
        title = str(editorial_title('One\nTwo\nThree'))
        self.assertIn('One<br>Two<br><em>Three</em>', title)
