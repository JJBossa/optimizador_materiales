(() => {
  'use strict';

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
  let pendiente;

  function limpiarAviso() {
    mensajeError.textContent = '';
    aviso.hidden = true;
  }

  function terminar(operacion, resultado) {
    if (pendiente !== operacion) return;
    pendiente = null;
    clearInterval(operacion.sondeo);
    clearTimeout(operacion.limite);
    operacion.overlay.remove();
    operacion.enlace.removeAttribute('aria-busy');
    estado.textContent = '';
    const seguro = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `${operacion.cookie}=; Max-Age=0; Path=/; SameSite=Lax${seguro}`;
    if (!resultado || resultado === 'preparado') return;
    if (resultado !== 'espera') operacion.marco?.remove();
    aviso.hidden = false;
    mensajeError.textContent = errores[resultado] || errores[500];
  }

  aviso.querySelector('button').addEventListener('click', limpiarAviso);
  window.addEventListener('pagehide', () => {
    if (pendiente) terminar(pendiente);
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

    const token = crypto.randomUUID().replaceAll('-', '');
    destino.searchParams.set('_cutless_download', token);
    const overlay = window.mostrarIndicadorCarga(mensaje, { autoCerrar: false });
    overlay.setAttribute('aria-hidden', 'true');
    estado.textContent = mensaje;
    enlace.setAttribute('aria-busy', 'true');
    const operacion = { enlace, overlay, cookie: `cutless_descarga_${token}` };
    pendiente = operacion;

    operacion.sondeo = setInterval(() => {
      const prefijo = `${operacion.cookie}=`;
      const respuesta = document.cookie.split('; ').find(cookie => cookie.startsWith(prefijo));
      if (respuesta) terminar(operacion, respuesta.slice(prefijo.length));
    }, 200);
    // Límite de espera para una interrupción sin señal, nunca una confirmación de éxito.
    operacion.limite = setTimeout(() => terminar(operacion, 'espera'), 120000);

    if (enlace.target === '_blank') {
      const destinoNativo = document.createElement('a');
      destinoNativo.href = destino.href;
      destinoNativo.target = enlace.target;
      destinoNativo.rel = enlace.rel || 'noopener';
      destinoNativo.click();
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
