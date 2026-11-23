(() => {
  const bloque = document.querySelector('[data-cliente-telefono]');
  if (!bloque) return;

  const pais = bloque.querySelector('select');
  const busqueda = bloque.querySelector('[data-busqueda-pais]');
  const filtro = busqueda.querySelector('input');
  const estado = busqueda.querySelector('[role="status"]');
  const normalizar = texto => texto.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
  const opciones = Array.from(pais.options, opcion => ({
    opcion,
    texto: normalizar(`${opcion.textContent} ${opcion.value}`),
  }));

  filtro.addEventListener('input', () => {
    const texto = normalizar(filtro.value.trim());
    const seleccionado = pais.value;
    const visibles = [];
    let coincidencias = 0;
    for (const { opcion, texto: etiqueta } of opciones) {
      const coincide = opcion.value && etiqueta.includes(texto);
      if (coincide) coincidencias += 1;
      if (!texto || coincide || opcion.value === seleccionado) visibles.push(opcion);
    }
    pais.replaceChildren(...visibles);
    pais.value = seleccionado;
    estado.textContent = texto ? `${coincidencias} ${coincidencias === 1 ? 'coincidencia' : 'coincidencias'}.` : '';
  });

  filtro.addEventListener('keydown', evento => {
    if (evento.key === 'Enter') {
      evento.preventDefault();
      pais.focus();
    }
  });
  busqueda.hidden = false;
})();
