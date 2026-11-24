(() => {
  function iniciar() {
    for (const campo of document.querySelectorAll('textarea[data-limite-texto]')) {
      const limite = Number(campo.dataset.limiteTexto);
      const contador = document.createElement('small');
      contador.className = 'form-text';
      contador.style.display = 'block';
      campo.after(contador);

      function actualizar() {
        const longitud = campo.value.length;
        const exceso = longitud > limite;
        contador.textContent = `${longitud}/${limite} caracteres${exceso ? ' · Supera el máximo' : ''}`;
        contador.classList.toggle('text-danger', exceso);
      }

      campo.addEventListener('input', actualizar);
      actualizar();
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar, { once: true });
  else iniciar();
})();
