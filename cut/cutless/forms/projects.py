from hashlib import sha256

from django import forms
from django.db.models import Q

from ..models import Proyecto, Cliente, Optimizacion
from ..services.calendario import fecha_comercial
from .descripciones import DescripcionLimitadaField, DescripcionModeloMixin, TextoLimitadoTextarea
from .nombres import NombreLimitadoField, NombreModeloMixin


FECHAS_PROYECTO = {
    'fecha_inicio': 'La fecha de inicio',
    'fecha_fin': 'La fecha de finalización',
}


class ProyectoForm(DescripcionModeloMixin, NombreModeloMixin, forms.ModelForm):
    """Formulario para crear y editar proyectos"""
    
    # Campo personalizado para seleccionar múltiples optimizaciones
    optimizaciones = forms.ModelMultipleChoiceField(
        queryset=Optimizacion.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        label='Optimizaciones (Opcional)',
        help_text='Selecciona las optimizaciones que deseas asociar a este proyecto.'
    )
    
    class Meta:
        model = Proyecto
        fields = ['nombre', 'descripcion', 'cliente', 'fecha_inicio', 'fecha_fin']
        field_classes = {'nombre': NombreLimitadoField, 'descripcion': DescripcionLimitadaField}
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Cocina Integral, Mueble de Sala'
            }),
            'descripcion': TextoLimitadoTextarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción del proyecto'
            }),
            'cliente': forms.Select(attrs={
                'class': 'form-select'
            }),
            'fecha_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'nombre': 'Nombre del Proyecto',
            'descripcion': 'Descripción',
            'cliente': 'Cliente',
            'fecha_inicio': 'Fecha de Inicio',
            'fecha_fin': 'Fecha de Finalización',
        }
        error_messages = {
            'fecha_inicio': {'invalid': 'Ingresa una fecha de inicio válida.'},
            'fecha_fin': {'invalid': 'Ingresa una fecha de finalización válida.'},
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)

        self.hoy = fecha_comercial()
        self._estado_guardado = self.instance.estado
        self.modifica_optimizaciones = self.is_bound and any(
            self.add_prefix(campo) in self.data for campo in ('optimizaciones', 'seleccion_optimizaciones')
        )
        self.fechas_guardadas = {
            campo: getattr(self.instance, campo) for campo in FECHAS_PROYECTO
        } if not self.instance._state.adding else {}
        fechas_omitidas = {}
        for nombre in FECHAS_PROYECTO:
            campo = self.fields[nombre]
            guardada = self.fechas_guardadas.get(nombre)
            clave = self.add_prefix(nombre)
            if self.is_bound and guardada is not None and clave not in self.data:
                fechas_omitidas[clave] = guardada.isoformat()
            if guardada is not None and guardada < self.hoy:
                campo.help_text = 'Puedes conservar la fecha guardada, dejar el campo vacío o elegir hoy o una fecha posterior.'
            else:
                campo.widget.attrs['min'] = self.hoy.isoformat()
                campo.help_text = 'Opcional. Elige hoy o una fecha posterior.'
        if fechas_omitidas:
            self.data = self.data.copy()
            self.data.update(fechas_omitidas)
        
        self.fields['cliente'].queryset = Cliente.objects.none()
        if user:
            # Filtrar clientes del usuario
            self.fields['cliente'].queryset = Cliente.objects.filter(usuario=user).order_by('nombre')
            
            # Filtrar optimizaciones del usuario que no estén ya en otro proyecto (o que estén en este proyecto si es edición)
            if instance:
                # Si es edición, mostrar optimizaciones que ya están en este proyecto o que no tienen proyecto
                optimizaciones_queryset = Optimizacion.objects.filter(
                    usuario=user
                ).filter(
                    Q(proyecto__isnull=True) | Q(proyecto=instance)
                ).order_by('-fecha')
                # Pre-seleccionar las optimizaciones que ya están en el proyecto
                self.optimizaciones_guardadas = list(
                    instance.optimizacion_set.filter(usuario=user).order_by('pk').values_list('pk', flat=True)
                )
                self.fields['optimizaciones'].initial = self.optimizaciones_guardadas
                # También detecta asociaciones modificadas desde el formulario del optimizador.
                revision = ':'.join((instance.estado, instance.fecha_actualizacion.isoformat(),
                                     ','.join(map(str, self.optimizaciones_guardadas))))
                self.fields['revision'] = forms.CharField(required=False, widget=forms.HiddenInput)
                self.initial['revision'] = sha256(revision.encode()).hexdigest()
            else:
                # Si es creación, mostrar solo optimizaciones sin proyecto
                optimizaciones_queryset = Optimizacion.objects.filter(
                    usuario=user,
                    proyecto__isnull=True
                ).order_by('-fecha')
            
            self.fields['optimizaciones'].queryset = optimizaciones_queryset
        
    def clean(self):
        datos = super().clean()
        clave = self.add_prefix('estado')
        if clave in self.data:
            estados = self.data.getlist(clave) if hasattr(self.data, 'getlist') else [self.data[clave]]
            if estados != [self._estado_guardado]:
                self.add_error(None, 'El estado se cambia con las acciones del detalle del proyecto.')
        if 'revision' in self.fields:
            clave = self.add_prefix('revision')
            if (clave in self.data or self.modifica_optimizaciones) and datos.get('revision') != self.initial['revision']:
                self.add_error(None, 'El proyecto cambió. Vuelve a abrirlo antes de guardar.')
        for campo, etiqueta in FECHAS_PROYECTO.items():
            fecha = datos.get(campo)
            if fecha is not None and fecha < self.hoy and fecha != self.fechas_guardadas.get(campo):
                self.add_error(campo, forms.ValidationError(
                    f'{etiqueta} no puede ser anterior a hoy. Elige hoy o una fecha posterior.',
                    code='fecha_pasada',
                ))
        inicio, fin = datos.get('fecha_inicio'), datos.get('fecha_fin')
        guardadas = (self.fechas_guardadas.get('fecha_inicio'), self.fechas_guardadas.get('fecha_fin'))
        if inicio and fin and fin < inicio and (inicio, fin) != guardadas:
            self.add_error('fecha_fin', forms.ValidationError(
                'La finalización no puede ser anterior al inicio.',
                code='fin_anterior_al_inicio',
            ))
        return datos
