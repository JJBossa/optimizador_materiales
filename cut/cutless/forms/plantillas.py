import csv
from functools import partial

from django import forms

from ..formatos_numericos import FORMATO_DECIMAL, FORMATO_ENTERO, preparar_decimal
from ..models import Plantilla
from ..pieces import FormatoPiezasInvalido, filas_piezas, parsear_piezas_desde_texto, piezas_como_csv, serializar_piezas
from ..units import (
    CENTIMETROS_POR_UNIDAD, LADO_MAX_CM, LADO_PIEZA_MIN_CM, LADO_TABLERO_MIN_CM,
    margen_en_cm, margen_en_mm, medida_editable, medida_tablero_en_cm,
)
from .nombres import LIMITE_PLANTILLA, NombreLimitadoField, NombreModeloMixin
from .numeros import DecimalEntradaField, MedidaEntradaField

CONTRATO_PIEZAS = {
    'factores': CENTIMETROS_POR_UNIDAD, 'minCm': LADO_PIEZA_MIN_CM, 'maxCm': LADO_MAX_CM,
    'decimal': FORMATO_DECIMAL, 'entero': FORMATO_ENTERO,
}

class PlantillaForm(NombreModeloMixin, forms.ModelForm):
    """Formulario para crear y editar plantillas."""

    margen_corte = DecimalEntradaField(
        label='Margen de Corte (mm)', required=False, min_value=0, max_value=10,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    
    def __init__(self, *args, user=None, origen_tablero=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.origen_tablero = origen_tablero if origen_tablero is not None else self.instance
        if self.instance.pk:
            campo_nombre = self.fields['nombre']
            if (self.instance.es_predefinida and campo_nombre.nombre_guardado is None
                    and campo_nombre.supera_limite(self.instance.nombre)):
                campo_nombre.help_text += ' Acorta el nombre original para guardar una copia.'
            unidad = self.instance.unidad_medida or 'cm'
            self.initial['ancho_tablero'] = medida_editable(self.instance.ancho_tablero, unidad)
            self.initial['alto_tablero'] = medida_editable(self.instance.alto_tablero, unidad)
            if not self.is_bound:
                try:
                    self.initial['piezas'] = piezas_como_csv(self.instance.piezas)
                except FormatoPiezasInvalido:
                    # Conservar el original para que la corrección sea explícita.
                    self.initial['piezas'] = self.instance.piezas
                    self.fields['piezas'].help_text = (
                        'El listado guardado necesita revisión. Comprueba todas las filas antes de guardar.'
                    )
            self.initial['margen_corte'] = margen_en_mm(self.instance.margen_corte)
        else:
            self.initial.setdefault('margen_corte', 3)

    @property
    def contrato_piezas(self):
        return CONTRATO_PIEZAS

    @property
    def filas_editor(self):
        try:
            filas = list(filas_piezas(self['piezas'].value() or '', csv_editable=True))
        except (csv.Error, FormatoPiezasInvalido):
            return None
        if len(filas) <= 20 and all(len(fila) == 4 for fila in filas):
            return [[str(preparar_decimal(valor)) for valor in fila] for fila in filas]
        return None

    def clean(self):
        datos = super().clean()
        unidad = datos.get('unidad_medida')
        if unidad:
            for campo in ('ancho_tablero', 'alto_tablero'):
                valor = datos.get(campo)
                if valor is not None:
                    cm = medida_tablero_en_cm(valor, unidad, getattr(self.origen_tablero, campo), self.origen_tablero.unidad_medida)
                    if not LADO_TABLERO_MIN_CM <= cm <= LADO_MAX_CM:
                        self.add_error(campo, 'Cada lado del tablero debe medir entre 10 y 300 cm. Revisa la unidad seleccionada.')
                    else:
                        datos[campo] = cm
        piezas = datos.get('piezas')
        if piezas and unidad:
            filas = parsear_piezas_desde_texto(piezas, unidad, estricto=True)
            if len(filas) > 20:
                self.add_error('piezas', 'Puedes guardar hasta 20 tipos de pieza.')
            for numero, pieza in enumerate(filas, 1):
                ancho, alto = pieza['ancho_cm'], pieza['alto_cm']
                if not LADO_PIEZA_MIN_CM <= ancho <= LADO_MAX_CM or not LADO_PIEZA_MIN_CM <= alto <= LADO_MAX_CM:
                    self.add_error('piezas', f'Pieza {numero}: cada lado debe medir entre 0,1 y 300 cm.')
                elif datos.get('ancho_tablero') and datos.get('alto_tablero'):
                    w, h = datos['ancho_tablero'], datos['alto_tablero']
                    cabe = ancho <= w and alto <= h
                    girada = datos.get('permitir_rotacion') and alto <= w and ancho <= h
                    if not (cabe or girada):
                        self.add_error('piezas', f'Pieza {numero}: no cabe en el tablero con la rotación elegida.')
        nombre = datos.get('nombre')
        if self.user and nombre:
            existentes = Plantilla.objects.filter(usuario=self.user, nombre=nombre)
            if not self.instance.es_predefinida:
                existentes = existentes.exclude(pk=self.instance.pk)
            if existentes.exists():
                self.add_error('nombre', 'Ya tienes una plantilla con este nombre. Elige otro.')
        return datos

    class Meta:
        model = Plantilla
        fields = ['nombre', 'descripcion', 'categoria', 'ancho_tablero', 'alto_tablero', 'unidad_medida', 'piezas', 'permitir_rotacion', 'margen_corte']
        field_classes = {
            'nombre': partial(NombreLimitadoField, limite=LIMITE_PLANTILLA),
            'ancho_tablero': MedidaEntradaField, 'alto_tablero': MedidaEntradaField,
        }
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Cocina Estándar, Mueble de TV'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la plantilla'
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-select'
            }),
            'ancho_tablero': forms.TextInput(attrs={'class': 'form-control'}),
            'alto_tablero': forms.TextInput(attrs={'class': 'form-control'}),
            'unidad_medida': forms.Select(attrs={
                'class': 'form-select'
            }),
            'piezas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Formato: nombre,ancho,alto,cantidad (una por línea)\n\nEjemplos:\nPuerta,80,200,2\nCajón,40,50,4\nFondo,85,198,1\nTravesaño,70,2,4\n\nCada línea debe tener EXACTAMENTE 4 valores separados por comas.'
            }),
            'permitir_rotacion': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'nombre': 'Nombre de la Plantilla',
            'descripcion': 'Descripción',
            'categoria': 'Categoría',
            'ancho_tablero': 'Ancho del tablero',
            'alto_tablero': 'Alto del tablero',
            'unidad_medida': 'Unidad de Medida',
            'piezas': 'Piezas (formato: nombre,ancho,alto,cantidad)',
            'permitir_rotacion': 'Permitir Rotación',
            'margen_corte': 'Margen de Corte (mm)',
        }
    
    def clean_piezas(self):
        texto = self.cleaned_data['piezas']
        try:
            piezas = parsear_piezas_desde_texto(texto, estricto=True, csv_editable=True)
        except (ValueError, TypeError):
            raise forms.ValidationError(
                'Usa nombre,ancho,alto,cantidad. En CSV escribe medidas positivas con punto decimal y cantidades enteras.'
            ) from None
        if not piezas:
            raise forms.ValidationError('Debes ingresar al menos una pieza.')
        for pieza in piezas:
            if len(pieza['nombre']) > 50:
                raise forms.ValidationError('Cada pieza necesita un nombre de hasta 50 caracteres.')
            if pieza['cantidad'] > 100:
                raise forms.ValidationError('La cantidad debe estar entre 1 y 100 por tipo de pieza.')
        if self.instance.pk:
            try:
                if piezas == parsear_piezas_desde_texto(self.instance.piezas, estricto=True):
                    return self.instance.piezas
            except FormatoPiezasInvalido:
                pass  # El usuario puede corregir un listado histórico ilegible.
        return serializar_piezas(piezas)

    def clean_margen_corte(self):
        margen = self.cleaned_data['margen_corte']
        if margen is None:
            return 0.3
        if self.origen_tablero.pk and float(margen) == margen_en_mm(self.origen_tablero.margen_corte):
            return self.origen_tablero.margen_corte
        return margen_en_cm(margen)
