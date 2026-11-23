from django.contrib import admin

from cutless.forms.numeros import ImporteDecimalField

from .models import PerfilUsuario

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'timeout_sesion', 'tema_preferido', 'fecha_creacion')
    list_filter = ('tema_preferido', 'timeout_sesion')
    search_fields = ('usuario__username', 'usuario__email')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in ('precio_tablero_predeterminado', 'mano_obra_predeterminada'):
            kwargs['form_class'] = ImporteDecimalField
        return super().formfield_for_dbfield(db_field, request, **kwargs)
