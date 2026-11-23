import re

from django import forms

from ..formatos_numericos import AYUDA_DECIMAL, FORMATO_DECIMAL, FORMATO_ENTERO, preparar_decimal, preparar_importe


class EntradaDecimal:
    widget = forms.TextInput
    default_error_messages = {'invalid': f'Escribe un número válido. {AYUDA_DECIMAL}'}

    def widget_attrs(self, widget):
        return {**super().widget_attrs(widget), 'inputmode': 'decimal', 'pattern': FORMATO_DECIMAL}

    def prepare_value(self, value):
        return super().prepare_value(preparar_decimal(value))

    def to_python(self, value):
        if value in self.empty_values:
            return None
        texto = str(preparar_decimal(value))
        if not re.fullmatch(FORMATO_DECIMAL, texto):
            raise forms.ValidationError(self.error_messages['invalid'], code='invalid')
        return super().to_python(texto.replace(',', '.'))


class DecimalEntradaField(EntradaDecimal, forms.DecimalField):
    pass


class PresentacionImporte:
    def prepare_value(self, value):
        return super().prepare_value(preparar_importe(value))


class ImporteDecimalField(PresentacionImporte, forms.DecimalField):
    pass


class ImporteEntradaField(PresentacionImporte, DecimalEntradaField):
    pass


class MedidaEntradaField(EntradaDecimal, forms.FloatField):
    pass


class CantidadEntradaField(forms.IntegerField):
    widget = forms.TextInput

    def widget_attrs(self, widget):
        return {**super().widget_attrs(widget), 'inputmode': 'numeric', 'pattern': FORMATO_ENTERO}

    def to_python(self, value):
        if value not in self.empty_values and not re.fullmatch(FORMATO_ENTERO, str(value)):
            raise forms.ValidationError(self.error_messages['invalid'], code='invalid')
        return super().to_python(value)
