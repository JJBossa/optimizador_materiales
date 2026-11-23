/* La selección estándar es explícita: unas medidas iguales no identifican el material. */
(() => {
  function init() {
    const container = document.getElementById('medidas-pred-container');
    const button = document.getElementById('tableros-dropdown');
    const selected = document.getElementById('medida_habitual');
    const width = document.getElementById('ancho_tablero');
    const height = document.getElementById('alto_tablero');
    const unit = document.getElementById('unidad_medida_selector');
    const material = document.getElementById('material_select');
    if (!container || !button || !selected || !width || !height || container.dataset.medidasReady) return;
    container.dataset.medidasReady = 'true';
    const options = Array.from(container.querySelectorAll('[data-medida]'));
    const factors = {cm:1, m:100, mm:.1, in:2.54, ft:30.48};
    const factor = () => factors[unit?.value] || 1;
    const number = value => String(Number(value.toFixed(6)));
    let choosing = false;
    function refresh() {
      for (const option of options) {
        option.textContent = `${option.dataset.nombre} (${number(Number(option.dataset.anchoCm)/factor())}×${number(Number(option.dataset.altoCm)/factor())} ${unit?.value || 'cm'})`;
      }
      let option = options.find(item => item.dataset.medida === selected.value);
      if (option && (Math.abs(Number(width.value.replace(',', '.'))*factor()-Number(option.dataset.anchoCm)) > .01 ||
                     Math.abs(Number(height.value.replace(',', '.'))*factor()-Number(option.dataset.altoCm)) > .01)) {
        selected.value = ''; option = null;
      }
      button.textContent = option ? option.textContent : 'Elegir medidas habituales';
      if (option) button.dataset.tableroSeleccionado = selected.value;
      else delete button.dataset.tableroSeleccionado;
    }
    function matchLibrary(option) {
      if (!material) return;
      const data = window.materialData || {};
      const match = Array.from(material.options).find(item => {
        const candidate = data[item.value];
        return candidate && candidate.nombre.toLowerCase().includes(option.dataset.nombre.toLowerCase()) &&
          Math.abs(candidate.ancho-Number(option.dataset.anchoCm)) <= .01 &&
          Math.abs(candidate.alto-Number(option.dataset.altoCm)) <= .01;
      });
      material.value = match ? match.value : '';
      material.dispatchEvent(new Event('change', {bubbles:true}));
    }
    for (const option of options) option.addEventListener('click', event => {
      event.preventDefault(); choosing = true; window.cambioDesdeDropdown = true;
      width.value = window.CutlessUnits.entradaDesdeCm(Number(option.dataset.anchoCm), unit.value);
      height.value = window.CutlessUnits.entradaDesdeCm(Number(option.dataset.altoCm), unit.value);
      selected.value = option.dataset.medida;
      matchLibrary(option);
      width.dispatchEvent(new Event('change', {bubbles:true}));
      height.dispatchEvent(new Event('change', {bubbles:true}));
      choosing = false; window.cambioDesdeDropdown = false; refresh();
      if (typeof bootstrap !== 'undefined') bootstrap.Dropdown?.getInstance(button)?.hide();
    });
    material?.addEventListener('change', () => { if (!choosing) { selected.value = ''; refresh(); } });
    width.addEventListener('input', refresh); height.addEventListener('input', refresh);
    unit?.addEventListener('change', () => queueMicrotask(refresh));
    refresh();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
