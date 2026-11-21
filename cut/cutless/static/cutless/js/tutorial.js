/* Intro.js 7.2.0 comparte capas del documento entre sus instancias. */
(() => {
  'use strict';

  const ventana = window.visualViewport;
  const compacta = matchMedia('(max-width: 600px)');
  let activa = null;
  let operaciones = Promise.resolve();
  let ultimaApertura = 0;

  function visible(elemento) {
    return elemento instanceof HTMLElement && elemento.isConnected &&
      elemento !== document.body && elemento.getClientRects().length > 0 &&
      getComputedStyle(elemento).visibility === 'visible' &&
      !elemento.closest('[inert], [aria-hidden="true"]');
  }

  function encolar(operacion) {
    operaciones = operaciones.then(operacion).catch(error => {
      console.error('No se pudo mostrar la ayuda de CutLess.', error);
      void window.cutlessAlerta?.({ titulo: 'Ayuda', mensaje: 'Vuelve a abrir la ayuda para intentarlo de nuevo.' });
    });
    return operaciones;
  }

  function ocultarPaneles() {
    const bootstrap = window.bootstrap;
    if (!bootstrap) return Promise.resolve();
    const bienvenida = document.querySelector('#modalBienvenida');
    const menu = document.querySelector('#navbarNav');
    return Promise.all([
      ocultar(bienvenida, bootstrap.Modal, 'modal', bienvenida?.getClientRects().length > 0),
      ocultar(menu, bootstrap.Collapse, 'collapse', document.documentElement.classList.contains('mobile-nav-open'))
    ]);
  }

  function ocultar(elemento, componente, tipo, abierto) {
    if (!abierto) return Promise.resolve();
    const panel = componente.getInstance(elemento);
    if (!panel) return Promise.resolve();
    return new Promise(resolve => {
      const alMostrar = () => panel.hide();
      elemento.addEventListener(`shown.bs.${tipo}`, alMostrar, { once: true });
      elemento.addEventListener(`hidden.bs.${tipo}`, () => {
        elemento.removeEventListener(`shown.bs.${tipo}`, alMostrar);
        resolve();
      }, { once: true });
      panel.hide();
    });
  }

  function limpiar(sesion, restaurarFoco) {
    if (activa !== sesion) return;
    // La fábrica conserva cada instancia en su registro. Liberar solo la propia.
    if (sesion.registro) delete window.introJs.instances[sesion.registro];
    activa = null;
    document.body.classList.remove('tutorial-running');
    if (restaurarFoco) {
      const origen = visible(sesion.origen) ? sesion.origen :
        document.querySelector('[data-bs-target="#navbarNav"]');
      if (visible(origen)) origen.focus({ preventScroll: true });
    }
  }

  function esperarRetiro(sesion) {
    const capa = sesion.capa;
    if (!capa?.isConnected) return Promise.resolve();
    // exit() termina antes de que Intro.js retire la capa tras el fundido.
    return new Promise(resolve => {
      const observador = new MutationObserver(() => {
        if (capa.isConnected) return;
        observador.disconnect();
        resolve();
      });
      observador.observe(capa.parentNode, { childList: true });
    });
  }

  async function cerrar(sesion, restaurarFoco = true) {
    if (activa !== sesion || !sesion) return;
    // v7.2.0 difiere el repintado 350 ms y exit() no cancela ese temporizador.
    window.clearTimeout(sesion.guia._lastShowElementTimer);
    try {
      await sesion.guia.exit(true);
      await esperarRetiro(sesion);
    } finally {
      limpiar(sesion, restaurarFoco);
    }
  }

  function avanzar(sesion, anterior) {
    return encolar(async () => {
      if (activa !== sesion || !visible(sesion.cuadro)) return;
      try {
        if (anterior) await sesion.guia.previousStep();
        else await sesion.guia.nextStep();
      } catch (error) {
        await cerrar(sesion);
        throw error;
      }
      if (sesion.terminada) {
        await esperarRetiro(sesion);
        limpiar(sesion, true);
        sesion.alCompletar?.();
      }
    });
  }

  function ajustarVentana() {
    const cuadro = activa?.cuadro;
    if (!cuadro || !ventana) return;
    cuadro.style.setProperty('--ayuda-izquierda-visible', `${ventana.offsetLeft}px`);
    cuadro.style.setProperty('--ayuda-ancho-visible', `${ventana.width}px`);
    cuadro.style.setProperty('--ayuda-alto-visible', `${ventana.height}px`);
    cuadro.style.setProperty('--ayuda-borde-inferior-visible', `${ventana.offsetTop + ventana.height}px`);
  }

  function prepararCuadro(sesion) {
    if (activa !== sesion) return;
    const cuadro = document.querySelector('.introjs-tooltip.customTooltip');
    if (!cuadro) return;
    sesion.cuadro = cuadro;
    sesion.capa = document.querySelector('body > .introjs-helperLayer');
    const titulo = cuadro.querySelector('.introjs-tooltip-title');
    const texto = cuadro.querySelector('.introjs-tooltiptext');
    titulo.id = 'cutless-ayuda-titulo';
    texto.id = 'cutless-ayuda-texto';
    texto.tabIndex = 0;
    cuadro.setAttribute('role', 'dialog');
    cuadro.setAttribute('aria-modal', 'true');
    cuadro.setAttribute('aria-labelledby', titulo.id);
    cuadro.setAttribute('aria-describedby', texto.id);
    const cerrarBoton = cuadro.querySelector('.introjs-skipbutton');
    const siguiente = cuadro.querySelector('.introjs-nextbutton');
    const anterior = cuadro.querySelector('.introjs-prevbutton');
    cerrarBoton.setAttribute('aria-label', 'Cerrar ayuda');
    cerrarBoton.title = 'Cerrar ayuda';
    cerrarBoton.onclick = () => { void encolar(() => cerrar(sesion)); };
    siguiente.onclick = () => { void avanzar(sesion, false); };
    if (anterior) {
      const desactivado = anterior.classList.contains('introjs-disabled');
      anterior.setAttribute('aria-disabled', String(desactivado));
      anterior.tabIndex = desactivado ? -1 : 0;
      anterior.onclick = () => { void avanzar(sesion, true); };
    }
    ajustarVentana();
    if (visible(cuadro)) siguiente.focus({ preventScroll: true });
  }

  window.mostrarGuia = (pasos, alCompletar = null, origen = document.activeElement) => {
    const solicitud = ++ultimaApertura;
    if (activa?.cuadro?.contains(origen)) origen = activa.origen;
    return encolar(async () => {
      if (solicitud !== ultimaApertura) return;
      await cerrar(activa, false);
      await ocultarPaneles();
      if (solicitud !== ultimaApertura) return;
      if (typeof window.introJs !== 'function') {
        void window.cutlessAlerta?.({ titulo: 'Ayuda', mensaje: 'La ayuda interactiva no está disponible en este momento.' });
        return;
      }
      const visibles = pasos.filter(paso => !('element' in paso) || visible(paso.element));
      if (!visibles.length) {
        visibles.push({
          title: 'Ayuda',
          intro: 'No hay controles disponibles para guiar en esta pantalla. Puedes volver a Inicio para preparar un corte o a Historial para consultar los anteriores.'
        });
      }
      const guia = window.introJs().setOptions({
        steps: visibles, showProgress: true, showBullets: false,
        exitOnOverlayClick: false, keyboardNavigation: false, disableInteraction: true,
        nextLabel: 'Siguiente', prevLabel: 'Anterior', skipLabel: '×', doneLabel: 'Finalizar',
        tooltipClass: 'customTooltip', highlightClass: 'customHighlight',
        scrollPadding: 24, scrollToElement: true, scrollTo: compacta.matches ? 'element' : 'tooltip',
        positionPrecedence: ['bottom', 'top', 'left', 'right']
      });
      const instancias = window.introJs.instances;
      const registro = Object.keys(instancias).find(clave => instancias[clave] === guia);
      const sesion = { guia, registro, origen, alCompletar };
      activa = sesion;
      document.body.classList.add('tutorial-running');
      guia.onafterchange(() => prepararCuadro(sesion));
      guia.oncomplete(() => { sesion.terminada = true; });
      try {
        await guia.start();
        if (!sesion.cuadro) throw new Error('Intro.js no creó el cuadro de ayuda.');
      } catch (error) {
        await cerrar(sesion);
        throw error;
      }
    });
  };

  document.addEventListener('keydown', event => {
    const sesion = activa;
    if (!sesion) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      void encolar(() => cerrar(sesion));
    } else if (event.key === 'Tab') {
      event.preventDefault();
      const controles = [...(sesion.cuadro?.querySelectorAll('[tabindex="0"]') ?? [])].filter(visible);
      if (!controles.length) return;
      const actual = controles.indexOf(document.activeElement);
      const paso = event.shiftKey ? -1 : 1;
      const destino = actual < 0 ? (event.shiftKey ? controles.length - 1 : 0) :
        (actual + paso + controles.length) % controles.length;
      controles[destino].focus({ preventScroll: true });
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      void avanzar(sesion, event.key === 'ArrowLeft');
    } else if ((event.key === 'Enter' || event.key === ' ') &&
      sesion.cuadro?.contains(event.target) && event.target.matches('[role="button"]')) {
      event.preventDefault();
      event.target.click();
    }
  });

  ventana?.addEventListener('resize', ajustarVentana);
  ventana?.addEventListener('scroll', ajustarVentana);
  window.addEventListener('pagehide', () => {
    ++ultimaApertura;
    void encolar(() => cerrar(activa, false));
  });
})();
