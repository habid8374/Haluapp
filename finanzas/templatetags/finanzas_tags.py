from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def format_thousands(value):
    try:
        if isinstance(value, (int, float, Decimal)):
            return f"{value:,.2f}"
        return value
    except (TypeError, ValueError):
        return value