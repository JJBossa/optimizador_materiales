from django import forms

from ..models import Presupuesto, Optimizacion, Cliente, Proyecto
from ..services.presupuestos import TRANSICIONES_REGISTRO, fecha_comercial, fecha_vencida
from .descripciones import DescripcionLimitadaField, TextoLimitadoTextarea
from .nombres import NombreLimitadoField
from .numeros import ImporteDecimalField

ACCION_BORRADOR = 'guardar_borrador'
ACCION_EMITIR = 'emitir'


def valores_post(datos, campo):
    return datos.getlist(campo) if hasattr(datos, 'getlist') else [datos[campo]] if campo in datos else []


class PresupuestoForm(forms.ModelForm):
    """Formulario para crear y editar presupuestos con múltiples optimizaciones"""
    
    # Campo opcional para escribir el nombre del cliente directamente
    nombre_cliente_nuevo = NombreLimitadoField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'O escribe el nombre del cliente aquí'
        }),
        label='Nombre del Cliente (Alternativa)',
        help_text='Si escribes un nombre aquí, se creará o buscará el cliente automáticamente. Deja vacío si seleccionaste un cliente arriba.'
    )
    
    class Meta:
        model = Presupuesto
        fields = ['cliente', 'optimizaciones', 'precio_tablero', 'mano_obra', 'fecha_validez', 'notas', 'proyecto']
        field_classes = {
            'precio_tablero': ImporteDecimalField, 'mano_obra': ImporteDecimalField,
            'notas': DescripcionLimitadaField,
        }
        widgets = {
            'cliente': forms.Select(attrs={
                'class': 'form-select'
            }),
            'optimizaciones': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'precio_tablero': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'mano_obra': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'fecha_validez': forms.DateInput(format='%Y-%m-%d', attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notas': TextoLimitadoTextarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Notas adicionales para el cliente'
            }),
            'proyecto': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'cliente': 'Cliente',
            'optimizaciones': 'Optimizaciones',
            'precio_tablero': 'Precio por Tablero',
            'mano_obra': 'Mano de Obra',
            'fecha_validez': 'Válido Hasta',
            'notas': 'Notas',
            'proyecto': 'Proyecto (Opcional)',
        }
        help_texts = {
            'fecha_validez': 'Fecha hasta la cual el presupuesto es válido',
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        self._hoy = fecha_comercial()
        acciones = valores_post(self.data, 'accion')
        self.accion = acciones[0] if len(acciones) == 1 else ACCION_BORRADOR
        self._accion_valida = len(acciones) <= 1 and self.accion in (ACCION_BORRADOR, ACCION_EMITIR)
        es_creacion = self.instance._state.adding
        self._fecha_guardada = None
        if (not es_creacion and self.instance.estado == 'borrador'
                and user is not None and self.instance.usuario_id == user.pk):
            self._fecha_guardada = self.instance.fecha_validez
            self.fields['notas'].conservar(self.instance.notas)
            self.fields['revision'] = forms.CharField(required=False, widget=forms.HiddenInput)
            self.initial['revision'] = self.instance.fecha_actualizacion.isoformat()

        campo_fecha = self.fields['fecha_validez']
        if self._fecha_guardada is not None and self._fecha_guardada < self._hoy:
            campo_fecha.help_text = (
                'Puedes conservar la fecha vencida guardada al guardar el borrador. '
                'Para emitir, elige hoy o una fecha posterior.'
            )
        else:
            campo_fecha.widget.attrs['min'] = self._hoy.isoformat()
        if es_creacion and not self.is_bound:
            self.initial.setdefault('fecha_validez', self._hoy)

        self.fields['cliente'].required = False
        
        for campo in ('cliente', 'optimizaciones', 'proyecto'):
            self.fields[campo].queryset = self.fields[campo].queryset.none()
        if user:
            # Filtrar clientes del usuario
            self.fields['cliente'].queryset = Cliente.objects.filter(usuario=user).order_by('nombre')
            # Filtrar optimizaciones del usuario
            self.fields['optimizaciones'].queryset = (
                Optimizacion.objects.filter(usuario=user).select_related('material').order_by('-fecha')
            )
            if instance:
                self.fields['optimizaciones'].initial = list(instance.optimizaciones.values_list('pk', flat=True))
            # Filtrar proyectos del usuario
            self.fields['proyecto'].queryset = Proyecto.objects.filter(usuario=user).order_by('-fecha_creacion')
        
        # No duplicar el cliente seleccionado en la alternativa de creación.
        self.fields['nombre_cliente_nuevo'].initial = ''

    def clean_fecha_validez(self):
        fecha = self.cleaned_data['fecha_validez']
        if fecha_vencida(fecha, hoy=self._hoy) and self.accion == ACCION_EMITIR:
            raise forms.ValidationError(
                'Para emitir, selecciona una fecha de validez de hoy o posterior.', code='emision_fecha_pasada',
            )
        if fecha_vencida(fecha, hoy=self._hoy) and fecha != self._fecha_guardada:
            raise forms.ValidationError(
                'La fecha de validez no puede ser anterior a hoy. Selecciona la fecha actual o una posterior.',
                code='fecha_pasada',
            )
        return fecha

    def clean(self):
        from decimal import Decimal
        datos = super().clean()
        estados = valores_post(self.data, 'estado')
        if not self._accion_valida or (estados and ('accion' in self.data or estados != ['borrador'])):
            self.add_error(None, 'Usa una sola acción: guardar borrador o emitir presupuesto.')
        if 'revision' in self.fields:
            revisiones = valores_post(self.data, 'revision')
            if (revisiones or self.accion == ACCION_EMITIR) and revisiones != [self.initial['revision']]:
                # El formulario ligado conserva la revisión antigua para evitar sobrescrituras al reenviar.
                self.add_error(None, 'Este borrador cambió. Vuelve a abrirlo antes de guardar o emitir.')
        if datos.get('cliente') and datos.get('nombre_cliente_nuevo'):
            self.add_error('nombre_cliente_nuevo', 'Selecciona un cliente o escribe uno nuevo, no ambos.')
        for campo in ('precio_tablero', 'mano_obra'):
            if datos.get(campo) is not None and datos[campo] < 0:
                self.add_error(campo, 'El importe no puede ser negativo.')
        precio, mano = datos.get('precio_tablero'), datos.get('mano_obra')
        seleccion = datos.get('optimizaciones')
        if precio is not None and mano is not None and seleccion is not None:
            total = precio * sum(opt.num_tableros or 0 for opt in seleccion) + mano
            if total > Decimal('99999999.99'):
                self.add_error('precio_tablero', 'El total supera el máximo admitido: $99.999.999,99.')
        return datos


class EstadoPresupuestoEmitidoForm(forms.Form):
    estado = forms.ChoiceField(label='Nuevo estado')
    estado_origen = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, presupuesto, **kwargs):
        super().__init__(*args, **kwargs)
        self.estado_actual = presupuesto.estado
        self.initial['estado_origen'] = self.estado_actual
        etiquetas = dict(Presupuesto.ESTADOS_CHOICES)
        self.fields['estado'].choices = [
            (destino, etiquetas[destino]) for destino in TRANSICIONES_REGISTRO.get(self.estado_actual, ())
        ]

    def clean_estado(self):
        if len(valores_post(self.data, 'estado')) != 1:
            raise forms.ValidationError('Registra un solo estado.', code='estado_multiple')
        return self.cleaned_data['estado']

    def clean(self):
        datos = super().clean()
        if valores_post(self.data, 'estado_origen') != [self.estado_actual] or 'accion' in self.data:
            self.add_error(None, 'El presupuesto cambió de estado. Vuelve al detalle y revisa su estado actual.')
        return datos
