(() => {
  const agrupador = new Intl.NumberFormat('es-CL', {useGrouping: 'always'});
  const decimalCanonico = /^[+-]?[0-9]+(?:\.[0-9]+)?$/;

  function formatearCLP(valor, conSigno = false) {
    if (typeof valor === 'string') {
      if (!decimalCanonico.test(valor)) return '—';
    } else if (typeof valor !== 'bigint' && !Number.isFinite(valor)) {
      return '—';
    }

    const texto = String(valor);
    const [mantisa, exponente = '0'] = texto.replace(/^[+-]/, '').split('e');
    const [entera, fraccion = ''] = mantisa.split('.');
    const digitos = entera + fraccion;
    const corte = entera.length + Number(exponente);
    const enteros = corte <= 0 ? '0' : digitos.slice(0, corte).padEnd(corte, '0');
    const pesos = BigInt(enteros) + (corte >= 0 && digitos[corte] >= '5' ? 1n : 0n);
    const noEsCero = /[1-9]/.test(digitos);
    const signo = noEsCero ? (texto.startsWith('-') ? '-' : conSigno ? '+' : '') : '';

    if (!pesos && noEsCero) return signo ? `${signo}(menos de $1)` : 'Menos de $1';
    return `${signo}$${agrupador.format(pesos)}`;
  }

  if (typeof module === 'object' && module.exports) module.exports = {formatearCLP};
  else window.formatearCLP = formatearCLP;
})();
