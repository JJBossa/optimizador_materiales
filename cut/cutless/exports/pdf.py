"""Generacion de reportes PDF."""
import base64
import io
import os
from uuid import uuid4

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from django.conf import settings

from ..packing import normalizar_info_desperdicio
from ..render import _info_desperdicio_desde_optimizacion
from ..pieces import parsear_piezas_desde_texto
from ..units import convertir_desde_cm, obtener_factor_area_desde_cm2, obtener_simbolo_area, obtener_simbolo_unidad

def generar_pdf(optimizacion, imagenes_base64, numero_lista=None, info_desperdicio=None, archivo_salida=None):
    """
    Genera UN SOLO PDF con todos los tableros, cada uno en su propia página.
    
    Args:
        optimizacion: Objeto Optimizacion
        imagenes_base64: Lista de imágenes en base64
        numero_lista: Parámetro legado; el código permanente identifica la exportación.
        archivo_salida: Buffer opcional; evita crear un PDF temporal en MEDIA_ROOT.
        info_desperdicio: Dict igual al tercer retorno de generar_grafico (areas en cm²).
                         Si es None, se regenera desde la optimización guardada (más costoso).
    """
    if isinstance(imagenes_base64, str):
        imagenes_base64 = [imagenes_base64] if imagenes_base64 else []
    
    if not imagenes_base64:
        return None
    
    # Los archivos del servidor comparten almacenamiento entre propietarios.
    filename = f"optimizacion-{optimizacion.pk or uuid4().hex}.pdf"
    filepath = os.path.join(settings.MEDIA_ROOT, "pdfs", filename)
    if archivo_salida is None:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

    c = canvas.Canvas(archivo_salida if archivo_salida is not None else filepath, pagesize=letter)
    width, height = letter

    # === PÁGINA 1: Información general ===
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, height - 50, f"Reporte {optimizacion.codigo} - CutLess")
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, height - 70, "Método: Área decreciente y rectángulos libres")
    if optimizacion.nombre:
        nombre = optimizacion.nombre
        c.setFont('Helvetica', 11)
        while c.stringWidth(nombre, 'Helvetica', 11) > width-100:
            nombre = nombre[:-2] + '…'
        c.drawCentredString(width/2, height-90, nombre)


    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, height - 110, "Información General:")
    c.setFont("Helvetica", 11)
    c.drawString(2.5*cm, height - 130, f"• Usuario: {optimizacion.usuario.username}")
    c.drawString(2.5*cm, height - 145, f"• Fecha: {optimizacion.fecha.strftime('%d/%m/%Y %H:%M')}")
    # Obtener unidad y convertir dimensiones para mostrar
    unidad = getattr(optimizacion, 'unidad_medida', 'cm') or 'cm'
    ancho_mostrar = convertir_desde_cm(optimizacion.ancho_tablero, unidad)
    alto_mostrar = convertir_desde_cm(optimizacion.alto_tablero, unidad)
    simbolo = obtener_simbolo_unidad(unidad)
    
    c.drawString(2.5*cm, height - 160, f"• Dimensiones del tablero: {ancho_mostrar} × {alto_mostrar} {simbolo}")
    c.drawString(2.5*cm, height - 175, f"• Tableros generados: {len(imagenes_base64)}")
    
    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0, 0.5, 0)
    c.drawString(2.5*cm, height - 195, f"• Aprovechamiento: {optimizacion.aprovechamiento_total:.2f}%")
    c.setFillColorRGB(0, 0, 0)
    
    # Información de costos (si existe)
    costo_total = optimizacion.get_costo_total()
    if costo_total or optimizacion.precio_tablero or optimizacion.mano_obra:
        y_pos_costo = height - 220
        c.setFont("Helvetica-Bold", 12)
        c.setFillColorRGB(0, 0.5, 0.8)
        c.drawString(2*cm, y_pos_costo, "Información de Costos:")
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 11)
        y_pos_costo -= 20
        
        if optimizacion.material:
            c.drawString(2.5*cm, y_pos_costo, f"• Material: {optimizacion.material.nombre}")
            y_pos_costo -= 15
        
        if optimizacion.precio_tablero:
            c.drawString(2.5*cm, y_pos_costo, f"• Precio por tablero: ${optimizacion.precio_tablero:,.0f}")
            y_pos_costo -= 15
            if optimizacion.num_tableros:
                costo_material = optimizacion.precio_tablero * optimizacion.num_tableros
                c.drawString(2.5*cm, y_pos_costo, f"• Costo de material ({optimizacion.num_tableros} tableros): ${costo_material:,.0f}")
                y_pos_costo -= 15
        
        if optimizacion.mano_obra:
            c.drawString(2.5*cm, y_pos_costo, f"• Mano de obra: ${optimizacion.mano_obra:,.0f}")
            y_pos_costo -= 15
        
        if costo_total:
            c.setFont("Helvetica-Bold", 12)
            c.setFillColorRGB(0, 0.5, 0)
            c.drawString(2.5*cm, y_pos_costo, f"• COSTO TOTAL: ${costo_total:,.0f}")
            c.setFillColorRGB(0, 0, 0)
            y_pos_costo -= 20
        
        # Ajustar posición inicial de piezas
        height_piezas = y_pos_costo - 10
    else:
        height_piezas = height - 225

    # Encabezado de lista de piezas
    # Tabla de piezas detallada
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, height_piezas, "Lista de Piezas:")
    c.setFont("Helvetica-Bold", 10)
    
    # Encabezados de tabla
    y_pos = height_piezas - 20
    c.drawString(2.5*cm, y_pos, "Cant.")
    c.drawString(4*cm, y_pos, "Nombre")
    c.drawString(9*cm, y_pos, "Dimensiones")
    c.drawString(14*cm, y_pos, "Área unit.")
    c.drawString(17.5*cm, y_pos, "Área total")
    
    # Línea separadora
    y_pos -= 5
    c.line(2*cm, y_pos, width - 2*cm, y_pos)
    y_pos -= 15
    
    c.setFont("Helvetica", 9)
    total_area_piezas = 0
    total_cantidad_piezas = 0
    
    from xml.sax.saxutils import escape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    estilo_pieza = ParagraphStyle('Nombre de pieza', fontName='Helvetica', fontSize=9, leading=11)
    for pieza in parsear_piezas_desde_texto(optimizacion.piezas, optimizacion.unidad_medida, estricto=True):
        nombre = Paragraph(escape(pieza['nombre']).replace('\n', '<br/>'), estilo_pieza)
        _, alto_nombre = nombre.wrap(4.8*cm, height)
        alto_fila = max(15, alto_nombre + 4)
        if y_pos - alto_fila < 120:
            c.showPage()
            y_pos = height - 50
            # Reimprimir encabezados si hay nueva página
            c.setFont("Helvetica-Bold", 10)
            c.drawString(2.5*cm, y_pos, "Cant.")
            c.drawString(4*cm, y_pos, "Nombre")
            c.drawString(9*cm, y_pos, "Dimensiones")
            c.drawString(14*cm, y_pos, "Área unit.")
            c.drawString(17.5*cm, y_pos, "Área total")
            y_pos -= 5
            c.line(2*cm, y_pos, width - 2*cm, y_pos)
            y_pos -= 15
            c.setFont("Helvetica", 9)
        
        cantidad = pieza['cantidad']
        ancho_cm, alto_cm = pieza['ancho_cm'], pieza['alto_cm']
        # Calcular áreas
        area_unit_cm2 = ancho_cm * alto_cm
        area_total_cm2 = area_unit_cm2 * cantidad

        # Convertir para mostrar
        simbolo_area = obtener_simbolo_area(optimizacion.unidad_medida)
        factor_area = obtener_factor_area_desde_cm2(optimizacion.unidad_medida)

        area_unit_mostrar = round(area_unit_cm2 * factor_area, 2)
        area_total_mostrar = round(area_total_cm2 * factor_area, 2)

        ancho_mostrar = convertir_desde_cm(ancho_cm, optimizacion.unidad_medida)
        alto_mostrar = convertir_desde_cm(alto_cm, optimizacion.unidad_medida)

        # Dibujar fila
        c.drawString(2.5*cm, y_pos, str(cantidad))
        nombre.drawOn(c, 4*cm, y_pos + 9 - alto_nombre)
        c.drawString(9*cm, y_pos, f"{ancho_mostrar} × {alto_mostrar} {obtener_simbolo_unidad(optimizacion.unidad_medida)}")
        c.drawString(14*cm, y_pos, f"{area_unit_mostrar} {simbolo_area}")
        c.drawString(17.5*cm, y_pos, f"{area_total_mostrar} {simbolo_area}")

        total_area_piezas += area_total_cm2
        total_cantidad_piezas += cantidad

        y_pos -= alto_fila

    # Resumen de piezas
    y_pos -= 10
    c.line(2*cm, y_pos, width - 2*cm, y_pos)
    y_pos -= 15
    c.setFont("Helvetica-Bold", 10)
    simbolo_area = obtener_simbolo_area(optimizacion.unidad_medida)
    factor_area = obtener_factor_area_desde_cm2(optimizacion.unidad_medida)
    total_area_mostrar = round(total_area_piezas * factor_area, 2)
    c.drawString(17.5*cm, y_pos, f"Total: {total_area_mostrar} {simbolo_area}")
    c.drawString(2.5*cm, y_pos, f"Total piezas: {total_cantidad_piezas}")
    
    # Información de configuración
    y_pos -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2*cm, y_pos, "Configuración de optimización:")
    c.setFont("Helvetica", 9)
    y_pos -= 15
    rotacion_texto = "Sí" if getattr(optimizacion, 'permitir_rotacion', True) else "No"
    c.drawString(2.5*cm, y_pos, f"• Rotación automática: {rotacion_texto}")
    y_pos -= 12
    # El margen de corte se guarda en cm, pero siempre se muestra en mm
    margen_cm = getattr(optimizacion, 'margen_corte', 0.3)
    margen_mm = round(margen_cm * 10, 1)  # Convertir de cm a mm
    c.drawString(2.5*cm, y_pos, f"• Margen de corte (kerf): {margen_mm} mm")
    
    y_pos -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y_pos, "Resumen por Tablero:")
    y_pos -= 15
    c.setFont("Helvetica-Bold", 9)
    c.drawString(2.5*cm, y_pos, "Tablero")
    c.drawString(5*cm, y_pos, "Piezas")
    c.drawString(8*cm, y_pos, "Área usada")
    c.drawString(12*cm, y_pos, "Desperdicio")
    c.drawString(16*cm, y_pos, "% Uso")
    y_pos -= 5
    c.line(2*cm, y_pos, width - 2*cm, y_pos)
    y_pos -= 12
    c.setFont("Helvetica", 9)

    if info_desperdicio is None:
        info_desperdicio = _info_desperdicio_desde_optimizacion(optimizacion) or {}
    else:
        info_desperdicio = normalizar_info_desperdicio(info_desperdicio)
    info_tableros = info_desperdicio.get('info_tableros') or []

    for i in range(len(imagenes_base64)):
        if y_pos < 100:
            c.showPage()
            y_pos = height - 50
        c.drawString(2.5*cm, y_pos, f"Tablero {i+1}")
        if i < len(info_tableros):
            row = info_tableros[i]
            n_p = row.get('num_piezas', 0)
            au = round(float(row['area_usada']) * factor_area, 2)
            dp = round(float(row['desperdicio']) * factor_area, 2)
            pct = row.get('porcentaje_uso')
            c.drawString(5*cm, y_pos, str(n_p))
            c.drawString(8*cm, y_pos, f"{au} {simbolo_area}")
            c.drawString(12*cm, y_pos, f"{dp} {simbolo_area}")
            if pct is not None:
                c.drawString(16*cm, y_pos, f"{float(pct):.2f}%")
            else:
                c.drawString(16*cm, y_pos, "-")
        else:
            for col_x in (5*cm, 8*cm, 12*cm, 16*cm):
                c.drawString(col_x, y_pos, "-")
        y_pos -= 12

    # Los planos usan la misma geometría horizontal que la web. Las imágenes
    # antiguas solo se conservan como respaldo cuando no existe geometría guardada.
    from .board_pdf import dibujar_tablero
    from reportlab.lib.utils import ImageReader
    for i, img_base64 in enumerate(imagenes_base64, start=1):
        c.showPage()
        vista = info_tableros[i-1].get('vista_web') if i <= len(info_tableros) else None
        if vista:
            dibujar_tablero(c, vista, unidad, optimizacion.margen_corte, i,
                            len(imagenes_base64), width, height, info_tableros[i-1], codigo=optimizacion.codigo, nombre=optimizacion.nombre)
        elif img_base64 and not img_base64.isspace():
            image = ImageReader(io.BytesIO(base64.b64decode(img_base64)))
            iw, ih = image.getSize()
            ratio = min((width-80)/iw, (height-120)/ih)
            c.setFont('Helvetica-Bold', 16)
            c.drawCentredString(width/2, height-40, f'Tablero {i} de {len(imagenes_base64)}')
            c.drawImage(image, (width-iw*ratio)/2, (height-ih*ratio)/2,
                        width=iw*ratio, height=ih*ratio, mask='auto')

    # Pie de página final
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.line(2*cm, 1*cm, width - 2*cm, 1*cm)
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 0.7*cm, "CutLess - Optimización de Recursos en Carpintería")
    
    c.save()
    
    if archivo_salida is not None:
        return archivo_salida
    return os.path.join("pdfs", filename)

def generar_pdf_presupuesto(presupuesto, archivo_salida=None):
    """Genera una cotización paginada con el mismo detalle que la vista."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

    if archivo_salida is None:
        archivo_salida = os.path.join(settings.MEDIA_ROOT, 'presupuestos', f'presupuesto_{presupuesto.pk}_{uuid4().hex}.pdf')
        os.makedirs(os.path.dirname(archivo_salida), exist_ok=True)

    doc = SimpleDocTemplate(
        archivo_salida, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.5*cm, bottomMargin=2*cm, title=f'Presupuesto {presupuesto.numero}',
    )
    estilos = getSampleStyleSheet()
    flujo = []

    def parrafo(texto, estilo='BodyText'):
        seguro = escape(str(texto)).replace('\n', '<br/>')
        flujo.append(Paragraph(seguro, estilos[estilo]))

    def encabezado_y_pie(lienzo, documento):
        lienzo.saveState()
        lienzo.setFont('Helvetica-Bold', 10)
        lienzo.setFillColorRGB(0, .3, .6)
        lienzo.drawString(documento.leftMargin, A4[1] - 1.5*cm, f'Presupuesto {presupuesto.numero}')
        lienzo.setFont('Helvetica', 9)
        lienzo.drawRightString(A4[0] - documento.rightMargin, cm, f'CutLess · Página {documento.page}')
        lienzo.restoreState()

    parrafo(f'Presupuesto {presupuesto.numero}', 'Title')
    cliente = presupuesto.cliente_cotizado
    if cliente:
        parrafo(f'Cliente: {cliente.nombre}', 'Heading2')
        for campo, etiqueta in (('rut', 'RUT'), ('email', 'Correo'), ('telefono', 'Teléfono'), ('direccion', 'Dirección')):
            valor = getattr(cliente, campo)
            if valor:
                parrafo(f'{etiqueta}: {valor}')
    else:
        parrafo('Sin cliente asignado', 'Heading2')

    parrafo(f'Fecha de creación: {presupuesto.fecha_creacion:%d/%m/%Y %H:%M}')
    parrafo(f'Válido hasta: {presupuesto.fecha_validez:%d/%m/%Y}')
    parrafo(f'Estado: {presupuesto.get_estado_display()}')
    if presupuesto.es_historico:
        parrafo('Cotización histórica. Se conserva el total emitido y los planes se muestran con sus datos actuales.')

    optimizaciones = presupuesto.lineas_cotizadas
    parrafo(f'Detalles de las optimizaciones ({len(optimizaciones)})', 'Heading2')
    for optimizacion in optimizaciones:
        unidad = optimizacion.unidad_medida or 'cm'
        simbolo = obtener_simbolo_unidad(unidad)
        ancho = convertir_desde_cm(optimizacion.ancho_tablero, unidad)
        alto = convertir_desde_cm(optimizacion.alto_tablero, unidad)
        parrafo(optimizacion.etiqueta, 'Heading3')
        parrafo(f'Dimensiones: {ancho:g} × {alto:g} {simbolo} · Tableros: {optimizacion.num_tableros or 0}')
        parrafo(f'Aprovechamiento: {optimizacion.aprovechamiento_total:.2f}%')
        if optimizacion.material:
            parrafo(f'Material: {optimizacion.material.nombre}')
        for pieza in parsear_piezas_desde_texto(optimizacion.piezas, unidad, estricto=True):
            parrafo(f"{pieza['nombre']}: {pieza['ancho']:g} × {pieza['alto']:g} {simbolo} (×{pieza['cantidad']})")

    if not presupuesto.es_historico:
        parrafo('Desglose de costos', 'Heading2')
        filas = [['Concepto', 'Cantidad', 'Precio unitario', 'Subtotal']]
        for optimizacion in optimizaciones:
            cantidad = optimizacion.num_tableros or 0
            precio = presupuesto.precio_tablero
            filas.append([f'Tableros ({optimizacion.codigo})', cantidad, f'${precio:,.2f}', f'${precio * cantidad:,.2f}'])
        if presupuesto.mano_obra:
            importe = f'${presupuesto.mano_obra:,.2f}'
            filas.append(['Mano de obra', 1, importe, importe])
        if len(filas) > 1:
            tabla = LongTable(filas, colWidths=[6*cm, 2.5*cm, 4*cm, 4*cm], repeatRows=1)
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#315175')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('LINEBELOW', (0, 0), (-1, -1), .25, colors.lightgrey),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            flujo.append(tabla)
            flujo.append(Spacer(1, .4*cm))

    parrafo(f'TOTAL: ${presupuesto.total_vigente:,.2f}', 'Heading2')
    if presupuesto.notas:
        parrafo('Notas', 'Heading3')
        parrafo(presupuesto.notas)
    doc.build(flujo, onFirstPage=encabezado_y_pie, onLaterPages=encabezado_y_pie)
    return archivo_salida


def generar_pdf_resumen_desperdicio(optimizaciones, estadisticas, periodo='todos', archivo_salida=None):
    """
    Genera un PDF con el resumen de desperdicio desde estadísticas.
    
    Args:
        optimizaciones: QuerySet de optimizaciones filtradas
        estadisticas: Diccionario con estadísticas calculadas
        periodo: Período seleccionado (todos, semanal, mensual, anual)
    
    Returns:
        str: Ruta del archivo PDF generado
    """
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from django.utils import timezone
    import os
    from django.conf import settings
    
    filename = f"resumen_desperdicio_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(settings.MEDIA_ROOT, "pdfs", filename)
    if archivo_salida is None:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Retornar path relativo para compatibilidad con FileResponse
    relative_path = os.path.join("pdfs", filename)
    
    c = canvas.Canvas(archivo_salida if archivo_salida is not None else filepath, pagesize=A4)
    width, height = A4
    
    # === PÁGINA 1: RESUMEN ===
    c.setFont("Helvetica-Bold", 18)
    c.setFillColorRGB(0.86, 0.21, 0.27)  # Rojo para desperdicio
    c.drawCentredString(width / 2, height - 50, "📊 RESUMEN DE DESPERDICIO")
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(width / 2, height - 70, "Reporte de Eficiencia - CutLess")
    
    # Período
    periodo_texto = {
        'todos': 'Todos los tiempos',
        'semanal': 'Última semana',
        'mensual': 'Último mes',
        'anual': 'Último año'
    }.get(periodo, 'Todos los tiempos')
    
    c.setFont("Helvetica", 11)
    c.drawString(2*cm, height - 100, f"Período: {periodo_texto}")
    c.drawString(2*cm, height - 115, f"Fecha del reporte: {timezone.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Estadísticas principales
    y_pos = height - 150
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y_pos, "Estadísticas Generales:")
    c.setFont("Helvetica", 11)
    y_pos -= 20
    
    stats = [
        f"Total Optimizaciones: {estadisticas.get('total_optimizaciones', 0)}",
        f"Aprovechamiento Promedio: {estadisticas.get('promedio_aprovechamiento', 0):.2f}%",
        f"Desperdicio Promedio: {estadisticas.get('promedio_desperdicio', 0):.2f}%",
        f"Mejor Aprovechamiento: {estadisticas.get('max_aprovechamiento', 0):.2f}%",
        f"Peor Aprovechamiento: {estadisticas.get('min_aprovechamiento', 0):.2f}%",
    ]
    
    for stat in stats:
        c.drawString(2.5*cm, y_pos, f"• {stat}")
        if 'Desperdicio' in stat:
            c.setFillColorRGB(0.86, 0.21, 0.27)
            c.drawString(2.5*cm, y_pos, f"• {stat}")
            c.setFillColorRGB(0, 0, 0)
        y_pos -= 18
    
    # === PÁGINA 2+: DETALLE ===
    c.showPage()
    
    # Encabezados de tabla
    y_pos = height - 50
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, y_pos, "Detalle de Optimizaciones:")
    y_pos -= 25
    
    # Encabezados de columnas
    headers = ['Código', 'Fecha', 'Dimensiones', 'Aprovech.', 'Desperd.', 'Tableros']
    x_positions = [2*cm, 6*cm, 8.5*cm, 12.5*cm, 15*cm, 17.5*cm]
    
    c.setFont("Helvetica-Bold", 9)
    for header, x_pos in zip(headers, x_positions):
        c.drawString(x_pos, y_pos, header)
    
    y_pos -= 15
    c.setFont("Helvetica", 8)
    
    # Datos
    for opt in optimizaciones.order_by('fecha')[:30]:  # Máximo 30 por página
        if y_pos < 50:
            c.showPage()
            y_pos = height - 50
        
        fecha_str = opt.fecha.strftime('%d/%m/%Y')
        unidad_opt = getattr(opt, 'unidad_medida', 'cm') or 'cm'
        ancho_mostrar = convertir_desde_cm(opt.ancho_tablero, unidad_opt)
        alto_mostrar = convertir_desde_cm(opt.alto_tablero, unidad_opt)
        simbolo = obtener_simbolo_unidad(unidad_opt)
        dim_str = f"{ancho_mostrar}×{alto_mostrar}{simbolo}"
        
        aprovechamiento = opt.aprovechamiento_total or 0
        desperdicio = 100 - aprovechamiento
        num_tableros = opt.num_tableros or 1
        
        c.drawString(x_positions[0], y_pos, opt.codigo)
        c.drawString(x_positions[1], y_pos, fecha_str)
        c.drawString(x_positions[2], y_pos, dim_str)
        c.drawString(x_positions[3], y_pos, f"{aprovechamiento:.1f}%")
        
        # Colorear desperdicio
        if desperdicio > 30:
            c.setFillColorRGB(0.86, 0.21, 0.27)
        elif desperdicio > 15:
            c.setFillColorRGB(1.0, 0.76, 0.03)
        else:
            c.setFillColorRGB(0.13, 0.55, 0.13)
        c.drawString(x_positions[4], y_pos, f"{desperdicio:.1f}%")
        c.setFillColorRGB(0, 0, 0)
        
        c.drawString(x_positions[5], y_pos, str(num_tableros))
        
        y_pos -= 15
    
    # Pie de página
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(width / 2, 30, f"Generado el {timezone.now().strftime('%d/%m/%Y %H:%M')} - CutLess")
    
    c.save()
    return archivo_salida if archivo_salida is not None else relative_path
