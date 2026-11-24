from django.contrib.auth.management.commands.createsuperuser import Command as DjangoCommand
from django.core.exceptions import ValidationError

from usuarios.forms import NombreUsuarioField


class Command(DjangoCommand):
    def _validate_username(self, username, verbose_field_name, database):
        try:
            nombre = NombreUsuarioField().clean(username)
        except ValidationError as error:
            return ' '.join(error.messages)
        return (
            super()._validate_username(username, verbose_field_name, database)
            or (super()._validate_username(nombre, verbose_field_name, database) if nombre != username else None)
        )
