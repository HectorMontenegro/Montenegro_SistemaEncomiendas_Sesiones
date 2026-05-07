# envios/templatetags/envios_extras.py
from django import template

register = template.Library()

@register.filter
def cut(value, arg):
    """Remueve todas las ocurrencias de arg de value"""
    return value.replace(arg, '')