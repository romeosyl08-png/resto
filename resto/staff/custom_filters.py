# staff/templatetags/custom_filters.py
# Créer ce fichier dans staff/templatetags/custom_filters.py

from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiplie deux nombres"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """Soustrait deux nombres"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add_filter(value, arg):
    """Additionne deux nombres"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0
