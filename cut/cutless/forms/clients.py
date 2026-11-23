from unicodedata import category

from django import forms

from ..direcciones import NOMBRES_PAISES
from ..models import Cliente
from ..validacion_contacto import (
    PAISES_TELEFONICOS,
    normalizar_rut,
    normalizar_telefono,
    pais_para_telefono_guardado,
)


class DireccionEstructuradaForm(forms.Form):
    campos = {
        'direccion_pais': ('País o territorio de la dirección', 'country'),
        'direccion_calle': ('Calle, avenida o camino', 'address-line1'),
        'direccion_numero': ('Número', None),
        'direccion_unidad': ('Departamento, oficina o unidad', 'address-line2'),
        'direccion_region': ('Región, estado o provincia', 'address-level1'),
        'direccion_comuna': ('Comuna o distrito', 'address-level3'),
        'direccion_localidad': ('Ciudad o localidad', 'address-level2'),
        'direccion_referencia': ('Referencia adicional (solo en la ficha)', None),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, (etiqueta, token) in self.campos.items():
            attrs = {'autocomplete': f'section-direccion {token}'} if token else {}
            if nombre == 'direccion_pais':
                opciones = sorted(NOMBRES_PAISES.items(), key=lambda opcion: opcion[1].casefold())
                self.fields[nombre] = forms.ChoiceField(
                    label=etiqueta, required=False, choices=[('', 'Selecciona un país o territorio'), *opciones],
                    widget=forms.Select(attrs={**attrs, 'class': 'form-select'}),
                )
            else:
                self.fields[nombre] = forms.CharField(
                    label=etiqueta, required=False, strip=False,
                    max_length=Cliente._meta.get_field(nombre).max_length,
                    widget=forms.TextInput(attrs={**attrs, 'class': 'form-control'}),
                )
        self.fields['direccion_numero'].help_text = 'Puedes escribir 12-B o S/N.'

    def clean(self):
        datos = super().clean()
        for nombre, valor in list(datos.items()):
            if any(category(caracter) in {'Cc', 'Cs', 'Zl', 'Zp'} for caracter in valor):
                self.add_error(nombre, 'Escribe este dato en una sola línea, sin caracteres de control.')
            else:
                datos[nombre] = valor.strip() or None
        return datos


class DireccionLegadaForm(forms.Form):
    direccion_legada = forms.CharField(
        label='Dirección legada editable', required=False, strip=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )


class ClienteForm(forms.ModelForm):
    """Formulario para crear y editar clientes."""

    telefono_pais = forms.ChoiceField(
        label='País o territorio',
        choices=[('', 'Selecciona un país o territorio'), *PAISES_TELEFONICOS],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'autocomplete': 'section-cliente-tel country'}),
        error_messages={'invalid_choice': 'Selecciona un país o territorio de la lista.'},
    )
    telefono = forms.CharField(
        label='Número de teléfono',
        required=False,
        max_length=64,
        help_text='Escribe el número nacional o pega el número completo con +. Deja vacío si no tienes teléfono.',
        widget=forms.TextInput(attrs={
            'type': 'tel',
            'class': 'form-control',
            'inputmode': 'tel',
            'autocomplete': 'section-cliente-tel tel',
        }),
        error_messages={'max_length': 'El teléfono es demasiado largo. Revisa el número y el prefijo.'},
    )
    direccion_accion = forms.ChoiceField(
        label='Qué hacer con la dirección', required=False,
        choices=[
            ('', 'Mantener la dirección actual'),
            (Cliente.ModoDireccion.ESTRUCTURADA, 'Guardar la dirección estructurada'),
            ('editar_legado', 'Guardar el texto de dirección legada'),
            (Cliente.ModoDireccion.LEGADO, 'Volver a mostrar la dirección legada'),
            (Cliente.ModoDireccion.SIN_DATO, 'Dejar la ficha sin dirección activa'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Esta selección se aplica al guardar los cambios de la ficha.',
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.initial['telefono_pais'] = pais_para_telefono_guardado(self.instance.telefono)
        self.es_alta = self.instance._state.adding
        self.cambios_direccion = {}
        accion = self.data.get('direccion_accion')
        estructurada = {
            campo: self.data[campo] if campo in self.data else getattr(self.instance, campo)
            for campo in DireccionEstructuradaForm.campos
        }
        legado = {'direccion_legada': self.data.get('direccion_legada', self.instance.direccion_legada)}
        self.direccion_estructurada = DireccionEstructuradaForm(
            data=estructurada if self.is_bound and (self.es_alta or accion == 'estructurada') else None,
            initial=estructurada,
        )
        self.direccion_legada = DireccionLegadaForm(
            data=legado if self.is_bound and accion == 'editar_legado' else None,
            initial=legado,
        )

    def clean(self):
        datos = super().clean()
        modo = Cliente.ModoDireccion
        accion = modo.ESTRUCTURADA if self.es_alta else datos.get('direccion_accion')
        if accion == modo.ESTRUCTURADA:
            if not self.direccion_estructurada.is_valid():
                self.add_error(None, 'Revisa los campos de la dirección estructurada.')
            else:
                campos = self.direccion_estructurada.cleaned_data
                if any(campos.get(campo) for campo in (
                    'direccion_calle', 'direccion_region', 'direccion_comuna', 'direccion_localidad'
                )):
                    self.cambios_direccion = {
                        campo: valor for campo, valor in campos.items() if self.es_alta or campo in self.data
                    }
                    self.cambios_direccion['direccion_modo'] = modo.ESTRUCTURADA
                elif not self.es_alta or any(campos.values()):
                    self.add_error(None, 'Indica calle, región, comuna o localidad para guardar la dirección.')
        elif accion == 'editar_legado':
            if 'direccion_legada' not in self.data or not self.direccion_legada.is_valid():
                self.add_error(None, 'Revisa el texto de la dirección legada.')
            else:
                texto = self.direccion_legada.cleaned_data['direccion_legada']
                if not texto.strip():
                    self.add_error(None, 'Para quitar la dirección activa, selecciona «Dejar la ficha sin dirección activa».')
                else:
                    self.cambios_direccion = {'direccion_modo': modo.LEGADO}
                    original = self.instance.direccion_legada.replace('\r\n', '\n').replace('\r', '\n')
                    if texto.replace('\r\n', '\n').replace('\r', '\n') != original:
                        self.cambios_direccion['direccion_legada_editada'] = texto
        elif accion == modo.LEGADO:
            if self.instance.direccion_legada.strip():
                self.cambios_direccion = {'direccion_modo': modo.LEGADO}
            else:
                self.add_error('direccion_accion', 'Esta ficha aún no tiene una dirección legada.')
        elif accion == modo.SIN_DATO:
            self.cambios_direccion = {'direccion_modo': modo.SIN_DATO}
        return datos

    def save(self, commit=True):
        cliente = super().save(commit=False)
        for campo, valor in self.cambios_direccion.items():
            setattr(cliente, campo, valor)
        if commit:
            if self.es_alta:
                cliente.save()
            else:
                contacto = [campo for campo in ('nombre', 'rut', 'email', 'telefono', 'notas') if campo in self.data]
                cliente.save(update_fields=[*contacto, *self.cambios_direccion, 'fecha_actualizacion'])
        return cliente

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre']
        if self.user and Cliente.objects.filter(usuario=self.user, nombre=nombre).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya tienes un cliente con este nombre.')
        return nombre

    class Meta:
        model = Cliente
        fields = ['nombre', 'rut', 'email', 'telefono_pais', 'telefono', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Juan Pérez, Empresa XYZ S.A.'
            }),
            'rut': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej.: 12.345.678-5'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'cliente@ejemplo.com'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Notas adicionales sobre el cliente'
            }),
        }
        labels = {
            'nombre': 'Nombre o Razón Social',
            'rut': 'RUT',
            'email': 'Correo Electrónico',
            'notas': 'Notas',
        }
        help_texts = {'rut': 'Incluye el dígito verificador. Puedes escribir el RUT con o sin puntos.'}

    def _dato_guardado_sin_cambios(self, campo):
        # El navegador elimina saltos de línea de los campos de una sola línea.
        original = getattr(self.instance, campo)
        visible = original.replace('\r', '').replace('\n', '')
        enviado = self[campo].data
        return not self.instance._state.adding and enviado in (None, original, visible)

    def clean_rut(self):
        if self._dato_guardado_sin_cambios('rut'):
            return self.instance.rut
        return normalizar_rut(self.cleaned_data['rut'])

    def clean_telefono(self):
        pais_inicial = self.initial['telefono_pais']
        pais = self.cleaned_data.get('telefono_pais') or pais_inicial
        if pais == pais_inicial and self._dato_guardado_sin_cambios('telefono'):
            return self.instance.telefono
        return normalizar_telefono(self.cleaned_data['telefono'], pais)
