from django import forms
from django.forms.widgets import Script

from .nombres import LongitudHTMLValidator
from .piezas import texto_de_textarea


LIMITE_DESCRIPCION = 150
LONGITUD_DESCRIPCION = LongitudHTMLValidator(LIMITE_DESCRIPCION)


def supera_limite_texto(valor):
    return LONGITUD_DESCRIPCION.clean(texto_de_textarea(valor)) > LIMITE_DESCRIPCION


class TextoLimitadoTextarea(forms.Textarea):
    class Media:
        js = (Script('cutless/js/contador-texto.js', defer=True),)

    def get_context(self, name, value, attrs):
        contexto = super().get_context(name, value, attrs)
        atributos = contexto['widget']['attrs']
        atributos['data-limite-texto'] = LIMITE_DESCRIPCION
        # Un histórico, una copia o un POST rechazado deben poder corregirse progresivamente.
        if not supera_limite_texto(value or ''):
            atributos['maxlength'] = LIMITE_DESCRIPCION
        return contexto


class DescripcionLimitadaField(forms.CharField):
    widget = TextoLimitadoTextarea

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.guardada = None
        ayuda = f'Máximo {LIMITE_DESCRIPCION} caracteres.'
        self.help_text = f'{self.help_text.rstrip(".")}. {ayuda}' if self.help_text else ayuda

    def conservar(self, valor):
        self.guardada = valor
        if supera_limite_texto(valor):
            self.help_text += ' Puedes conservar el texto guardado si no lo modificas.'

    def _conserva_guardada(self, valor):
        return self.guardada is not None and (
            valor is None or texto_de_textarea(valor) == texto_de_textarea(self.guardada)
        )

    def bound_data(self, data, initial):
        # Si un POST parcial falla en otro campo, vuelve a presentar el texto omitido.
        if data is None and self.guardada is not None:
            return self.guardada
        return super().bound_data(data, initial)

    def clean(self, valor):
        if self._conserva_guardada(valor):
            return self.guardada
        texto = texto_de_textarea(valor or '')
        LONGITUD_DESCRIPCION(texto)
        return super().clean(texto)

    def has_changed(self, initial, data):
        if self.guardada is None or self.disabled:
            return super().has_changed(initial, data)
        return not self._conserva_guardada(data) and self.to_python(texto_de_textarea(data)) != self.guardada


class DescripcionModeloMixin:
    campo_descripcion = 'descripcion'

    def __init__(self, *args, conservar_descripcion=True, **kwargs):
        super().__init__(*args, **kwargs)
        if conservar_descripcion and not self.instance._state.adding and self.campo_descripcion in self.fields:
            self.fields[self.campo_descripcion].conservar(getattr(self.instance, self.campo_descripcion))
