from collections import Counter
import re

from django.db import models, router, transaction
from django.db.models import Q
from django.contrib.auth.models import User
from decimal import Decimal
from types import SimpleNamespace
from django.utils.functional import cached_property
from .direcciones import NOMBRES_PAISES
from .units import UNIDADES_CHOICES as OPCIONES_UNIDAD

class Material(models.Model):
    """
    Modelo para gestionar tipos de tableros/materiales disponibles.
    Permite crear catálogo de materiales con precios.
    """
    UNIDADES_CHOICES = OPCIONES_UNIDAD
    
    usuario = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text="Usuario propietario. Null para materiales predefinidos del sistema."
    )
    nombre = models.CharField(max_length=100, help_text="Nombre del material (ej: MDF 18mm, Contrachapado)")
    ancho = models.FloatField(help_text="Ancho del tablero en cm")
    alto = models.FloatField(help_text="Alto del tablero en cm")
    unidad_medida = models.CharField(
        max_length=2, 
        choices=UNIDADES_CHOICES, 
        default='cm',
        help_text="Unidad de medida para mostrar"
    )
    precio = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Precio por tablero (opcional)"
    )
    es_predefinido = models.BooleanField(
        default=False,
        help_text="Si es True, es un material del sistema (no se puede eliminar)"
    )
    descripcion = models.TextField(blank=True, help_text="Descripción adicional del material")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materiales"
        ordering = ['-es_predefinido', 'nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.ancho}×{self.alto} {self.get_unidad_medida_display()})"
    
    def get_area(self):
        """Retorna el área del tablero en cm²"""
        return self.ancho * self.alto

class ContadorOptimizacion(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    siguiente = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(siguiente__gt=0), name='opt_contador_positivo')]


def _reservar_correlativos(cantidades, using):
    """Reserva un rango por usuario dentro de la transacción que inserta los planes."""
    inicios = {}
    contadores = ContadorOptimizacion.objects.using(using).select_for_update()
    # Un mismo orden de bloqueo evita interbloqueos entre lotes con usuarios en común.
    for usuario_id, cantidad in sorted(cantidades.items()):
        contador, _ = contadores.get_or_create(usuario_id=usuario_id)
        inicios[usuario_id] = contador.siguiente
        contador.siguiente += cantidad
        contador.save(using=using, update_fields=['siguiente'])
    return inicios


_CAMPOS_PERMANENTES = frozenset({'usuario', 'usuario_id', 'correlativo'})


class OptimizacionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if _CAMPOS_PERMANENTES.intersection(kwargs):
            raise ValueError('El propietario y el correlativo de una optimización son permanentes.')
        return super().update(**kwargs)

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False,
                    update_fields=None, unique_fields=None):
        if ignore_conflicts or update_conflicts:
            raise ValueError('La creación de optimizaciones por lotes no admite omitir ni sobrescribir conflictos.')
        objs = list(objs)
        if not objs:
            return objs
        if any(obj.usuario_id is None for obj in objs):
            raise ValueError('Cada optimización debe tener un propietario guardado.')
        self._for_write = True
        using = self.db
        with transaction.atomic(using=using):
            inicios = _reservar_correlativos(Counter(obj.usuario_id for obj in objs), using)
            for obj in objs:
                obj.correlativo = inicios[obj.usuario_id]
                inicios[obj.usuario_id] += 1
            return super().bulk_create(objs, batch_size=batch_size, update_fields=update_fields,
                                       unique_fields=unique_fields)

    def buscar_referencia(self, texto, *, admite_numero=False):
        """Busca el código dentro del conjunto de optimizaciones del propietario."""
        referencia = texto.rsplit(' · ', 1)[-1] if admite_numero else texto
        codigo = re.fullmatch(r'OPT-([0-9]+)', referencia, flags=re.I)
        numero = codigo[1] if codigo else texto if admite_numero and re.fullmatch(r'[0-9]+', texto) else ''
        numero = numero.lstrip('0')
        correlativo = int(numero) if 0 < len(numero) <= 19 else 0
        valido = 0 < correlativo <= 9223372036854775807
        if codigo:
            return self.filter(correlativo=correlativo) if valido else self.none()
        filtro = Q(nombre__icontains=texto) | Q(piezas__icontains=texto)
        if valido:
            filtro |= Q(correlativo=correlativo)
        return self.filter(filtro)


class Optimizacion(models.Model):
    objects = OptimizacionQuerySet.as_manager()
    nombre = models.CharField(max_length=100, blank=True, default='',
        help_text='Nombre opcional del trabajo; no sustituye su código permanente.')

    @property
    def etiqueta(self):
        return f'{self.nombre} · {self.codigo}' if self.nombre else self.codigo

    @property
    def codigo(self):
        """Código visible del propietario, independiente de la clave primaria."""
        return f'OPT-{self.correlativo:04d}' if self.correlativo is not None else ''

    UNIDADES_CHOICES = OPCIONES_UNIDAD
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    correlativo = models.PositiveBigIntegerField(editable=False)
    fecha = models.DateTimeField(auto_now_add=True)
    ancho_tablero = models.FloatField()  # Siempre guardado en cm (permite decimales)
    alto_tablero = models.FloatField()  # Siempre guardado en cm (permite decimales)
    unidad_medida = models.CharField(max_length=2, choices=UNIDADES_CHOICES, default='cm', 
                                     help_text="Unidad de medida usada por el usuario")
    piezas = models.TextField(help_text="Listado de piezas en formato ancho,alto,cantidad")
    imagen = models.ImageField(upload_to='optimizaciones/', null=True, blank=True)
    pdf = models.FileField(upload_to='pdfs/', null=True, blank=True)
    aprovechamiento_total = models.FloatField(default=0)
    # Campo legado para evitar errores de integridad en la BD
    favorito = models.BooleanField(default=False)
    # Nuevos campos para rotación y margen de corte
    permitir_rotacion = models.BooleanField(default=True, help_text="Permitir rotación automática de piezas 90°")
    margen_corte = models.FloatField(default=0.3, help_text="Margen de corte (kerf) en cm (guardado internamente). El valor se ingresa en mm.")
    
    # Campos para sistema de costos
    material = models.ForeignKey(
        Material, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Material/tablero utilizado (opcional)"
    )
    precio_tablero = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Precio por tablero usado en esta optimización"
    )
    mano_obra = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Costo de mano de obra (opcional)"
    )
    num_tableros = models.IntegerField(
        default=0,
        help_text="Número de tableros utilizados (calculado automáticamente)"
    )
    area_usada_total = models.FloatField(
        null=True,
        blank=True,
        help_text="Área total utilizada en cm² (snapshot al generar resultado)"
    )
    desperdicio_total = models.FloatField(
        null=True,
        blank=True,
        help_text="Desperdicio total en cm² (snapshot al generar resultado)"
    )
    resultado_generado = models.BooleanField(
        default=False,
        help_text="Indica si las imágenes y estadísticas del resultado están persistidas"
    )
    resultado_generado_en = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que se persistió el resultado completo"
    )
    resultado_extra = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadatos extra del resultado (piezas no colocadas, totales, etc.)"
    )

    def __str__(self):
        return f"{self.etiqueta} · {self.fecha.strftime('%d/%m/%Y %H:%M')}"
    
    def calcular_costo_total(self):
        """
        Calcula el costo total de la optimización.
        Fórmula: (num_tableros × precio_tablero) + mano_obra
        """
        if self.precio_tablero is None:
            return None
        
        costo_material = Decimal(str(self.num_tableros)) * self.precio_tablero
        costo_total = costo_material + self.mano_obra
        return costo_total
    
    def get_costo_total(self):
        """Retorna el costo total formateado o None"""
        costo = self.calcular_costo_total()
        if costo is None:
            return None
        return costo
    
    # Campos para asociación con cliente y proyecto (Fase 2)
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Cliente asociado a esta optimización (opcional)"
    )
    proyecto = models.ForeignKey(
        'Proyecto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Proyecto al que pertenece esta optimización (opcional)"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'correlativo'], name='opt_correlativo_usuario_unico'),
            models.CheckConstraint(condition=Q(correlativo__gt=0), name='opt_correlativo_positivo'),
        ]

    def save(self, *, force_insert=False, force_update=False, using=None, update_fields=None):
        using = using or router.db_for_write(type(self), instance=self)
        if self._state.adding or self.pk is None:
            if force_update or update_fields is not None:
                raise ValueError('Una optimización nueva debe guardarse completa.')
            if self.usuario_id is None:
                raise ValueError('La optimización debe tener un propietario guardado.')
            with transaction.atomic(using=using):
                self.correlativo = _reservar_correlativos({self.usuario_id: 1}, using)[self.usuario_id]
                super().save(force_insert=True, using=using)
            return

        if update_fields is None:
            guardado = type(self).objects.using(using).values_list('usuario_id', 'correlativo').get(pk=self.pk)
            if guardado != (self.usuario_id, self.correlativo):
                raise ValueError('El propietario y el correlativo de una optimización son permanentes.')
        else:
            update_fields = frozenset(update_fields)
            if _CAMPOS_PERMANENTES.intersection(update_fields):
                raise ValueError('El propietario y el correlativo de una optimización son permanentes.')
        # Una instancia desactualizada no puede reinsertar un código borrado.
        super().save(force_insert=force_insert, force_update=not force_insert, using=using, update_fields=update_fields)


class TableroOptimizacion(models.Model):
    """Imagen y estadísticas de un tablero dentro de una optimización."""
    optimizacion = models.ForeignKey(
        Optimizacion,
        on_delete=models.CASCADE,
        related_name='tableros',
    )
    numero = models.PositiveSmallIntegerField()
    imagen = models.ImageField(upload_to='optimizaciones/tableros/')
    area_usada = models.FloatField(help_text="Área usada en cm²")
    desperdicio = models.FloatField(help_text="Desperdicio en cm²")
    porcentaje_uso = models.FloatField(help_text="Porcentaje de aprovechamiento del tablero")
    num_piezas = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Tablero de optimización"
        verbose_name_plural = "Tableros de optimización"
        ordering = ['numero']
        unique_together = [['optimizacion', 'numero']]

    def __str__(self):
        return f"Tablero {self.numero} — {self.optimizacion.codigo}"


class Cliente(models.Model):
    """
    Modelo para gestionar clientes del usuario.
    """
    class ModoDireccion(models.TextChoices):
        LEGADO = 'legado', 'Legado'
        ESTRUCTURADA = 'estructurada', 'Estructurada'
        SIN_DATO = 'sin_dato', 'Sin dirección activa'

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Usuario propietario del cliente")
    nombre = models.CharField(max_length=200, help_text="Nombre completo o razón social")
    rut = models.CharField(max_length=20, blank=True, help_text="RUT o identificación fiscal")
    email = models.EmailField(blank=True, help_text="Correo electrónico")
    telefono = models.CharField(max_length=20, blank=True, help_text="Teléfono de contacto")
    direccion = models.TextField(blank=True, help_text="Dirección completa")
    direccion_legada_editada = models.TextField(null=True, blank=True)
    direccion_modo = models.CharField(max_length=12, choices=ModoDireccion.choices, null=True, blank=True)
    direccion_pais = models.CharField(max_length=2, null=True, blank=True)
    direccion_calle = models.CharField(max_length=160, null=True, blank=True)
    direccion_numero = models.CharField(max_length=32, null=True, blank=True)
    direccion_unidad = models.CharField(max_length=64, null=True, blank=True)
    direccion_region = models.CharField(max_length=120, null=True, blank=True)
    direccion_comuna = models.CharField(max_length=120, null=True, blank=True)
    direccion_localidad = models.CharField(max_length=120, null=True, blank=True)
    direccion_referencia = models.CharField(max_length=240, null=True, blank=True)
    notas = models.TextField(blank=True, help_text="Notas adicionales sobre el cliente")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']
        unique_together = [['usuario', 'nombre']]  # Un usuario no puede tener dos clientes con el mismo nombre
    
    def __str__(self):
        return self.nombre
    
    @property
    def direccion_legada(self):
        if self.direccion_legada_editada is not None:
            return self.direccion_legada_editada
        return self.direccion

    @property
    def direccion_activa(self):
        if self.direccion_modo == self.ModoDireccion.SIN_DATO:
            return ''
        if self.direccion_modo != self.ModoDireccion.ESTRUCTURADA:
            return self.direccion_legada

        calle = ' '.join(filter(None, (self.direccion_calle, self.direccion_numero)))
        localidad = self.direccion_localidad
        if localidad and self.direccion_comuna and localidad.casefold() == self.direccion_comuna.casefold():
            localidad = None
        ubicacion = ', '.join(filter(None, (localidad, self.direccion_comuna, self.direccion_region)))
        pais = NOMBRES_PAISES.get(self.direccion_pais) if self.direccion_pais != 'CL' else None
        return ', '.join(filter(None, (calle, self.direccion_unidad, ubicacion, pais)))

    def get_total_optimizaciones(self):
        """Retorna el número total de optimizaciones para este cliente"""
        return self.optimizacion_set.count()
    
    def get_total_costo(self):
        """Retorna el costo total de todas las optimizaciones del cliente"""
        optimizaciones = self.optimizacion_set.all()
        total = Decimal('0.00')
        for opt in optimizaciones:
            costo = opt.get_costo_total()
            if costo:
                total += costo
        return total


class Proyecto(models.Model):
    """
    Modelo para agrupar múltiples optimizaciones en un proyecto.
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Usuario propietario del proyecto")
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Cliente asociado al proyecto (opcional)"
    )
    nombre = models.CharField(max_length=200, help_text="Nombre del proyecto")
    descripcion = models.TextField(blank=True, help_text="Descripción del proyecto")
    fecha_inicio = models.DateField(null=True, blank=True, help_text="Fecha de inicio del proyecto")
    fecha_fin = models.DateField(null=True, blank=True, help_text="Fecha de finalización estimada")
    estado = models.CharField(
        max_length=20,
        choices=[
            ('planificacion', 'Planificación'),
            ('en_proceso', 'En Proceso'),
            ('completado', 'Completado'),
            ('cancelado', 'Cancelado'),
        ],
        default='planificacion',
        help_text="Estado actual del proyecto"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return self.nombre
    
    def get_total_optimizaciones(self):
        """Retorna el número total de optimizaciones en el proyecto"""
        return self.optimizacion_set.count()
    
    def get_total_costo(self):
        """Retorna el costo total del proyecto"""
        optimizaciones = self.optimizacion_set.all()
        total = Decimal('0.00')
        for opt in optimizaciones:
            costo = opt.get_costo_total()
            if costo:
                total += costo
        return total


class Presupuesto(models.Model):
    """
    Modelo para generar presupuestos/cotizaciones profesionales.
    """
    ESTADOS_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviado', 'Enviado'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
        ('vencido', 'Vencido'),
    ]
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="Usuario propietario del presupuesto"
    )
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Proyecto asociado (opcional)"
    )
    optimizaciones = models.ManyToManyField(
        Optimizacion,
        related_name='presupuestos',
        help_text="Optimizaciones asociadas al presupuesto"
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Cliente al que se envía el presupuesto"
    )
    numero = models.CharField(
        max_length=50,
        help_text="Número del presupuesto, único por usuario (ej: PRE-2025-0001)"
    )
    precio_tablero = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Precio por tablero usado en el presupuesto"
    )
    mano_obra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Costo de mano de obra"
    )
    costo_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Costo total del presupuesto"
    )
    fecha_validez = models.DateField(help_text="Fecha hasta la cual el presupuesto es válido")
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_CHOICES,
        default='borrador',
        help_text="Estado del presupuesto"
    )
    detalle_emitido = models.JSONField(null=True, blank=True, editable=False)
    notas = models.TextField(blank=True, help_text="Notas adicionales para el cliente")
    pdf = models.FileField(upload_to='presupuestos/', null=True, blank=True, help_text="PDF generado del presupuesto")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Presupuesto"
        verbose_name_plural = "Presupuestos"
        ordering = ['-fecha_creacion']
        unique_together = [['usuario', 'numero']]
    
    def __str__(self):
        return f"Presupuesto {self.numero} - {self.cliente.nombre if self.cliente else 'Sin cliente'}"
    
    def esta_vencido(self):
        """Verifica si el presupuesto está vencido"""
        from django.utils import timezone
        return timezone.now().date() > self.fecha_validez
    
    @cached_property
    def lineas_cotizadas(self):
        if self.detalle_emitido is None:
            return list(self.optimizaciones.all())
        return [
            SimpleNamespace(**{**linea, 'material': SimpleNamespace(nombre=linea['material']) if linea['material'] else None})
            for linea in self.detalle_emitido['optimizaciones']
        ]

    @property
    def cliente_cotizado(self):
        if self.detalle_emitido is None:
            return self.cliente
        cliente = self.detalle_emitido['cliente']
        return SimpleNamespace(**cliente) if cliente else None

    @property
    def es_historico(self):
        return self.estado != 'borrador' and self.detalle_emitido is None

    @property
    def direccion_cotizada(self):
        cliente = self.cliente_cotizado
        if cliente is None:
            return ''
        if self.detalle_emitido is not None:
            return getattr(cliente, 'direccion', '')
        if self.es_historico:
            return cliente.direccion_legada
        return cliente.direccion_activa

    @property
    def total_vigente(self):
        return self.calcular_costo_total_multiple() if self.estado == 'borrador' else self.costo_total

    def get_total_optimizaciones(self):
        return len(self.lineas_cotizadas)

    def calcular_costo_total_multiple(self):
        return self.precio_tablero * self.get_total_tableros() + self.mano_obra

    def get_total_tableros(self):
        return sum(opt.num_tableros or 0 for opt in self.lineas_cotizadas)

    def cerrar_detalle(self):
        """Conserva el cálculo y los datos de presentación al emitir el presupuesto."""
        if self.detalle_emitido is not None:
            return
        cliente = self.cliente
        campos = ('pk', 'codigo', 'etiqueta', 'ancho_tablero', 'alto_tablero',
                  'unidad_medida', 'aprovechamiento_total', 'num_tableros', 'piezas')
        lineas = [
            {**{campo: getattr(opt, campo) for campo in campos},
             'material': opt.material.nombre if opt.material else None}
            for opt in self.lineas_cotizadas
        ]
        self.detalle_emitido = {
            'optimizaciones': lineas,
            'cliente': ({
                'nombre': cliente.nombre,
                'rut': cliente.rut,
                'email': cliente.email,
                'telefono': cliente.telefono,
                'direccion': cliente.direccion_activa,
            } if cliente else None),
        }

    @staticmethod
    def generar_numero_presupuesto(usuario=None):
        """
        Genera un número de presupuesto en formato PRE-YYYY-NNNN.
        La secuencia es independiente por usuario.
        Ejemplo: PRE-2025-0001
        """
        from django.utils import timezone

        prefijo = f'PRE-{timezone.localdate().year}-'
        presupuestos = Presupuesto.objects.filter(numero__startswith=prefijo)
        if usuario is not None:
            presupuestos = presupuestos.filter(usuario=usuario)
        sufijos = (numero[len(prefijo):] for numero in presupuestos.values_list('numero', flat=True).iterator())
        mayor = max((int(sufijo) for sufijo in sufijos if sufijo.isascii() and sufijo.isdecimal()), default=0)
        return f'{prefijo}{mayor + 1:04d}'



class Plantilla(models.Model):
    """
    Modelo para guardar optimizaciones como plantillas reutilizables.
    Fase 4: Plantillas Avanzadas
    """
    CATEGORIAS_CHOICES = [
        ('cocina', 'Cocina'),
        ('muebles', 'Muebles'),
        ('puertas', 'Puertas'),
        ('ventanas', 'Ventanas'),
        ('estantes', 'Estantes'),
        ('otros', 'Otros'),
    ]
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Usuario propietario. Null para plantillas predefinidas del sistema."
    )
    nombre = models.CharField(max_length=200, help_text="Nombre de la plantilla")
    descripcion = models.TextField(blank=True, help_text="Descripción de la plantilla")
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIAS_CHOICES,
        default='otros',
        help_text="Categoría de la plantilla"
    )
    ancho_tablero = models.FloatField(help_text="Ancho del tablero en cm")
    alto_tablero = models.FloatField(help_text="Alto del tablero en cm")
    unidad_medida = models.CharField(
        max_length=2,
        choices=Material.UNIDADES_CHOICES,
        default='cm',
        help_text="Unidad de medida"
    )
    piezas = models.TextField(help_text="Listado de piezas en formato nombre,ancho,alto,cantidad")
    permitir_rotacion = models.BooleanField(default=True, help_text="Permitir rotación automática")
    margen_corte = models.FloatField(default=0.3, help_text="Margen de corte en cm")
    es_predefinida = models.BooleanField(
        default=False,
        help_text="Si es True, es una plantilla del sistema (no se puede eliminar)"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Plantilla"
        verbose_name_plural = "Plantillas"
        ordering = ['-es_predefinida', 'categoria', 'nombre']
        unique_together = [['usuario', 'nombre']]  # Un usuario no puede tener dos plantillas con el mismo nombre
    
    def __str__(self):
        return self.nombre
    
    def get_piezas_list(self):
        """Retorna la lista de piezas parseada"""
        from .utils import parsear_piezas_desde_texto
        return [
            {
                'nombre': p['nombre'],
                'ancho': p['ancho'],
                'alto': p['alto'],
                'cantidad': p['cantidad'],
            }
            for p in parsear_piezas_desde_texto(self.piezas)
        ]
