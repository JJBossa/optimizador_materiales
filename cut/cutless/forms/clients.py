from django import forms

from ..direcciones import DPA_CHILE, NOMBRES_PAISES, REGIONES_CHILE, codigo_por_nombre, nombre_comparable
from ..models import Cliente
from ..validacion_contacto import (
    PAISES_TELEFONICOS,
    clave_rut_cliente,
    normalizar_rut,
    normalizar_telefono,
    pais_para_telefono_guardado,
)
from ..validacion_direcciones import tiene_controles_direccion, validar_numero_direccion, validar_texto_direccion
from .nombres import NombreLimitadoField, NombreModeloMixin


PAISES_POSTALES = sorted(NOMBRES_PAISES.items(), key=lambda opcion: nombre_comparable(opcion[1]))


class DireccionEstructuradaForm(forms.Form):
    campos = {
        'direccion_pais': ('País o territorio de la dirección', 'country'),
        'direccion_region': ('Región, estado o provincia', 'address-level1'),
        'direccion_comuna': ('Ciudad o comuna', 'address-level2'),
        'direccion_calle': ('Calle, avenida o camino', 'address-line1'),
        'direccion_numero': ('Número', None),
        'direccion_codigo_postal': ('Código postal (opcional)', 'postal-code'),
        'direccion_unidad': ('Departamento, oficina o unidad (opcional)', 'address-line2'),
        'direccion_referencia': ('Referencia adicional (opcional, solo en la ficha)', None),
    }

    def __init__(self, cliente, data=None, actualizacion=None):
        modo = Cliente.ModoDireccion
        estructurada = cliente.direccion_modo == modo.ESTRUCTURADA
        self.requiere_actualizacion = not estructurada and cliente.direccion_modo != modo.SIN_DATO and bool(
            cliente.direccion_legada.strip()
        )
        self.guardada = {
            campo: (getattr(cliente, campo) or '') if estructurada else ''
            for campo in self.campos
        }
        if estructurada and (not self.guardada['direccion_comuna'] or cliente.direccion_pais != 'CL'):
            self.guardada['direccion_comuna'] = cliente.direccion_localidad or self.guardada['direccion_comuna']
        self.opcional = not self.requiere_actualizacion and not any(self.guardada.values())
        self.cliente = cliente
        if self.guardada['direccion_pais'] == 'CL':
            region = codigo_por_nombre(self.guardada['direccion_region'], REGIONES_CHILE)
            self.guardada['direccion_region'] = region
            comunas = DPA_CHILE.get(region, {}).get('comunas', {})
            self.guardada['direccion_comuna'] = codigo_por_nombre(self.guardada['direccion_comuna'], comunas)
        datos = data if data is not None else actualizacion
        valores = {campo: datos.get(campo, valor) if datos is not None else valor for campo, valor in self.guardada.items()}
        self.conserva_guardada = (
            data is not None and estructurada and not cliente._state.adding
            and all(self._coincide_con_guardada(campo, valor) for campo, valor in valores.items())
        )
        if self.conserva_guardada:
            valores = self.guardada.copy()
        self.chile = valores['direccion_pais'] == 'CL'
        origen = datos.get('ubicacion_pais') if datos is not None else None
        self.cambio_tipo = origen is not None and origen != valores['direccion_pais']
        if self.cambio_tipo and not self.conserva_guardada:
            valores.update(direccion_region='', direccion_comuna='')
        self.region = valores['direccion_region']
        self.cambios = {}
        # Una ficha sin cambios de dirección no debe volver a validar los datos históricos.
        super().__init__(data=valores if data is not None and not self.conserva_guardada else None, initial=valores)

        for nombre, (etiqueta, token) in self.campos.items():
            attrs = {'autocomplete': f'section-direccion {token}'} if token else {}
            if nombre == 'direccion_pais':
                campo = forms.ChoiceField(
                    label=etiqueta, required=False, choices=[('', 'Selecciona un país o territorio'), *PAISES_POSTALES],
                    widget=forms.Select(attrs={**attrs, 'class': 'form-select'}),
                    error_messages={'invalid_choice': 'Selecciona un país o territorio de la lista.'},
                )
                anterior = self.guardada[nombre]
                if anterior and anterior not in NOMBRES_PAISES and valores[nombre] == anterior:
                    # Mostrar el país anterior sin añadirlo a las opciones válidas para un cambio.
                    campo.widget.choices = [*campo.choices, (anterior, f'{anterior} (guardado anteriormente)')]
                self.fields[nombre] = campo
                continue
            widget = forms.TextInput(attrs={**attrs, 'class': 'form-control'})
            if self.chile and nombre in ('direccion_region', 'direccion_comuna'):
                opciones = REGIONES_CHILE if nombre == 'direccion_region' else DPA_CHILE.get(
                    self.region, {}
                ).get('comunas', {})
                placeholder = 'Selecciona una región' if nombre == 'direccion_region' else 'Selecciona una comuna'
                choices = [('', placeholder), *sorted(opciones.items(), key=lambda opcion: nombre_comparable(opcion[1]))]
                anterior = self.guardada[nombre]
                if (anterior and anterior not in opciones and self.guardada['direccion_pais'] == 'CL'
                        and (nombre == 'direccion_region' or self.region == self.guardada['direccion_region'])
                        and valores[nombre] == anterior):
                    choices.append((anterior, f'{anterior} (guardado anteriormente)'))
                widget = forms.Select(attrs={**attrs, 'class': 'form-select'}, choices=choices)
            self.fields[nombre] = forms.CharField(
                label=etiqueta, required=False, strip=False,
                max_length=Cliente._meta.get_field(nombre).max_length,
                widget=widget,
            )
        self.fields['direccion_numero'].help_text = 'Puedes escribir 100, 12-B, 100A o S/N.'

    def _coincide_con_guardada(self, campo, enviado):
        valor = self.guardada[campo]
        es_division_chilena = (
            self.guardada['direccion_pais'] == 'CL' and campo in ('direccion_region', 'direccion_comuna')
        )
        if es_division_chilena and enviado and enviado == getattr(self.cliente, campo):
            return True
        # El navegador normaliza los saltos en opciones y los elimina en campos de texto de una línea.
        if es_division_chilena or campo == 'direccion_pais':
            visible = valor.replace('\r\n', '\n').replace('\r', '\n')
        else:
            visible = valor.replace('\r', '').replace('\n', '')
        return enviado in (valor, visible)

    def _validar_texto(self, datos, campo, *, calle=False):
        if datos.get(campo):
            try:
                validar_texto_direccion(datos[campo], admite_calle_numerada=calle)
            except forms.ValidationError as error:
                self.add_error(campo, error)

    def clean(self):
        datos = super().clean()
        for nombre, valor in list(datos.items()):
            if tiene_controles_direccion(valor):
                self.add_error(nombre, forms.ValidationError(
                    'Escribe este dato en una sola línea, sin caracteres de control.', code='control_direccion',
                ))
            else:
                datos[nombre] = valor.strip()
        if self.opcional and not self.errors and not any(datos.values()):
            return datos
        if self.cambio_tipo:
            self.add_error('direccion_region', 'Confirma la ubicación para el país seleccionado.')
        obligatorios = {
            'direccion_pais': 'Selecciona el país o territorio.',
            'direccion_comuna': 'Indica la ciudad o comuna.',
            'direccion_calle': 'Indica la calle, avenida o camino.',
            'direccion_numero': 'Indica el número o escribe S/N.',
        }
        for campo, mensaje in obligatorios.items():
            if not datos.get(campo) and not self.has_error(campo):
                self.add_error(campo, mensaje)
        self._validar_texto(datos, 'direccion_calle', calle=True)
        if datos.get('direccion_numero'):
            try:
                validar_numero_direccion(datos['direccion_numero'])
            except forms.ValidationError as error:
                self.add_error('direccion_numero', error)
        if self.chile:
            region = DPA_CHILE.get(datos.get('direccion_region'))
            if region is None and not self.has_error('direccion_region'):
                self.add_error('direccion_region', 'Selecciona una región de Chile.')
            if region and datos.get('direccion_comuna') not in region['comunas'] and not self.has_error('direccion_comuna'):
                self.add_error('direccion_comuna', 'Selecciona una comuna de la región elegida.')
            postal = datos.get('direccion_codigo_postal')
            if postal and not (len(postal) == 7 and postal.isascii() and postal.isdigit()):
                self.add_error('direccion_codigo_postal', 'El código postal chileno debe tener siete dígitos.')
        else:
            self._validar_texto(datos, 'direccion_region')
            self._validar_texto(datos, 'direccion_comuna')

        if self.errors:
            return datos
        self.cambios = {campo: valor or None for campo, valor in datos.items()}
        misma_ubicacion = all(datos[campo] == self.guardada[campo] for campo in (
            'direccion_pais', 'direccion_region', 'direccion_comuna'
        ))
        if self.chile:
            self.cambios['direccion_region'] = region['nombre']
            self.cambios['direccion_comuna'] = region['comunas'][datos['direccion_comuna']]
            self.cambios['direccion_localidad'] = self.cliente.direccion_localidad if misma_ubicacion else None
        else:
            self.cambios['direccion_localidad'] = self.cambios['direccion_comuna']
            self.cambios['direccion_comuna'] = self.cliente.direccion_comuna if misma_ubicacion else None
        self.cambios['direccion_modo'] = Cliente.ModoDireccion.ESTRUCTURADA
        return datos


class ClienteForm(NombreModeloMixin, forms.ModelForm):
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
    def __init__(self, *args, user=None, actualizacion=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.initial['telefono_pais'] = pais_para_telefono_guardado(self.instance.telefono)
        if actualizacion is not None:
            self.initial.update({campo: actualizacion[campo] for campo in self.fields if campo in actualizacion})
        self.es_alta = self.instance._state.adding
        self.cambios_direccion = {}
        self.direccion_estructurada = DireccionEstructuradaForm(
            self.instance, data=self.data if self.is_bound else None, actualizacion=actualizacion,
        )

    def clean(self):
        datos = super().clean()
        direccion = self.direccion_estructurada
        if direccion.conserva_guardada or direccion.is_valid():
            self.cambios_direccion = direccion.cambios
        elif direccion.requiere_actualizacion:
            self.add_error(None, 'Actualiza la dirección histórica para guardar los cambios de la ficha.')
        else:
            self.add_error(None, 'Revisa los campos de la dirección.')
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
        field_classes = {'nombre': NombreLimitadoField}
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
        rut = normalizar_rut(self.cleaned_data['rut'])
        propietario = self.user.pk if self.user else self.instance.usuario_id
        if not rut or propietario is None:
            return rut

        clave = clave_rut_cliente(rut)
        otros = (Cliente.objects.filter(usuario_id=propietario)
                 .exclude(pk=self.instance.pk).exclude(rut='').values_list('rut', flat=True))
        for guardado in otros.iterator():
            try:
                clave_guardada = clave_rut_cliente(guardado)
            except forms.ValidationError:
                # Las identificaciones históricas ajenas al formato chileno no compiten por un RUT válido.
                continue
            if clave_guardada == clave:
                raise forms.ValidationError(
                    'Ya tienes un cliente registrado con este RUT. Revisa la ficha existente antes de crear otro.',
                    code='duplicado',
                )
        return rut

    def clean_telefono(self):
        pais_inicial = self.initial['telefono_pais']
        pais = self.cleaned_data.get('telefono_pais') or pais_inicial
        if pais == pais_inicial and self._dato_guardado_sin_cambios('telefono'):
            return self.instance.telefono
        return normalizar_telefono(self.cleaned_data['telefono'], pais)
