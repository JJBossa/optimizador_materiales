from django import forms
from django.core.validators import MaxLengthValidator


LIMITE_NOMBRE = 30


class LongitudHTMLValidator(MaxLengthValidator):
    message = 'Usa como máximo %(limit_value)d caracteres (ingresaste %(show_value)d).'

    def clean(self, valor):
        return len(valor.encode('utf-16-le', errors='surrogatepass')) // 2


class NombreLimitadoField(forms.CharField):
    """Aplica el máximo del formulario sin cambiar la capacidad del modelo."""

    def __init__(self, **kwargs):
        # Los ModelForm también pasan el max_length de la columna.
        kwargs.pop('max_length', None)
        super().__init__(**kwargs)
        self.max_length = LIMITE_NOMBRE
        if not self.widget.is_hidden:
            self.widget.attrs['maxlength'] = LIMITE_NOMBRE
        self.validador_longitud = LongitudHTMLValidator(LIMITE_NOMBRE)
        self.validators.append(self.validador_longitud)
        self.help_text = f'{self.help_text} Máximo {LIMITE_NOMBRE} caracteres.'.strip()
        self.nombre_guardado = None

    def supera_limite(self, valor):
        return self.validador_longitud.clean(valor) > self.max_length

    def conservar(self, valor):
        self.nombre_guardado = valor
        if self.supera_limite(valor):
            self.help_text += ' Puedes conservar el nombre guardado. Si lo cambias, respeta el máximo.'

    def conserva_nombre(self, valor):
        if self.nombre_guardado is None:
            return False
        # Los inputs de una línea descartan CR y LF al mostrar el valor guardado.
        valor_visible = self.nombre_guardado.replace('\r', '').replace('\n', '')
        return valor is None or valor in (self.nombre_guardado, valor_visible)

    def clean(self, valor):
        if self.conserva_nombre(valor):
            return self.nombre_guardado
        return super().clean(valor)

    def has_changed(self, initial, data):
        return not self.conserva_nombre(data) and super().has_changed(initial, data)


class NombreModeloMixin:
    campo_nombre = 'nombre'

    def __init__(self, *args, conservar_nombre=True, **kwargs):
        super().__init__(*args, **kwargs)
        if conservar_nombre and not self.instance._state.adding and self.campo_nombre in self.fields:
            self.fields[self.campo_nombre].conservar(getattr(self.instance, self.campo_nombre))
