(() => {
  const normalizar = texto => texto.normalize('NFD').replace(/\p{M}/gu, '').trim().toLowerCase();

  function buscar(opciones, texto, admitePrefijo) {
    const consulta = normalizar(texto);
    if (!consulta) return opciones;
    if (/^\+?\d+$/.test(consulta)) {
      return admitePrefijo ? opciones.filter(opcion => opcion.prefijo === consulta.replace(/^\+/, '')) : [];
    }
    const exacta = opciones.find(opcion => normalizar(opcion.codigo) === consulta);
    const coincidencias = opciones.filter(opcion => opcion.codigo && opcion !== exacta &&
      normalizar(opcion.etiqueta).includes(consulta));
    return exacta ? [exacta, ...coincidencias] : coincidencias;
  }

  function iniciar(bloque) {
    const selector = bloque.querySelector('select');
    const etiqueta = selector?.labels?.[0];
    if (!selector?.id || !etiqueta || !selector.options.length || selector.hidden ||
        selector.disabled || selector.multiple) return;

    const opciones = Array.from(selector.options).filter(opcion => !opcion.disabled).map(opcion => ({
      codigo: opcion.value,
      etiqueta: opcion.text,
      prefijo: opcion.text.match(/\(\+(\d+)\)$/)?.[1],
    }));
    const admitePrefijo = bloque.dataset.selectorPais === 'telefono';
    const interfaz = document.createElement('div');
    const controles = document.createElement('div');
    const entrada = document.createElement('input');
    const abrirLista = document.createElement('button');
    const lista = document.createElement('div');
    const estado = document.createElement('div');

    controles.className = 'input-group';
    entrada.id = `busqueda-${selector.id}`;
    entrada.type = 'text';
    entrada.autocomplete = 'off';
    entrada.spellcheck = false;
    entrada.className = 'form-control';
    entrada.placeholder = opciones.find(opcion => !opcion.codigo)?.etiqueta ?? '';
    entrada.setAttribute('role', 'combobox');
    entrada.setAttribute('aria-autocomplete', 'list');
    entrada.setAttribute('aria-expanded', 'false');
    for (const atributo of ['aria-describedby', 'aria-invalid', 'aria-errormessage']) {
      if (selector.hasAttribute(atributo)) entrada.setAttribute(atributo, selector.getAttribute(atributo));
    }
    abrirLista.type = 'button';
    abrirLista.className = 'btn btn-outline-secondary selector-pais-abrir';
    abrirLista.tabIndex = -1;
    abrirLista.setAttribute('aria-label', 'Mostrar países o territorios');
    lista.id = `${entrada.id}-opciones`;
    lista.className = 'selector-pais-lista';
    lista.hidden = true;
    lista.setAttribute('role', 'listbox');
    lista.setAttribute('aria-label', etiqueta.textContent.trim());
    entrada.setAttribute('aria-controls', lista.id);
    estado.setAttribute('role', 'status');
    estado.className = 'visually-hidden';
    controles.append(entrada, abrirLista);
    interfaz.append(controles, lista, estado);

    let abierta = false;
    let activa = -1;
    let visibles = [];
    const mostrarConfirmada = () => {
      entrada.value = selector.value ? selector.selectedOptions[0]?.text ?? '' : '';
    };

    function cerrar() {
      abierta = false;
      activa = -1;
      lista.hidden = true;
      lista.replaceChildren();
      estado.className = 'visually-hidden';
      estado.textContent = '';
      entrada.setAttribute('aria-expanded', 'false');
      entrada.removeAttribute('aria-activedescendant');
      mostrarConfirmada();
    }

    function activar(indice) {
      activa = indice;
      if (indice < 0) {
        entrada.removeAttribute('aria-activedescendant');
        return;
      }
      const opcion = lista.children[indice];
      for (const elemento of lista.children) {
        elemento.setAttribute('aria-selected', String(elemento === opcion));
      }
      entrada.setAttribute('aria-activedescendant', opcion.id);
      const superior = opcion.offsetTop;
      const inferior = superior + opcion.offsetHeight;
      if (superior < lista.scrollTop) lista.scrollTop = superior;
      else if (inferior > lista.scrollTop + lista.clientHeight) lista.scrollTop = inferior - lista.clientHeight;
    }

    function mostrar(texto) {
      abierta = true;
      visibles = buscar(opciones, texto, admitePrefijo);
      lista.replaceChildren(...visibles.map((dato, indice) => {
        const opcion = document.createElement('div');
        opcion.id = `${lista.id}-${indice}`;
        opcion.dataset.indice = indice;
        opcion.setAttribute('role', 'option');
        opcion.setAttribute('aria-selected', String(dato.codigo === selector.value));
        opcion.textContent = dato.etiqueta;
        return opcion;
      }));
      lista.hidden = false;
      lista.scrollTop = 0;
      activar(-1);
      entrada.setAttribute('aria-expanded', 'true');
      estado.className = visibles.length ? 'visually-hidden' : 'selector-pais-sin-resultados';
      estado.textContent = visibles.length ?
        `${visibles.length} ${visibles.length === 1 ? 'coincidencia' : 'coincidencias'}.` :
        'No hay coincidencias.';
    }

    function confirmar(indice) {
      const codigo = visibles[indice].codigo;
      const cambio = selector.value !== codigo;
      if (cambio) selector.value = codigo;
      cerrar();
      entrada.focus({ preventScroll: true });
      if (cambio) selector.dispatchEvent(new Event('change', { bubbles: true }));
    }

    entrada.addEventListener('focus', () => entrada.select());
    entrada.addEventListener('click', () => {
      if (!abierta) {
        entrada.select();
        mostrar('');
      }
    });
    abrirLista.addEventListener('mousedown', evento => evento.preventDefault());
    abrirLista.addEventListener('click', () => {
      entrada.focus();
      if (abierta) cerrar();
      else {
        entrada.select();
        mostrar('');
      }
    });
    entrada.addEventListener('input', evento => {
      if (!evento.isComposing) mostrar(entrada.value);
    });
    entrada.addEventListener('change', evento => evento.stopPropagation());
    entrada.addEventListener('compositionend', () => mostrar(entrada.value));
    entrada.addEventListener('blur', cerrar);
    entrada.addEventListener('keydown', evento => {
      if (evento.isComposing) return;
      switch (evento.key) {
        case 'ArrowDown':
        case 'ArrowUp':
          evento.preventDefault();
          if (!abierta) mostrar('');
          if (visibles.length) {
            const abajo = evento.key === 'ArrowDown';
            activar(abajo ? Math.min(activa + 1, visibles.length - 1) :
              (activa < 0 ? visibles.length - 1 : Math.max(activa - 1, 0)));
          }
          break;
        case 'Enter':
          evento.preventDefault();
          if (abierta && activa >= 0) confirmar(activa);
          else if (!abierta) mostrar('');
          break;
        case 'Escape':
          if (abierta) {
            evento.preventDefault();
            cerrar();
          }
          break;
        case 'Tab':
          cerrar();
          break;
      }
    });

    // Las opciones son no tabulables y el foco permanece en el combobox.
    lista.addEventListener('mousedown', evento => evento.preventDefault());
    lista.addEventListener('click', evento => {
      const opcion = evento.target.closest('[data-indice]');
      if (opcion) confirmar(Number(opcion.dataset.indice));
    });
    selector.addEventListener('change', cerrar);

    mostrarConfirmada();
    selector.after(interfaz);
    etiqueta.htmlFor = entrada.id;
    selector.hidden = true;
  }

  if (typeof module === 'object' && module.exports) module.exports = { buscar, iniciar };
  if (typeof document !== 'undefined') document.querySelectorAll('[data-selector-pais]').forEach(iniciar);
})();
