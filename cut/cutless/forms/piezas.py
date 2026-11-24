from collections import defaultdict

from django import forms

from .nombres import NombreLimitadoField


def texto_de_textarea(valor):
    return valor.replace('\r\n', '\n').replace('\r', '\n')


class NombresPiezasGuardados:
    """Permite conservar cada aparición del nombre aunque la fila cambie de posición."""

    def __init__(self, piezas=()):
        self.por_texto = defaultdict(list)
        for pieza in piezas:
            nombre = pieza['nombre']
            self.por_texto[texto_de_textarea(nombre)].append(nombre)

    def tomar(self, valor):
        if valor is None:
            return None
        candidatos = self.por_texto.get(texto_de_textarea(valor))
        if candidatos:
            if valor in candidatos:
                candidatos.remove(valor)
                return valor
            return candidatos.pop(0)
        return None


class NombrePiezaField(NombreLimitadoField):
    def conserva_nombre(self, valor):
        return (self.nombre_guardado is not None and valor is not None
                and texto_de_textarea(valor) == texto_de_textarea(self.nombre_guardado))

    def to_python(self, valor):
        return texto_de_textarea(super().to_python(valor))


def validar_nombres_piezas(piezas, guardadas=()):
    nombres_guardados = NombresPiezasGuardados(guardadas)
    campo = NombrePiezaField()
    for fila, pieza in enumerate(piezas, 1):
        nombre = pieza['nombre']
        campo.nombre_guardado = nombres_guardados.tomar(nombre)
        try:
            pieza['nombre'] = campo.clean(nombre)
        except forms.ValidationError as error:
            raise forms.ValidationError([f'Pieza {fila}: {mensaje}' for mensaje in error.messages]) from error


class BasePiezasFormSet(forms.BaseFormSet):
    def __init__(self, *args, piezas_guardadas=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.nombres_guardados = NombresPiezasGuardados(piezas_guardadas)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        if index is not None:
            if self.is_bound:
                nombre = self.data.get(f'{self.add_prefix(index)}-nombre')
            else:
                nombre = self.initial[index]['nombre'] if self.initial and index < len(self.initial) else None
            kwargs['nombre_guardado'] = self.nombres_guardados.tomar(nombre)
        return kwargs
