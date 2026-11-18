const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../static/usuarios/js/auth-feedback.js'), 'utf8');
const spaceError = 'El nombre de usuario no puede contener espacios. Quítalos para continuar.';

function mount({value = '', serverError = '', registration = true} = {}) {
  const listeners = new Map();
  const fieldListeners = new Map();
  const errors = {
    hidden: !serverError, textContent: serverError, dataset: {},
    replaceChildren() { this.textContent = ''; },
    append(line) { this.textContent = line.textContent; },
  };
  const wrapper = {dataset: {}, querySelector: () => errors};
  let ariaInvalid = Boolean(serverError);
  const username = {
    value, validity: {}, type: 'text', dataset: {usernameSpaceError: spaceError},
    closest: () => wrapper,
    getAttribute: () => String(ariaInvalid),
    setAttribute: (_, value) => { ariaInvalid = value === 'true'; },
    addEventListener: (name, fn) => fieldListeners.set(name, fn),
  };
  const summary = {hidden: !serverError, focus() {}};
  const form = {
    dataset: {authFeedback: registration ? 'register' : 'login'},
    querySelectorAll: () => [username],
    querySelector: () => summary,
    elements: {namedItem: name => name === 'username' ? username : null},
    addEventListener: (name, fn) => listeners.set(name, fn),
    classList: {add() {}},
  };
  const document = {
    querySelector: () => form, documentElement: {classList: {remove() {}}},
    createElement: () => ({
      textContent: '', setAttribute() {},
      append(icon, text) { this.textContent += icon.textContent + text; },
    }),
  };
  vm.runInNewContext(script, {document});
  return {
    errors,
    value: () => username.value,
    invalid: () => ariaInvalid,
    blur: () => fieldListeners.get('blur')(),
    type(value) {
      username.value = value;
      fieldListeners.get('input')();
    },
    submit() {
      let prevented = false;
      listeners.get('submit')({preventDefault() { prevented = true; }});
      return prevented;
    },
  };
}

test('detecta espacios internos al escribir y evita el envío sin cambiar el valor', () => {
  const ui = mount();
  for (const value of ['Ana Pérez', 'Ana\u00a0Pérez', 'Ana\tPérez']) {
    ui.type(value);
    assert.equal(ui.errors.textContent, '! ' + spaceError);
    assert.equal(ui.invalid(), true);
    assert.equal(ui.submit(), true);
    assert.equal(ui.value(), value);
  }
  ui.type('Ana_Pérez');
  assert.equal(ui.errors.hidden, true);
  assert.equal(ui.submit(), false);
});

test('omite espacios exteriores y permite los caracteres que Django acepta', () => {
  const ui = mount({value: '\u0085 José_27@equipo.+- \u0085'});
  assert.equal(ui.submit(), false);
  assert.equal(ui.errors.hidden, true);
});

test('conserva el error de duplicado al salir del campo y lo limpia al editar', () => {
  const duplicate = 'Este nombre de usuario ya está en uso. Prueba con otro.';
  const ui = mount({value: 'Ana_Pérez', serverError: duplicate});
  ui.blur();
  assert.equal(ui.errors.textContent, duplicate);
  assert.equal(ui.invalid(), true);
  assert.equal(ui.errors.hidden, false);
  ui.type('Ana_2027');
  assert.equal(ui.errors.hidden, true);
  assert.equal(ui.invalid(), false);
});

test('deja otros caracteres inválidos a Django y conserva su respuesta', () => {
  const ui = mount({value: 'persona!nueva'});
  assert.equal(ui.submit(), false);
  const rejected = mount({value: 'persona!nueva', serverError: 'Usa letras, números o estos símbolos.'});
  rejected.blur();
  assert.equal(rejected.errors.hidden, false);
});

test('la comprobación de espacios se limita al formulario de registro', () => {
  const ui = mount({value: 'Ana Pérez', registration: false});
  assert.equal(ui.submit(), false);
});
