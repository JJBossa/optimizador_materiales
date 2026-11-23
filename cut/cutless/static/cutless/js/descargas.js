(() => {
  'use strict';

  const agente = navigator.userAgent;
  const esIOS = /iPhone|iPad|iPod/.test(agente)
    || (/Macintosh/.test(agente) && navigator.maxTouchPoints > 1);
  if (esIOS) {
    // Safari en iOS puede mostrar PDF y PNG desde una pestaña iniciada por el toque.
    // La activación nativa también deja que el navegador se encargue de Excel.
    const ayuda = 'cutless-download-ios-help';
    for (const enlace of document.querySelectorAll('a[data-descarga="pdf"], a[data-descarga="png"]')) {
      if (enlace.origin !== location.origin) continue;
      enlace.target = '_blank';
      enlace.relList.add('noopener');
      const descripcion = enlace.getAttribute('aria-describedby');
      enlace.setAttribute('aria-describedby', descripcion ? `${descripcion} ${ayuda}` : ayuda);
    }
    return;
  }

  const mensajes = {
    pdf: 'Generando documento PDF...',
    excel: 'Preparando archivo Excel...',
    png: 'Generando imagen...',
  };
  const errores = {
    401: 'La sesión ha expirado. Inicia sesión y vuelve a solicitar el archivo.',
    403: 'No tienes permiso para descargar este archivo.',
    404: 'El archivo solicitado no está disponible. Actualiza la página y vuelve a intentarlo.',
    422: 'Hay datos del archivo que necesitan revisión antes de exportarlo.',
    500: 'No se pudo preparar el archivo. Intenta descargarlo de nuevo.',
    red: 'Se interrumpió la solicitud. Comprueba la conexión y vuelve a intentarlo.',
    espera: 'No se pudo confirmar la preparación. Revisa las descargas del navegador antes de reintentar.',
    inesperado: 'La respuesta no contiene el archivo solicitado. Actualiza la página y vuelve a intentarlo.',
  };
  const aviso = document.getElementById('cutless-download-error');
  const mensajeError = aviso.querySelector('[data-download-error]');
  const estado = document.getElementById('cutless-download-status');
  const duracionVisualMinima = 420;
  let pendiente;
  let presentacion;

  function limpiarAviso() {
    mensajeError.textContent = '';
    aviso.hidden = true;
  }

  function retirarIndicador(operacion) {
    clearTimeout(operacion.retirada);
    operacion.overlay.remove();
    if (presentacion === operacion) {
      presentacion = null;
      estado.textContent = '';
    }
  }

  function terminar(operacion, resultado) {
    if (pendiente !== operacion) return;
    pendiente = null;
    clearInterval(operacion.sondeo);
    clearTimeout(operacion.limite);
    operacion.enlace.removeAttribute('aria-busy');
    const seguro = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `${operacion.cookie}=; Max-Age=0; Path=/; SameSite=Lax${seguro}`;
    if (resultado === 'preparado') {
      const restante = duracionVisualMinima - (performance.now() - operacion.inicio);
      if (restante > 0 && operacion.overlay.isConnected) {
        // El navegador ya tiene las cabeceras. Solo la presentación continúa.
        const mensaje = 'Archivo preparado.';
        operacion.overlay.classList.add('cutless-loading--prepared');
        operacion.overlay.querySelector('[data-loading-message]').textContent = mensaje;
        estado.textContent = mensaje;
        operacion.retirada = setTimeout(() => retirarIndicador(operacion), restante);
      } else {
        retirarIndicador(operacion);
      }
      return;
    }
    retirarIndicador(operacion);
    if (!resultado) return;
    if (resultado !== 'espera') operacion.marco?.remove();
    aviso.hidden = false;
    mensajeError.textContent = errores[resultado] || errores[500];
  }

  function abrirPestana(operacion, destino) {
    const enlace = document.createElement('a');
    enlace.href = destino.href;
    enlace.target = operacion.enlace.target;
    enlace.rel = operacion.enlace.rel || 'noopener';
    if (document.hidden || !navigator.userActivation?.isActive) {
      enlace.click();
      return;
    }

    // Un fotograma visible antes de cambiar de pestaña, dentro de la activación del clic.
    let abierta = false;
    const abrir = () => {
      if (abierta || pendiente !== operacion) return;
      abierta = true;
      clearTimeout(respaldo);
      enlace.click();
    };
    const respaldo = setTimeout(abrir, 80);
    requestAnimationFrame(() => requestAnimationFrame(abrir));
  }

  aviso.querySelector('button').addEventListener('click', limpiarAviso);
  window.addEventListener('pagehide', () => {
    if (pendiente) terminar(pendiente);
    if (presentacion) retirarIndicador(presentacion);
    limpiarAviso();
  });

  document.addEventListener('click', event => {
    if (!(event.target instanceof Element)) return;
    const enlace = event.target.closest('a[data-descarga]');
    if (!enlace || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey
      || event.shiftKey || event.altKey) return;
    const mensaje = mensajes[enlace.dataset.descarga];
    const destino = new URL(enlace.href);
    if (typeof mensaje !== 'string' || destino.origin !== location.origin
      || !navigator.cookieEnabled || typeof crypto.randomUUID !== 'function') return;

    event.preventDefault();
    if (pendiente || event.detail > 1) return;
    limpiarAviso();
    if (presentacion) retirarIndicador(presentacion);

    const token = crypto.randomUUID().replaceAll('-', '');
    destino.searchParams.set('_cutless_download', token);
    const overlay = window.mostrarIndicadorCarga(mensaje, { autoCerrar: false });
    overlay.setAttribute('aria-hidden', 'true');
    estado.textContent = mensaje;
    enlace.setAttribute('aria-busy', 'true');
    const operacion = { enlace, overlay, cookie: `cutless_descarga_${token}`, inicio: performance.now() };
    pendiente = presentacion = operacion;

    operacion.sondeo = setInterval(() => {
      const prefijo = `${operacion.cookie}=`;
      const respuesta = document.cookie.split('; ').find(cookie => cookie.startsWith(prefijo));
      if (respuesta) terminar(operacion, respuesta.slice(prefijo.length));
    }, 200);
    // Límite de espera para una interrupción sin señal, nunca una confirmación de éxito.
    operacion.limite = setTimeout(() => terminar(operacion, 'espera'), 120000);

    if (enlace.target === '_blank') {
      abrirPestana(operacion, destino);
      return;
    }

    const marco = document.createElement('iframe');
    operacion.marco = marco;
    marco.hidden = true;
    marco.title = 'Descarga de archivo';
    marco.addEventListener('error', () => terminar(operacion, 'red'), { once: true });
    marco.src = destino.href;
    // Conservar el marco tras recibir cabeceras para no interrumpir el cuerpo en curso.
    document.body.appendChild(marco);
  });
})();
