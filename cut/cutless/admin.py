from django.contrib import admin
from .forms.materials import MaterialAdminForm
from .forms.numeros import ImporteDecimalField
from .formato_clp import formatear_clp
from .models import Optimizacion, Material

@admin.register(Optimizacion)
class OptimizacionAdmin(admin.ModelAdmin):
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

    @admin.display(description='Precio', ordering='precio')
    def precio_display(self, obj):
        return formatear_clp(obj.precio)
    
    def save_model(self, request, obj, form, change):
        if change:
            obj.save(update_fields=form.campos_actualizacion())
        else:
            super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Los usuarios normales solo ven sus materiales y los predefinidos
        return qs.filter(usuario=request.user) | qs.filter(es_predefinido=True)
