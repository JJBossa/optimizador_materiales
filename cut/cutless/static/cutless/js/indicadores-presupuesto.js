(() => {
  const panel = document.querySelector('[data-indicadores-url]');
  if (!panel) return;

  const estado = panel.querySelector('[data-indicadores-estado]');
  const lista = panel.querySelector('.indicadores-presupuesto__datos');
  const formatoClp = new Intl.NumberFormat('es-CL', {
    style: 'currency', currency: 'CLP', currencyDisplay: 'code',
    minimumFractionDigits: 0, maximumFractionDigits: 0,
  });
  const formatoUsd = new Intl.NumberFormat('es-CL', {
    style: 'currency', currency: 'USD', currencyDisplay: 'code',
  });
  const formatoFecha = new Intl.DateTimeFormat('es-CL', {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  });

  function mostrarIndicador(codigo, dato) {
    if (!dato) return;
    const fila = panel.querySelector(`[data-indicador="${codigo}"]`);
    fila.querySelector('[data-valor]').textContent = `≈ ${formatoClp.format(dato.valor)}`;
    const referencia = fila.querySelector('[data-referencia]');
    const fecha = formatoFecha.format(new Date(`${dato.fecha}T00:00:00Z`));
    referencia.dateTime = dato.fecha;
    referencia.textContent = dato.fecha_anterior ? `Dato del ${fecha}` : `Hoy, ${fecha}`;
  }

  async function cargar() {
    estado.textContent = 'Consultando indicadores…';
    try {
      const respuesta = await fetch(panel.dataset.indicadoresUrl, { redirect: 'error' });
      if (!respuesta.ok) throw new Error();
      const { indicadores, desde_cache: desdeCache } = await respuesta.json();
      const { dolar, uf } = indicadores;
      if (!dolar && !uf) throw new Error();
      mostrarIndicador('dolar', dolar);
      mostrarIndicador('uf', uf);

      const conversion = panel.querySelector('[data-indicador="conversion"] [data-valor]');
      if (conversion && dolar) {
        const usd = Number(panel.dataset.totalClp) / dolar.valor;
        if (Number.isFinite(usd)) conversion.textContent = `≈ ${formatoUsd.format(usd)}`;
      }

      lista.hidden = false;
      estado.textContent = desdeCache ? 'Valores en caché.' : '';
    } catch (_) {
      estado.textContent = 'Indicadores no disponibles por el momento.';
    }
  }

  cargar();
})();
