from django import template

from ..formato_clp import formatear_clp

register = template.Library()
register.filter('clp', formatear_clp)
