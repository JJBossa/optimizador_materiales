const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/usuarios/js/configuracion-inicial.js'), 'utf8');
const draftKey = 'cutless:setup-draft:v1:9';
let nextDraftId = 0;

function mount({storage = new Map(), confirmedDraft = '', hasErrors = 'false', selectedMode = 'esencial'} = {}) {
    function node(extra = {}) {
        const handlers = {};
        return Object.assign({
            addEventListener(name, handler) { handlers[name] = handler; },
            emit(name, event) { handlers[name]?.(event); },
        }, extra);
    }

    const elements = Object.fromEntries([
        'setup-prev', 'setup-next', 'setup-save', 'setup-step-text', 'tools-count',
        'optional-tools', 'setup-summary', 'setup-draft-id', 'setup-skip-draft-id',
        'setup-skip-form',
    ].map(id => [id, node()]));
    const radios = {
        modo: ['esencial', 'personalizado'],
        tema_preferido: ['auto', 'dark'],
        tamanio_fuente: ['normal', 'large'],
    };
    for (const name of Object.keys(radios)) {
        const values = radios[name];
        radios[name] = values.map(value => ({
            value,
            get checked() { return values.selected === value; },
            set checked(checked) { if (checked) values.selected = value; },
        }));
        values.selected = name === 'modo' ? selectedMode : hasErrors === 'true' && name === 'tema_preferido' ? '' : values[0];
    }

    const steps = [node({querySelector: () => ({focus() {}})}), node({querySelector: () => ({focus() {}})})];
    const document = node({
        getElementById: id => elements[id],
        querySelectorAll: () => [],
        documentElement: {dataset: {}, style: {}},
    });
    const radioList = selector => radios[selector.match(/name="([^"]+)"/)?.[1]] || [];
    elements['setup-form'] = node({
        dataset: {userId: '9', confirmedDraft, hasErrors},
        querySelectorAll: selector => selector === '[data-step]' ? steps : radioList(selector),
        querySelector: selector => radioList(selector).find(input => input.checked),
    });
    const window = node({
        matchMedia: () => node({matches: false}),
        crypto: {randomUUID: () => 'borrador-' + ++nextDraftId},
    });
    const localStorage = {
        getItem: key => storage.get(key),
        setItem: (key, value) => storage.set(key, value),
        removeItem: key => storage.delete(key),
    };
    vm.runInNewContext(source, {window, document, localStorage});
    document.emit('DOMContentLoaded');

    function eventFor(id, kind) {
        const event = {defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }};
        elements[id].emit(kind, event);
        return event;
    }

    return {
        storage, elements, radios, steps,
        change(name, index) {
            radios[name][index].checked = true;
            eventFor('setup-form', 'change');
        },
        eventFor,
    };
}

test('H15: Enter implícito del formulario avanza y el clic de omitir pertenece a su formulario', () => {
    const page = mount();
    assert.equal(page.eventFor('setup-form', 'submit').defaultPrevented, true);
    assert.equal(page.steps[1].hidden, false);
    assert.equal(page.elements['setup-draft-id'].value, undefined);
    assert.equal(page.eventFor('setup-skip-form', 'submit').defaultPrevented, false);
});

test('H15: continuar con el mouse avanza sin enviar y guardar después habilita el POST', () => {
    const page = mount();
    page.eventFor('setup-next', 'click');
    assert.equal(page.steps[1].hidden, false);
    assert.equal(page.elements['setup-draft-id'].value, undefined);
    assert.equal(page.eventFor('setup-form', 'submit').defaultPrevented, false);
    assert.match(page.elements['setup-draft-id'].value, /^borrador-/);
});

test('H17: un POST sin confirmación conserva el borrador al reabrir; un éxito lo retira', () => {
    const page = mount();
    page.change('modo', 1);
    page.change('tema_preferido', 1);
    page.eventFor('setup-next', 'click');
    page.eventFor('setup-form', 'submit');

    const reloaded = mount({storage: page.storage});
    assert.equal(reloaded.radios.modo[1].checked, true);
    assert.equal(reloaded.radios.tema_preferido[1].checked, true);
    const id = page.elements['setup-draft-id'].value;
    mount({storage: page.storage, confirmedDraft: id});
    assert.equal(page.storage.has(draftKey), false);
});

test('H17: un error conserva opciones válidas del servidor y recupera la elección no renderizada', () => {
    const page = mount();
    page.change('modo', 1);
    page.change('tema_preferido', 1);
    const conErrores = mount({storage: page.storage, hasErrors: 'true', selectedMode: 'personalizado'});
    assert.equal(conErrores.radios.modo[1].checked, true);
    assert.equal(conErrores.radios.tema_preferido[1].checked, true);
    assert.equal(JSON.parse(page.storage.get(draftKey)).theme, 'dark');
});
