from django import template

from ..services.alertas import categorias_disponibles


register = template.Library()
register.simple_tag(categorias_disponibles)
