"""Alertas vigentes de gestión, calculadas en lectura para un solo propietario."""
from datetime import timedelta

from django.db.models import Case, F, Q, Value, When
from django.urls import reverse

from ..models import Presupuesto, Proyecto
from ..permissions import usuario_tiene_permiso
from .calendario import fecha_comercial
from .presupuestos import ESTADOS_VENCIBLES, presupuestos_por_vencer
from .proyectos import finales_planificados, inicios_planificados, proyectos_atrasados


DIAS_PROXIMOS = 3
DIAS_VENCIDOS = 7
TAMANO_PAGINA = 10
CATEGORIAS = {'presupuestos': 'Presupuestos', 'proyectos': 'Proyectos'}
PERMISOS = {
    'presupuestos': 'puede_crear_presupuestos',
    'proyectos': 'puede_crear_proyectos',
}
TIPOS = {
    'presupuesto_vencido': (0, 'Presupuesto vencido'),
    'presupuesto_vence_hoy': (0, 'Presupuesto vence hoy'),
    'presupuesto_proximo_vencer': (1, 'Presupuesto próximo a vencer'),
    'presupuesto_pendiente_envio': (2, 'Presupuesto pendiente de envío'),
    'proyecto_atrasado': (0, 'Proyecto atrasado'),
    'proyecto_finaliza_hoy': (0, 'Proyecto finaliza hoy'),
    'proyecto_inicio_pendiente': (0, 'Proyecto pendiente de inicio'),
    'proyecto_inicia_hoy': (1, 'Proyecto inicia hoy'),
    'proyecto_proximo_finalizar': (1, 'Proyecto próximo a finalizar'),
}
PRIORIDADES = (('Alta', '!'), ('Media', '◷'), ('Baja', '•'))


def categorias_disponibles(usuario):
    if not usuario.is_authenticated or not getattr(getattr(usuario, 'perfil', None), 'notificaciones_pantalla', False):
        return {}
    return {
        categoria: etiqueta for categoria, etiqueta in CATEGORIAS.items()
        if usuario_tiene_permiso(usuario, PERMISOS[categoria])
    }


def _presupuestos(usuario, hoy, proximos):
    propios = Presupuesto.objects.filter(usuario=usuario).order_by()
    sin_sincronizar = presupuestos_por_vencer(propios, antes_de=hoy)
    vencidos = Q(fecha_validez__gte=hoy - timedelta(days=DIAS_VENCIDOS), fecha_validez__lt=hoy) & (
        Q(estado='vencido') | Q(pk__in=sin_sincronizar.values('pk'))
    )
    por_vencer = Q(estado__in=ESTADOS_VENCIBLES, fecha_validez__range=(hoy, proximos))
    sin_envio = Q(estado='emitido', fecha_validez__gt=proximos)
    return propios.filter(vencidos | por_vencer | sin_envio).annotate(
        tipo=Case(
            When(fecha_validez__lt=hoy, then=Value('presupuesto_vencido')),
            When(fecha_validez=hoy, then=Value('presupuesto_vence_hoy')),
            When(fecha_validez__lte=proximos, then=Value('presupuesto_proximo_vencer')),
            default=Value('presupuesto_pendiente_envio'),
        ),
        referencia=F('numero'), fecha=F('fecha_validez'),
    )


def _proyectos(usuario, hoy, proximos):
    propios = Proyecto.objects.filter(usuario=usuario).order_by()
    atrasados = proyectos_atrasados(propios, hoy=hoy)
    inicios = inicios_planificados(propios, hasta=hoy)
    finales = finales_planificados(propios, desde=hoy, hasta=proximos)
    return propios.filter(
        Q(pk__in=atrasados.values('pk')) | Q(pk__in=inicios.values('pk')) | Q(pk__in=finales.values('pk'))
    ).annotate(
        tipo=Case(
            When(fecha_fin__lt=hoy, then=Value('proyecto_atrasado')),
            When(fecha_fin=hoy, then=Value('proyecto_finaliza_hoy')),
            When(estado='planificacion', fecha_inicio__lt=hoy, then=Value('proyecto_inicio_pendiente')),
            When(estado='planificacion', fecha_inicio=hoy, then=Value('proyecto_inicia_hoy')),
            default=Value('proyecto_proximo_finalizar'),
        ),
        referencia=F('nombre'),
        fecha=Case(
            When(tipo__in=('proyecto_inicio_pendiente', 'proyecto_inicia_hoy'), then=F('fecha_inicio')),
            default=F('fecha_fin'),
        ),
    )


def _filas(candidatos, categoria):
    altas = tuple(tipo for tipo, (orden, _) in TIPOS.items() if orden == 0)
    medias = tuple(tipo for tipo, (orden, _) in TIPOS.items() if orden == 1)
    return candidatos.annotate(
        categoria=Value(categoria), registro=F('pk'),
        orden=Case(When(tipo__in=altas, then=Value(0)), When(tipo__in=medias, then=Value(1)), default=Value(2)),
    ).values('orden', 'fecha', 'categoria', 'registro', 'tipo', 'referencia')


def _alerta(fila, hoy):
    tipo, referencia, fecha = fila['tipo'], fila['referencia'], fila['fecha']
    categoria, registro = fila['categoria'], fila['registro']
    orden, titulo = TIPOS[tipo]
    prioridad, icono = PRIORIDADES[orden]
    dias = (fecha - hoy).days
    plazo = 'mañana' if dias == 1 else f'en {dias} días'
    dia = fecha.strftime('%d/%m/%Y')
    mensajes = {
        'presupuesto_vencido': f'El presupuesto {referencia} está vencido. Su validez terminaba el {dia}.',
        'presupuesto_vence_hoy': f'El presupuesto {referencia} vence hoy.',
        'presupuesto_proximo_vencer': f'El presupuesto {referencia} vence {plazo}.',
        'presupuesto_pendiente_envio': f'El presupuesto {referencia} está pendiente de envío.',
        'proyecto_atrasado': f'El proyecto {referencia} está atrasado. Su finalización estaba prevista para el {dia}.',
        'proyecto_finaliza_hoy': f'El proyecto {referencia} tiene programada su finalización para hoy.',
        'proyecto_inicio_pendiente': f'El proyecto {referencia} tenía previsto iniciar el {dia} y sigue en Planificación.',
        'proyecto_inicia_hoy': f'El proyecto {referencia} tiene programado su inicio para hoy.',
        'proyecto_proximo_finalizar': f'El proyecto {referencia} tiene programada su finalización {plazo}.',
    }
    ruta = 'detalle_presupuesto' if categoria == 'presupuestos' else 'detalle_proyecto'
    return {
        'id': f'{categoria}:{registro}', 'tipo': tipo, 'categoria': categoria, 'prioridad': prioridad,
        'titulo': titulo, 'mensaje': mensajes[tipo], 'fecha': fecha, 'referencia': referencia,
        'url': reverse(f'cutless:{ruta}', args=[registro]), 'icono': icono,
    }


def obtener_alertas(usuario, *, categoria='', pagina=1, solo_total=False):
    categorias = categorias_disponibles(usuario)
    hoy = fecha_comercial()
    proximos = hoy + timedelta(days=DIAS_PROXIMOS)
    consultas = {}
    if 'presupuestos' in categorias:
        consultas['presupuestos'] = _presupuestos(usuario, hoy, proximos)
    if 'proyectos' in categorias:
        consultas['proyectos'] = _proyectos(usuario, hoy, proximos)
    # El total siempre abarca todo el espacio autorizado, incluso con filtro y paginación.
    respuesta = {'total': sum(qs.count() for qs in consultas.values()), 'categorias': categorias}
    if solo_total:
        return respuesta

    seleccion = [_filas(qs, clave) for clave, qs in consultas.items() if not categoria or categoria == clave]
    filas = []
    if seleccion:
        conjunto = seleccion[0].union(*seleccion[1:], all=True) if len(seleccion) > 1 else seleccion[0]
        inicio = (pagina - 1) * TAMANO_PAGINA
        filas = list(conjunto.order_by('orden', 'fecha', 'categoria', 'registro')[inicio:inicio + TAMANO_PAGINA + 1])
    return {
        **respuesta, 'alertas': [_alerta(fila, hoy) for fila in filas[:TAMANO_PAGINA]],
        'siguiente': pagina + 1 if len(filas) > TAMANO_PAGINA else None,
    }
