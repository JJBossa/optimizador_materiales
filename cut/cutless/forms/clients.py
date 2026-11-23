from django import forms

from ..models import Cliente
from ..validacion_contacto import (
    PAISES_TELEFONICOS,
    normalizar_rut,
    normalizar_telefono,
    pais_para_telefono_guardado,
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

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.initial['telefono_pais'] = pais_para_telefono_guardado(self.instance.telefono)

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre']
        if self.user and Cliente.objects.filter(usuario=self.user, nombre=nombre).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya tienes un cliente con este nombre.')
        return nombre

    class Meta:
        model = Cliente
        fields = ['nombre', 'rut', 'email', 'telefono_pais', 'telefono', 'direccion', 'notas']
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
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dirección completa'
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
            'direccion': 'Dirección',
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
