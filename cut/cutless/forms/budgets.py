from django import forms
from django.utils import timezone

from ..models import Presupuesto, Optimizacion, Cliente, Proyecto
from .descripciones import DescripcionLimitadaField, TextoLimitadoTextarea
from .nombres import NombreLimitadoField
from .numeros import ImporteDecimalField

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
        fields = ['cliente', 'optimizaciones', 'precio_tablero', 'mano_obra', 'fecha_validez', 'notas', 'estado', 'proyecto']
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
            'estado': forms.Select(attrs={
                'class': 'form-select'
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
            'estado': 'Estado',
            'proyecto': 'Proyecto (Opcional)',
        }
        help_texts = {
            'fecha_validez': 'Fecha hasta la cual el presupuesto es válido',
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        self._hoy = timezone.localdate(timezone=timezone.get_default_timezone())
        es_creacion = self.instance._state.adding
        self._fecha_guardada = None
        if (not es_creacion and self.instance.estado == 'borrador'
                and user is not None and self.instance.usuario_id == user.pk):
            self._fecha_guardada = self.instance.fecha_validez
            self.fields['notas'].conservar(self.instance.notas)

        campo_fecha = self.fields['fecha_validez']
        if self._fecha_guardada is not None and self._fecha_guardada < self._hoy:
            campo_fecha.help_text = 'Puedes conservar la fecha vencida guardada o elegir hoy o una fecha posterior'
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
            if instance:
                # Una optimización puede cotizarse en varios presupuestos, igual que al crear.
                optimizaciones_queryset = Optimizacion.objects.filter(usuario=user).order_by('-fecha')
                # Pre-seleccionar las optimizaciones que ya están en el presupuesto
                self.fields['optimizaciones'].initial = list(instance.optimizaciones.values_list('pk', flat=True))
            else:
                # Si es creación, mostrar todas las optimizaciones del usuario
                optimizaciones_queryset = Optimizacion.objects.filter(usuario=user).order_by('-fecha')
            self.fields['optimizaciones'].queryset = optimizaciones_queryset
            # Filtrar proyectos del usuario
            self.fields['proyecto'].queryset = Proyecto.objects.filter(usuario=user).order_by('-fecha_creacion')
        
        # No duplicar el cliente seleccionado en la alternativa de creación.
        self.fields['nombre_cliente_nuevo'].initial = ''

    def clean_fecha_validez(self):
        fecha = self.cleaned_data['fecha_validez']
        if fecha < self._hoy and fecha != self._fecha_guardada:
            raise forms.ValidationError(
                'La fecha de validez no puede ser anterior a hoy. Selecciona la fecha actual o una posterior.',
                code='fecha_pasada',
            )
        return fecha

    def clean(self):
        from decimal import Decimal
        datos = super().clean()
        if datos.get('cliente') and datos.get('nombre_cliente_nuevo'):
            self.add_error('nombre_cliente_nuevo', 'Selecciona un cliente o escribe uno nuevo, no ambos.')
        for campo in ('precio_tablero', 'mano_obra'):
            if datos.get(campo) is not None and datos[campo] < 0:
                self.add_error(campo, 'El importe no puede ser negativo.')
        precio, mano = datos.get('precio_tablero'), datos.get('mano_obra')
        seleccion = datos.get('optimizaciones')
        if precio is not None and mano is not None and seleccion is not None:
            total = precio * sum(opt.num_tableros for opt in seleccion) + mano
            if total > Decimal('99999999.99'):
                self.add_error('precio_tablero', 'El total supera el máximo admitido: $99.999.999,99.')
        return datos
