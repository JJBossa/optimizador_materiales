"""Reglas del catálogo de materiales, con dimensiones almacenadas en cm."""

from django.core.exceptions import ValidationError

from .models import Material


def dimension_material_valida(cm):
    return 10 <= cm <= 300


def validar_precio_material(precio):
    if precio is not None:
        Material._meta.get_field('precio').run_validators(precio)
        if precio < 0:
            raise ValidationError('El precio no puede ser negativo.', code='min_value')


def precio_material_valido(precio):
    try:
        validar_precio_material(precio)
    except ValidationError:
        return False
    return True
