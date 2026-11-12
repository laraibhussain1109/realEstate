from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from django import template

register = template.Library()


@register.filter
def area_label(unit):
    return {'sqyd': 'sq. yd.', 'sqft': 'sq. ft.', 'sqm': 'sq. m.'}.get(unit, unit)


@register.filter
def indian_number(value):
    try:
        parts = f'{Decimal(value):.0f}'
    except (InvalidOperation, TypeError, ValueError):
        return value
    if len(parts) <= 3:
        return parts
    left, right = parts[:-3], parts[-3:]
    groups = []
    while left:
        groups.insert(0, left[-2:])
        left = left[:-2]
    return ','.join(groups + [right])


@register.simple_tag(takes_context=True)
def query_string(context, **kwargs):
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value
    return '?' + query.urlencode()
