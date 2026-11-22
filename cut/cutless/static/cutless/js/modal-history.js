(() => {
  'use strict';

  window.createModalHistory = ({element, key, valid, render, findOpener}) => {
    const url = location.href;
    let closing = false, hiding = false, lastValue, rendered = null;
    const modal = () => bootstrap.Modal.getOrCreateInstance(element);
    const entry = () => {
      const state = history.state?.[key];
      return state?.url === url && location.href === url ? state : null;
    };
    const isOpen = () => !closing && valid(entry()?.value);
    const visible = () => element.classList.contains('show');

    function synchronize() {
      if (!isOpen()) {
        rendered = null;
        if (visible()) modal().hide();
        return;
      }
      if (hiding) return;
      const value = entry().value;
      const signature = JSON.stringify(value);
      if (rendered === signature && visible()) return;
      rendered = signature;
      lastValue = value;
      const result = render(value);
      modal().show();
      return result;
    }

    function write(value, replace) {
      const state = {...history.state, [key]: {url, value}};
      if (replace) history.replaceState(state, '', url);
      else history.pushState(state, '', url);
    }

    function close() {
      if (closing) return;
      if (isOpen()) {
        closing = true;
        history.back();
      } else if (visible()) modal().hide();
    }

    element.querySelectorAll('[data-close-modal-viewer]').forEach(button => {
      button.addEventListener('click', close);
    });
    document.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || !isOpen()) return;
      const focusedModal = event.target.closest?.('.modal.show');
      if (focusedModal && focusedModal !== element) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      close();
    }, true);
    element.addEventListener('hide.bs.modal', event => {
      // Bootstrap también puede pedir el cierre al pulsar el fondo.
      if (closing || isOpen()) {
        event.preventDefault();
        close();
        return;
      }
      hiding = true;
    });
    element.addEventListener('shown.bs.modal', () => {
      // Bootstrap ignora hide() mientras transcurre la animación de apertura.
      if (!isOpen() && !closing) modal().hide();
    });
    element.addEventListener('hidden.bs.modal', () => {
      hiding = false;
      if (isOpen()) synchronize();
      else findOpener(lastValue)?.focus({preventScroll: true});
    });
    window.addEventListener('popstate', () => {
      closing = false;
      synchronize();
    });
    window.addEventListener('pageshow', () => {
      closing = false;
      synchronize();
    });

    return {
      open(value) {
        if (closing || !valid(value)) return;
        write(value, Boolean(entry()));
        return synchronize();
      },
      replace(value) {
        if (isOpen() && valid(value)) {
        write(value, true);
        rendered = JSON.stringify(value);
      }
      },
      isOpen,
    };
  };
})();
