import math
import re
from decimal import Decimal

from django import forms

from ..materiales import dimension_material_valida, precio_material_valido, validar_precio_material
from ..models import Material
from ..units import convertir_a_cm, convertir_desde_cm


_AGRUPACION_AMBIGUA = r'[+\-]?0*[1-9][0-9]{0,2}[.,][0-9]{3}'
_FORMATO_DECIMAL = rf'(?!{_AGRUPACION_AMBIGUA}$)[+\-]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)'
_AYUDA_DECIMAL = 'Usa coma o punto decimal, sin separadores de miles.'
_AYUDA_DIMENSION = f'{_AYUDA_DECIMAL} Para tres decimales ambiguos, añade un cero final (ej.: 12,3450).'


class DecimalMaterialField(forms.DecimalField):
    widget = forms.TextInput

    def widget_attrs(self, widget):
        return {**super().widget_attrs(widget), 'inputmode': 'decimal', 'pattern': _FORMATO_DECIMAL}

    def prepare_value(self, value):
        if isinstance(value, (float, Decimal)):
            texto = str(value)
            # Los decimales iniciales provienen del modelo y ya tienen un significado conocido.
            if re.fullmatch(_AGRUPACION_AMBIGUA, texto):
                return f'{texto}0'
            if 'e' in texto.lower():
                return format(Decimal(texto), 'f')
        return super().prepare_value(value)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        texto = str(self.prepare_value(value))
        if not re.fullmatch(_FORMATO_DECIMAL, texto):
            raise forms.ValidationError(f'Escribe un número válido. {_AYUDA_DECIMAL}', code='invalid')
        return super().to_python(texto.replace(',', '.'))


class MaterialBaseForm(forms.ModelForm):
    """Controla la entrada decimal y conserva las cantidades históricas intactas."""

    medidas_en_cm = False
    medidas = ('ancho', 'alto')

    class Meta:
        model = Material
        fields = ('nombre', 'ancho', 'alto', 'unidad_medida', 'precio', 'descripcion')
        field_classes = dict.fromkeys(('ancho', 'alto', 'precio'), DecimalMaterialField)
        help_texts = {
            'ancho': _AYUDA_DIMENSION,
            'alto': _AYUDA_DIMENSION,
            'precio': f'Precio en pesos chilenos (opcional). Hasta dos decimales. {_AYUDA_DECIMAL}',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.medidas_originales = {}
        self.unidad_original = self.instance.unidad_medida
        if self.instance.pk is None:
            return

        if self.unidad_original not in dict(Material.UNIDADES_CHOICES):
            unidad = self.fields['unidad_medida']
            unidad.choices = [('', 'Unidad histórica inválida. Selecciona una unidad.'), *unidad.choices]
            self.initial['unidad_medida'] = ''
            self.unidad_original = 'cm'

        for campo in self.medidas:
            original = getattr(self.instance, campo)
            self.medidas_originales[campo] = original
            self.initial[campo] = original if self.medidas_en_cm else convertir_desde_cm(
                original, self.unidad_original
            )
            if not dimension_material_valida(original):
                if math.isfinite(self.initial[campo]):
                    aviso = 'La medida histórica está fuera de rango. Puedes conservarla o corregirla.'
                else:
                    aviso = 'Corrige la medida histórica para poder guardar.'
                self.fields[campo].help_text += f' {aviso}'

        if not precio_material_valido(self.instance.precio):
            self.fields['precio'].help_text += ' El precio histórico es inválido. Puedes conservarlo o corregirlo.'

    def clean(self):
        datos = super().clean()
        unidad = 'cm' if self.medidas_en_cm else datos.get('unidad_medida')
        conserva_unidad = self.medidas_en_cm or unidad == self.unidad_original
        for campo in self.medidas:
            valor = datos.get(campo)
            if valor is None or not unidad:
                continue
            if campo in self.medidas_originales and conserva_unidad and valor == Decimal(str(self.initial[campo])):
                datos[campo] = self.medidas_originales[campo]
                continue
            medida = convertir_a_cm(float(valor), unidad)
            if dimension_material_valida(medida):
                datos[campo] = medida
            else:
                self.add_error(campo, 'Cada lado debe medir entre 10 y 300 cm; revisa la unidad seleccionada.')

        precio = datos.get('precio')
        if self.instance.pk is None or precio != self.instance.precio:
            try:
                validar_precio_material(precio)
            except forms.ValidationError as error:
                self.add_error('precio', error)
        return datos

    def campos_actualizacion(self):
        campos = set(self.changed_data).difference(self.medidas)
        campos.update(
            campo for campo, original in self.medidas_originales.items()
            if self.cleaned_data[campo] != original
        )
        campos.add('fecha_actualizacion')
        return campos


class MaterialForm(MaterialBaseForm):
    """Alta y edición desde la biblioteca de CutLess."""

    class Meta(MaterialBaseForm.Meta):
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: MDF 18mm, Contrachapado'
            }),
            'ancho': forms.TextInput(attrs={'class': 'form-control', 'title': _AYUDA_DIMENSION}),
            'alto': forms.TextInput(attrs={'class': 'form-control', 'title': _AYUDA_DIMENSION}),
            'unidad_medida': forms.Select(attrs={
                'class': 'form-select'
            }),
            'precio': forms.TextInput(attrs={
                'class': 'form-control', 'title': _AYUDA_DECIMAL, 'placeholder': 'Opcional',
            }),
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


class MaterialAdminForm(MaterialBaseForm):
    """El administrador edita en cm y elige una unidad de presentación."""

    medidas_en_cm = True

    class Meta(MaterialBaseForm.Meta):
        fields = ('usuario', 'nombre', 'ancho', 'alto', 'unidad_medida', 'precio', 'es_predefinido', 'descripcion')
        labels = {'ancho': 'Ancho (cm)', 'alto': 'Alto (cm)', 'unidad_medida': 'Unidad de presentación'}
        help_texts = {
            **MaterialBaseForm.Meta.help_texts,
            'ancho': f'Ingresa el ancho en centímetros. {_AYUDA_DIMENSION}',
            'alto': f'Ingresa el alto en centímetros. {_AYUDA_DIMENSION}',
            'unidad_medida': 'Controla la presentación del material. Las medidas de este formulario se ingresan en cm.',
        }
