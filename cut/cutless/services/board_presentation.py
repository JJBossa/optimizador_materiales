"""Datos de presentación derivados; nunca modifica la distribución guardada."""
from cutless.packing import reserva_sierra
from cutless.units import convertir_desde_cm


def preparar_plano_horizontal(vista, unidad, margen):
    if not vista:
        return None
    ancho, alto = float(vista['ancho']), float(vista['alto'])
    girar = alto > ancho
    width, height = (alto, ancho) if girar else (ancho, alto)
    catalogo = {p['numero']: p for p in vista['catalogo']}
    piezas = []
    reservas = []
    for original in vista['piezas']:
        p = dict(original)
        x, y, w, h = (float(p[k]) for k in ('x', 'y', 'ancho', 'alto'))
        ancho_reserva, alto_reserva = reserva_sierra(w, h, x, y, ancho, alto, margen or 0)
        if girar:
            reservas.append((alto-y-alto_reserva, x, alto_reserva, ancho_reserva))
            x, y, w, h = alto-y-h, x, h, w
        else:
            reservas.append((x, y, ancho_reserva, alto_reserva))
        tipo = catalogo[p['numero']]
        medidas = f"{convertir_desde_cm(tipo['ancho'], unidad):g} × {convertir_desde_cm(tipo['alto'], unidad):g} {unidad}"
        p.update(x=x, y=y, ancho=w, alto=h, cx=x+w/2, cy=y+h/2,
                 medida_ancho=convertir_desde_cm(tipo['ancho'], unidad),
                 medida_alto=convertir_desde_cm(tipo['alto'], unidad),
                 texto=min(h/5, w/(max(8, len(p['nombre']), len(medidas))*.65), height*.035))
        # No reducir toda la descripción hasta volverla ilegible. En piezas
        # pequeñas, una referencia mayor enlaza con el detalle de la tabla.
        p['texto_detallado'] = p['texto'] >= width*.008
        p['texto_referencia'] = min(h*.32, w/max(3, len(str(p['numero']))+2), height*.035)
        piezas.append(p)
    # La reserva se calcula antes de girar, en los mismos lados que usa el motor.
    cortes = sorted({0., width, *[x for x, _, _, _ in reservas], *[x+w for x, _, w, _ in reservas]})
    libres = []
    for left, right in zip(cortes, cortes[1:]):
        middle = (left+right)/2
        ocupados = sorted((y, y+h) for x, y, w, h in reservas if x < middle < x+w)
        cursor = 0.
        gaps = []
        for start, end in ocupados:
            if start > cursor+1e-7:
                gaps.append((cursor, start))
            cursor = max(cursor, end)
        if cursor < height-1e-7:
            gaps.append((cursor, height))
        for top, bottom in gaps:
            anterior = next((r for r in libres if abs(r['x']+r['ancho']-left)<1e-7 and abs(r['y']-top)<1e-7 and abs(r['alto']-(bottom-top))<1e-7), None)
            if anterior:
                anterior['ancho'] = right-anterior['x']
            else:
                libres.append(dict(x=left, y=top, ancho=right-left, alto=bottom-top))
    sobrantes = []
    for r in libres:
        if min(r['ancho'], r['alto']) <= 1e-7:
            continue
        r.update(cx=r['x']+r['ancho']/2, cy=r['y']+r['alto']/2,
                 medida_ancho=convertir_desde_cm(r['ancho'], unidad),
                 medida_alto=convertir_desde_cm(r['alto'], unidad),
                 texto=min(r['alto']/4, r['ancho']/18, height*.03))
        r['mostrar_texto'] = r['texto'] >= width*.008 and min(r['ancho'], r['alto']) >= height*.1
        sobrantes.append(r)
    area_sobrante = sum(r['ancho'] * r['alto'] for r in sobrantes)
    area_piezas = sum(p['ancho'] * p['alto'] for p in piezas)
    area_reservada_sierra = max(0., width * height - area_sobrante - area_piezas)
    pad = height*.14
    return dict(ancho=width, alto=height, piezas=piezas, sobrantes=sobrantes,
                area_reservada_sierra_cm2=area_reservada_sierra, area_sobrante_cm2=area_sobrante,
                cota_ancho=convertir_desde_cm(width, unidad), cota_alto=convertir_desde_cm(height, unidad),
                centro_x=width/2, centro_y=height/2, pad=pad, cota=-pad*.45,
                origen=-pad, vista_ancho=width+pad*1.5, vista_alto=height+pad*1.5,
                texto_cota=height*.035)
