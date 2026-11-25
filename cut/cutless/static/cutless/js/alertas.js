(() => {
  const categoriasValidas = ['presupuestos', 'proyectos'];
  const prioridades = ['Alta', 'Media', 'Baja'];

  function textoTotal(total) {
    return `${total} alerta${total === 1 ? ' activa' : 's activas'}`;
  }

  function nombreCampana(total) {
    return total === null ? 'Notificaciones' : `Notificaciones, ${textoTotal(total)}`;
  }

  function urlInterna(url, categoria, origen) {
    if (typeof url !== 'string' || !url.startsWith('/') || url.startsWith('//') || url.includes('\\')) return false;
    try {
      const destino = new URL(url, origen);
      return destino.origin === origen && !destino.search && !destino.hash &&
        new RegExp(`/${categoria}/[1-9][0-9]*/$`).test(destino.pathname);
    } catch (_) {
      return false;
    }
  }

  function respuestaValida(datos, { resumen, pagina, origen }) {
    if (!datos || !Number.isSafeInteger(datos.total) || datos.total < 0 ||
        !datos.categorias || typeof datos.categorias !== 'object' || Array.isArray(datos.categorias)) return false;
    if (!Object.entries(datos.categorias).every(([codigo, etiqueta]) =>
      categoriasValidas.includes(codigo) && typeof etiqueta === 'string')) return false;
    if (resumen) return true;
    return (datos.siguiente === null || datos.siguiente === pagina + 1) && Array.isArray(datos.alertas) &&
      datos.alertas.every(item => item && categoriasValidas.includes(item.categoria) &&
        Object.hasOwn(datos.categorias, item.categoria) && prioridades.includes(item.prioridad) &&
        ['id', 'titulo', 'mensaje', 'icono'].every(campo => typeof item[campo] === 'string') &&
        urlInterna(item.url, item.categoria, origen));
  }

  function iniciar(raiz) {
    const buscar = nombre => raiz.querySelector(`[data-alertas-${nombre}]`);
    const boton = buscar('boton');
    const contador = buscar('contador');
    const panel = raiz.querySelector('#panel-alertas');
    const lista = buscar('lista');
    const mensaje = buscar('mensaje');
    const totalPanel = buscar('total');
    const mas = buscar('mas');
    const reintento = buscar('reintentar');
    const enlaceSesion = buscar('sesion');
    const filtros = [...raiz.querySelectorAll('[data-alertas-filtro]')];
    let categoria = '';
    let siguiente = null;
    let pendiente = null;
    let expirada = false;
    const ids = new Set();

    function contar(total) {
      contador.hidden = !total;
      contador.textContent = total > 99 ? '99+' : total || '';
      boton.setAttribute('aria-label', nombreCampana(total));
      totalPanel.textContent = total === null ? '' : textoTotal(total);
    }

    function vaciar() {
      ids.clear();
      lista.replaceChildren();
      siguiente = null;
      mas.hidden = true;
    }

    function expirar() {
      expirada = true;
      pendiente?.abort();
      pendiente = null;
      vaciar();
      contar(null);
      reintento.hidden = true;
      filtros.forEach(filtro => { filtro.hidden = true; });
      enlaceSesion.hidden = false;
      mensaje.textContent = 'Tu sesión expiró. Vuelve a iniciar sesión.';
    }

    function nodo(etiqueta, clase, texto) {
      const elemento = document.createElement(etiqueta);
      if (clase) elemento.className = clase;
      if (texto) elemento.textContent = texto;
      return elemento;
    }

    function mostrarItem(aviso) {
      const prioridad = aviso.prioridad.toLowerCase();
      const item = nodo('li', `alertas-item alerta-${prioridad}`);
      const enlace = nodo('a');
      enlace.href = aviso.url;
      const icono = nodo('span', 'alertas-icono', aviso.icono);
      icono.setAttribute('aria-hidden', 'true');
      const cuerpo = nodo('span');
      cuerpo.append(nodo('span', 'alertas-prioridad', `Prioridad ${prioridad}`),
        nodo('strong', '', aviso.titulo), nodo('span', 'alertas-detalle', aviso.mensaje));
      enlace.append(icono, cuerpo);
      item.append(enlace);
      lista.append(item);
      return enlace;
    }

    async function consultar({ resumen = false, pagina = 1 } = {}) {
      if (expirada) return;
      pendiente?.abort();
      const carga = new AbortController();
      pendiente = carga;
      const url = new URL(raiz.dataset.endpoint, location.origin);
      const moverFoco = !resumen && [reintento, mas].includes(document.activeElement);
      if (resumen) url.searchParams.set('resumen', '1');
      else {
        url.searchParams.set('categoria', categoria);
        url.searchParams.set('pagina', pagina);
        if (pagina === 1) vaciar();
        mensaje.textContent = 'Cargando alertas…';
        reintento.hidden = true;
        mas.hidden = true;
      }
      try {
        const respuesta = await fetch(url, {
          signal: carga.signal, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
        });
        if (pendiente !== carga) return;
        if (respuesta.status === 401) {
          expirar();
          if (moverFoco && !panel.hidden) enlaceSesion.focus();
          return;
        }
        if (!respuesta.ok) throw new Error();
        const datos = await respuesta.json();
        if (pendiente !== carga) return;
        if (!respuestaValida(datos, { resumen, pagina, origen: location.origin })) throw new Error();
        if (!Object.keys(datos.categorias).length) {
          vaciar();
          contar(null);
          raiz.hidden = true;
          return;
        }

        contar(datos.total);
        filtros.forEach(filtro => {
          const codigo = filtro.dataset.alertasFiltro;
          filtro.hidden = Boolean(codigo) && !Object.hasOwn(datos.categorias, codigo);
        });
        if (resumen || panel.hidden) return;
        let primero;
        for (const aviso of datos.alertas) {
          if (ids.has(aviso.id)) continue;
          ids.add(aviso.id);
          const enlace = mostrarItem(aviso);
          primero ||= enlace;
        }
        mensaje.textContent = ids.size ? '' : 'No tienes alertas pendientes.';
        siguiente = datos.siguiente;
        mas.hidden = siguiente === null;
        if (moverFoco) (primero || (mas.hidden ? boton : mas)).focus();
      } catch (_) {
        if (pendiente !== carga || carga.signal.aborted) return;
        if (!resumen && !panel.hidden) {
          vaciar();
          mensaje.textContent = 'No se pudieron cargar las alertas. Intenta nuevamente.';
          reintento.hidden = false;
          if (moverFoco) reintento.focus();
        }
      }
    }

    function cerrar({ restaurarFoco = false } = {}) {
      panel.hidden = true;
      boton.setAttribute('aria-expanded', 'false');
      vaciar();
      if (restaurarFoco) boton.focus();
    }

    boton.addEventListener('click', () => {
      if (!panel.hidden) {
        cerrar();
        return;
      }
      panel.hidden = false;
      boton.setAttribute('aria-expanded', 'true');
      consultar();
    });
    buscar('cerrar').addEventListener('click', () => cerrar({ restaurarFoco: true }));
    document.addEventListener('keydown', evento => {
      if (evento.key === 'Escape' && !panel.hidden) {
        evento.preventDefault();
        evento.stopPropagation();
        cerrar({ restaurarFoco: true });
      }
    }, true);
    document.addEventListener('click', evento => {
      if (!panel.hidden && !raiz.contains(evento.target)) cerrar();
    });
    document.addEventListener('cutless:sesion-expirada', expirar);
    window.addEventListener('pagehide', () => {
      pendiente?.abort();
      pendiente = null;
      cerrar();
      contar(null);
    });
    window.addEventListener('pageshow', evento => {
      if (evento.persisted) consultar({ resumen: true });
    });
    filtros.forEach(filtro => filtro.addEventListener('click', () => {
      categoria = filtro.dataset.alertasFiltro;
      filtros.forEach(opcion => opcion.setAttribute('aria-pressed', String(opcion === filtro)));
      consultar();
    }));
    reintento.addEventListener('click', () => consultar());
    mas.addEventListener('click', () => consultar({ pagina: siguiente }));
    buscar('alternativa').hidden = true;
    boton.hidden = false;
    consultar({ resumen: true });
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { nombreCampana, respuestaValida };
  } else {
    document.querySelectorAll('[data-alertas]').forEach(iniciar);
  }
})();
