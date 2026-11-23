import math
import re
from decimal import Decimal

from django import forms

from ..models import Material
from ..units import convertir_a_cm, convertir_desde_cm


_AGRUPACION_AMBIGUA = r'[+\-]?0*[1-9][0-9]{0,2}[.,][0-9]{3}'
_FORMATO_DECIMAL = rf'(?!{_AGRUPACION_AMBIGUA}$)[+\-]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)'
_AYUDA_DECIMAL = 'Usa coma o punto decimal, sin separadores de miles.'
_AYUDA_DIMENSION = f'{_AYUDA_DECIMAL} Para tres decimales ambiguos, añade un cero final (ej.: 12,3450).'


class DecimalMaterialField(forms.DecimalField):
    def prepare_value(self, value):
        # Los datos iniciales son números y ya tienen un significado conocido.
        if isinstance(value, (float, Decimal)) and re.fullmatch(_AGRUPACION_AMBIGUA, str(value)):
            return f'{value}0'
        return super().prepare_value(value)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        texto = str(self.prepare_value(value))
        if not re.fullmatch(_FORMATO_DECIMAL, texto):
            raise forms.ValidationError(f'Escribe un número válido. {_AYUDA_DECIMAL}', code='invalid')
        return super().to_python(texto.replace(',', '.'))


class MaterialForm(forms.ModelForm):
    """Formulario para crear y editar materiales"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            unidad = self.instance.unidad_medida or 'cm'
            self.initial['ancho'] = convertir_desde_cm(self.instance.ancho, unidad)
            self.initial['alto'] = convertir_desde_cm(self.instance.alto, unidad)

    class Meta:
        model = Material
        fields = ['nombre', 'ancho', 'alto', 'unidad_medida', 'precio', 'descripcion']
        field_classes = dict.fromkeys(('ancho', 'alto', 'precio'), DecimalMaterialField)
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: MDF 18mm, Contrachapado'
            }),
            'ancho': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'decimal',
                                            'pattern': _FORMATO_DECIMAL, 'title': _AYUDA_DIMENSION}),
            'alto': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'decimal',
                                           'pattern': _FORMATO_DECIMAL, 'title': _AYUDA_DIMENSION}),
            'unidad_medida': forms.Select(attrs={
                'class': 'form-select'
            }),
            'precio': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'decimal',
                                             'pattern': _FORMATO_DECIMAL, 'title': _AYUDA_DECIMAL,
                                             'placeholder': 'Opcional'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción opcional del material'
            }),
        }
        labels = {
            'nombre': 'Nombre del Material',
            'ancho': 'Ancho',
            'alto': 'Alto',
            'unidad_medida': 'Unidad de Medida',
            'precio': 'Precio por Tablero',
            'descripcion': 'Descripción',
        }
        help_texts = {
            'ancho': _AYUDA_DIMENSION,
            'alto': _AYUDA_DIMENSION,
            'precio': f'Precio en pesos chilenos (opcional). Hasta dos decimales. {_AYUDA_DECIMAL}',
        }
    
    def clean(self):
        datos = super().clean()
        unidad = datos.get('unidad_medida')
        for campo in ('ancho', 'alto'):
            valor = datos.get(campo)
            if valor is not None:
                valor = float(valor)
                if not math.isfinite(valor) or valor <= 0:
                    self.add_error(campo, 'La medida debe ser un número mayor que cero.')
                elif unidad:
                    medida = convertir_a_cm(valor, unidad)
                    if not 10 <= medida <= 300:
                        self.add_error(campo, 'Cada lado debe medir entre 10 y 300 cm; revisa la unidad seleccionada.')
                    else:
                        datos[campo] = medida
        precio = datos.get('precio')
        if precio is not None and precio < 0:
            self.add_error('precio', 'El precio no puede ser negativo.')
        return datos
