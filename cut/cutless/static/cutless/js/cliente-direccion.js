(() => {
  const bloque = document.querySelector('[data-cliente-direccion]');
  if (!bloque) return;

  const catalogo = JSON.parse(document.getElementById('catalogo-chile-direcciones').textContent);
  const pais = bloque.querySelector('#id_direccion_pais');
  const origen = bloque.querySelector('[name=ubicacion_pais]');
  const orden = new Intl.Collator('es-CL');
  let region = bloque.querySelector('#id_direccion_region');
  let comuna = bloque.querySelector('#id_direccion_comuna');

  const opciones = (control, entradas, placeholder) => {
    const ordenadas = Object.entries(entradas).sort((a, b) => orden.compare(a[1], b[1]));
    control.replaceChildren(new Option(placeholder, ''), ...ordenadas.map(([codigo, nombre]) => new Option(nombre, codigo)));
  };

  function reemplazar(anterior, chile, nivel) {
    const control = document.createElement(chile ? 'select' : 'input');
    control.id = anterior.id;
    control.name = anterior.name;
    control.autocomplete = `section-direccion address-level${nivel}`;
    control.className = chile ? 'form-select' : 'form-control';
    if (!chile) {
      control.type = 'text';
      control.maxLength = 120;
    }
    anterior.replaceWith(control);
    return control;
  }

  function actualizarComunas() {
    opciones(comuna, catalogo[region.value]?.comunas ?? {}, 'Selecciona una comuna');
  }

  pais.addEventListener('change', () => {
    const chile = pais.value === 'CL';
    origen.value = pais.value;
    region = reemplazar(region, chile, 1);
    comuna = reemplazar(comuna, chile, 2);
    if (chile) {
      opciones(region, Object.fromEntries(Object.entries(catalogo).map(([codigo, dato]) => [codigo, dato.nombre])),
        'Selecciona una región');
      actualizarComunas();
    }
  });

  bloque.addEventListener('change', event => {
    if (event.target === region && pais.value === 'CL') actualizarComunas();
  });
  document.querySelector('[data-actualizar-ubicacion]').hidden = true;

  const aviso = document.querySelector('[data-aviso-direccion]');
  if (!aviso) return;
  const continuar = aviso.querySelector('[data-continuar-direccion]');
  const controlPais = document.getElementById(`busqueda-${pais.id}`) || pais;
  continuar.hash = controlPais.id;
  const revisar = aviso.querySelector('[data-revisar-direccion]');
  const dialogo = document.createElement('dialog');
  if (typeof dialogo.showModal !== 'function') return;
  dialogo.className = 'cliente-direccion-dialogo';
  dialogo.setAttribute('aria-labelledby', 'titulo-aviso-direccion');
  dialogo.setAttribute('aria-describedby', 'ayuda-aviso-direccion');
  let retorno = controlPais;
  function abrir(activador) {
    retorno = activador;
    revisar.hidden = true;
    aviso.before(dialogo);
    dialogo.append(aviso);
    dialogo.showModal();
    continuar.focus();
  }
  dialogo.addEventListener('close', () => {
    dialogo.before(aviso);
    dialogo.remove();
    revisar.hidden = false;
    retorno.focus();
  });
  continuar.addEventListener('click', event => {
    if (!dialogo.open) return;
    event.preventDefault();
    retorno = controlPais;
    dialogo.close();
  });
  revisar.addEventListener('click', () => abrir(revisar));
  revisar.hidden = false;
  if (aviso.hasAttribute('data-mostrar-aviso')) abrir(controlPais);
})();
