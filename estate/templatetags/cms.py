"""Safely ordered homepage sections controlled through the Django admin."""
from types import SimpleNamespace
from django import template
from django.utils.html import escape, format_html, format_html_join
from estate.models import HomepageSection

register = template.Library()

# Keys map only to application-owned templates. A database key cannot select an
# arbitrary template or escape the homepage template directory.
DEFAULT_HOMEPAGE_SECTIONS = (
    {
        'key': 'intro',
        'title': 'More than a plot.\nA place to belong.',
        'body': 'Every new chapter begins with the right foundation. We help you explore residential spaces with clarity, care, and a personal approach — from your first question to your site visit.',
    },
    {
        'key': 'projects',
        'title': 'Find your next address.',
        'body': 'Explore thoughtfully presented residential developments and find the details that matter to you.',
    },
    {
        'key': 'locations',
        'title': 'A location to call your own.',
        'body': 'Explore by neighbourhood. Discover the setting for your next chapter.',
    },
    {
        'key': 'layout',
        'title': 'Your plot.\nYour perspective.\nYour decision.',
        'body': 'Get a closer look at the community. Explore the society plan, select individual plots, and understand the details that matter to you.',
    },
    {
        'key': 'approach',
        'title': 'Good foundations.\nLasting relationships.',
        'body': 'Buying land is a personal decision. We believe the experience should feel just as personal.',
    },
    {
        'key': 'gallery',
        'title': 'See the possibilities.',
        'body': 'Take a closer look through the project gallery. Illustrative brochure imagery is identified in its captions.',
    },
    {
        'key': 'testimonials',
        'title': 'In our customers’ words.',
        'body': 'Personal experiences shared with permission.',
    },
    {
        'key': 'visit',
        'title': 'The best way to picture your future?\nCome see it for yourself.',
        'body': 'Walk the location. Ask your questions. Let our team help you imagine what comes next.',
    },
    {
        'key': 'contact',
        'title': 'Your future starts with a conversation.',
        'body': 'Tell us what you have in mind. Our team is here to help you explore your next step.',
    },
)

SECTION_TEMPLATES = {
    section['key']: f"estate/home/{section['key']}.html"
    for section in DEFAULT_HOMEPAGE_SECTIONS
}


@register.simple_tag
def homepage_sections():
    """Return enabled sections in administrator-selected order.

    Fresh unseeded databases use the same safe defaults. Once any section is
    configured, absence or disabled status is respected rather than restoring
    it from defaults. Unknown keys are ignored.
    """
    sections = list(HomepageSection.objects.order_by('display_order', 'pk'))
    if not sections:
        return [SimpleNamespace(**section, template=SECTION_TEMPLATES[section['key']])
                for section in DEFAULT_HOMEPAGE_SECTIONS]
    return [SimpleNamespace(key=section.key, title=section.title, body=section.body,
                            template=SECTION_TEMPLATES[section.key])
            for section in sections
            if section.enabled and section.key in SECTION_TEMPLATES]


@register.filter
def editorial_title(value):
    """Escape CMS text while adding application-owned editorial emphasis."""
    lines = str(value or '').splitlines()
    if len(lines) > 1:
        prefix = format_html_join(format_html('<br>{}', ''), '{}', ((escape(line),) for line in lines[:-1]))
        return format_html('{}<br><em>{}</em>', prefix, escape(lines[-1]))
    words = (lines[0] if lines else '').split()
    prefix = ' '.join(words[:-2])
    emphasis = ' '.join(words[-2:])
    return format_html('{}{}<em>{}</em>', escape(prefix), ' ' if prefix else '', escape(emphasis))
