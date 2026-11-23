/* Mejora progresiva. Django lee las filas iniciales y valida el CSV enviado. */
(() => {
  function filaCsv([nombre, ancho, alto, cantidad]) {
    const citado = /[",\r\n]/.test(nombre) ? '"' + nombre.replaceAll('"', '""') + '"' : nombre;
    return [citado, ancho.replace(',', '.'), alto.replace(',', '.'), cantidad].join(',');
  }

  function validarMedida(valor, unidad, contrato) {
    const factor = contrato.factores[unidad];
    const numero = Math.round(Number(valor.replace(',', '.')) * factor * 1e6) / 1e6;
    return Number.isFinite(numero) && numero >= contrato.minCm && numero <= contrato.maxCm;
  }

  if (typeof module !== 'undefined') module.exports = {filaCsv, validarMedida};
  if (typeof document === 'undefined') return;

  const source = document.getElementById('id_piezas');
  if (!source) return;
  const iniciales = JSON.parse(document.getElementById('filas-editor-plantilla').textContent);
  if (iniciales === null) return; // El textarea permite corregir un listado ilegible sin perder texto.
  const contrato = JSON.parse(document.getElementById('contrato-editor-plantilla').textContent);
  const unit = document.getElementById('id_unidad_medida');
  const panel = document.createElement('section');
  panel.className = 'template-piece-editor';
  const note = document.createElement('p');
  note.textContent = 'Añade hasta 20 tipos de pieza. Las medidas usan la unidad seleccionada y admiten coma o punto decimal.';
  const rows = document.createElement('div');
  const add = document.createElement('button');
  add.type = 'button';
  add.className = 'btn btn-secondary';
  add.textContent = 'Añadir tipo de pieza';

  function sync() {
    source.value = Array.from(rows.children, row =>
      filaCsv(Array.from(row.querySelectorAll('textarea, input'), input => input.value))
    ).join('\n');
    add.disabled = rows.children.length >= 20;
  }

  function validarCampo(input) {
    const valor = input.value;
    let error = '';
    if (valor && input.dataset.dimension) {
      if (input.validity.patternMismatch) error = 'Usa coma o punto decimal, sin separadores de miles.';
      else if (!validarMedida(valor, unit.value, contrato)) {
        error = 'Cada lado debe medir entre 0,1 y 300 cm equivalentes.';
      }
    } else if (valor && input.inputMode === 'numeric' &&
      (input.validity.patternMismatch || Number(valor) < 1 || Number(valor) > 100)) {
      error = 'Escribe una cantidad entera de 1 a 100.';
    }
    input.setCustomValidity(error);
  }

  function actualizarUnidades() {
    rows.querySelectorAll('[data-dimension]').forEach(input => {
      input.parentElement.firstChild.textContent = `${input.dataset.dimension} (${unit.value})`;
      validarCampo(input);
    });
  }

  function renumerar() {
    Array.from(rows.children).forEach((row, i) => {
      row.querySelector('legend').textContent = `Tipo de pieza ${i + 1}`;
    });
  }

  function crearFila(values = ['', '', '', '1']) {
    const row = document.createElement('fieldset');
    row.className = 'card p-3 mb-3';
    const legend = document.createElement('legend');
    legend.className = 'h6';
    const grid = document.createElement('div');
    grid.className = 'row g-3';
    row.append(legend, grid);
    ['Nombre de la pieza', 'Ancho', 'Alto', 'Cantidad'].forEach((text, index) => {
      const label = document.createElement('label');
      label.className = 'col-md-3 form-label';
      label.append(document.createTextNode(text));
      const input = document.createElement(index ? 'input' : 'textarea');
      input.className = 'form-control';
      input.required = true;
      input.value = values[index];
      if (!index) {
        input.rows = 1;
        input.maxLength = 50;
      } else if (index === 3) {
        input.inputMode = 'numeric';
        input.pattern = contrato.entero;
      } else {
        input.inputMode = 'decimal';
        input.pattern = contrato.decimal;
        input.dataset.dimension = text;
      }
      input.addEventListener('input', () => {
        validarCampo(input);
        if (!input.validity.customError && !input.validity.patternMismatch) sync();
      });
      label.append(input);
      grid.append(label);
      validarCampo(input);
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'btn btn-outline-danger align-self-end mt-3';
    remove.dataset.action = 'delete';
    remove.dataset.icon = 'trash';
    remove.textContent = 'Eliminar';
    remove.addEventListener('click', () => { row.remove(); renumerar(); sync(); });
    row.append(remove);
    rows.append(row);
    renumerar();
    actualizarUnidades();
  }

  iniciales.forEach(crearFila);
  if (!iniciales.length) crearFila();
  unit.addEventListener('change', actualizarUnidades);
  add.addEventListener('click', () => {
    if (rows.children.length >= 20) return;
    crearFila();
    sync();
    rows.lastElementChild.querySelector('textarea').focus();
  });
  add.disabled = rows.children.length >= 20;
  source.hidden = true;
  source.required = false;
  const title = document.querySelector('label[for="id_piezas"]');
  if (title) title.textContent = 'Piezas de la plantilla *';
  panel.append(note, rows, add);
  source.after(panel);
  const format = source.parentElement.querySelector('.template-format');
  if (format) format.hidden = true;
  source.form.addEventListener('submit', sync);
})();
