from functools import partial

from django.contrib import admin
from django import forms
from django.db.models import Q

from usuarios.views import es_admin

from .forms.materials import MaterialAdminForm
from .forms.nombres import LIMITE_TRABAJO, NombreLimitadoField, NombreModeloMixin
from .forms.numeros import ImporteDecimalField
from .formato_clp import formatear_clp
from .models import Optimizacion, Material


class OptimizacionAdminForm(NombreModeloMixin, forms.ModelForm):
    class Meta:
        model = Optimizacion
        fields = '__all__'
        field_classes = {'nombre': partial(NombreLimitadoField, limite=LIMITE_TRABAJO)}


@admin.register(Optimizacion)
class OptimizacionAdmin(admin.ModelAdmin):
    form = OptimizacionAdminForm
    list_display = ('codigo', 'usuario', 'fecha', 'ancho_tablero', 'alto_tablero', 'aprovechamiento_total', 'costo_total_display')
    search_fields = ('usuario__username',)
    ordering = ('-fecha',)
    list_filter = ('fecha', 'aprovechamiento_total')

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in ('precio_tablero', 'mano_obra'):
            kwargs['form_class'] = ImporteDecimalField
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        return ('usuario', 'codigo') if obj else ()
    
    def costo_total_display(self, obj):
        return formatear_clp(obj.get_costo_total())
    costo_total_display.short_description = "Costo Total"

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    form = MaterialAdminForm
    list_display = ('nombre', 'ancho', 'alto', 'unidad_medida', 'precio_display', 'es_predefinido', 'usuario', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('es_predefinido', 'unidad_medida', 'fecha_creacion')
    ordering = ('-es_predefinido', 'nombre')

    def get_exclude(self, request, obj=None):
        if not request.user.is_superuser:
            return ('usuario', 'es_predefinido')
        return super().get_exclude(request, obj)

    def get_list_display(self, request):
        columnas = super().get_list_display(request)
        if not request.user.is_superuser:
            return tuple(columna for columna in columnas if columna != 'usuario')
        return columnas

    def lookup_allowed(self, lookup, value, request):
        if not request.user.is_superuser and lookup.split('__', 1)[0] in ('usuario', 'usuario_id'):
            return False
        return super().lookup_allowed(lookup, value, request)

    def puede_gestionar(self, request, obj):
        if obj is None or request.user.is_superuser:
            return True
        if obj.es_predefinido:
            return es_admin(request.user)
        return obj.usuario_id == request.user.pk

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self.puede_gestionar(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self.puede_gestionar(request, obj)

    def get_deleted_objects(self, objs, request):
        eliminados, cantidades, permisos, protegidos = super().get_deleted_objects(objs, request)
        if Optimizacion.objects.filter(material__in=objs).exists():
            protegidos.append('La selección incluye materiales asociados a optimizaciones.')
        return eliminados, cantidades, permisos, protegidos

    @admin.display(description='Precio', ordering='precio')
    def precio_display(self, obj):
        return formatear_clp(obj.precio)
    
    def save_model(self, request, obj, form, change):
        if change:
            campos = form.campos_actualizacion()
            if not request.user.is_superuser:
                campos.difference_update(('usuario', 'es_predefinido'))
            obj.save(update_fields=campos)
        else:
            if not request.user.is_superuser:
                obj.usuario = request.user
                obj.es_predefinido = False
            super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Los usuarios normales solo ven sus materiales y los predefinidos
        return qs.filter(Q(usuario=request.user) | Q(es_predefinido=True))
