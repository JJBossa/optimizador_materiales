/**
 * Utilidades para confirmaciones y mejoras de UX
 */

(function () {
    'use strict';

    window.confirmarEliminacion = async function (mensaje, tipo) {
        tipo = tipo || 'optimización';
        var mensajes = {
            'optimización': '¿Estás seguro de que deseas eliminar esta optimización? Esta acción no se puede deshacer.',
            'material': '¿Estás seguro de que deseas eliminar este material? Esta acción no se puede deshacer.',
            'cliente': '¿Estás seguro de que deseas eliminar este cliente? Esta acción no se puede deshacer.',
            'proyecto': '¿Estás seguro de que deseas eliminar este proyecto? Esta acción no se puede deshacer.',
            'plantilla': '¿Estás seguro de que deseas eliminar esta plantilla? Esta acción no se puede deshacer.',
            'seleccion': '¿Estás seguro de que deseas borrar las optimizaciones seleccionadas? Esta acción no se puede deshacer.'
        };

        var mensajeFinal = mensaje || mensajes[tipo] || '¿Estás seguro de que deseas realizar esta acción?';
        if (typeof window.cutlessConfirmar !== 'function') {
            return window.confirm(mensajeFinal);
        }
        return window.cutlessConfirmar({
            destructiva: true,
            titulo: 'Confirmar eliminación',
            mensaje: mensajeFinal,
            textoAceptar: 'Sí, eliminar',
            textoCancelar: 'Cancelar'
        });
    };

    window.mostrarIndicadorCarga = function (mensaje, { autoCerrar = true } = {}) {
        mensaje = mensaje || 'Generando...';
        window.ocultarIndicadorCarga();

        var template = document.getElementById('cutless-loading-template');
        var overlay;
        if (template) {
            overlay = template.content.firstElementChild.cloneNode(true);
            overlay.querySelector('[data-loading-message]').textContent = mensaje;
        } else {
            // Respaldo accesible si esta utilidad se carga sin la plantilla base.
            overlay = document.createElement('div');
            overlay.id = 'loading-overlay';
            overlay.className = 'cutless-loading';
            overlay.setAttribute('role', 'status');
            overlay.setAttribute('aria-live', 'polite');
            var texto = document.createElement('p');
            texto.className = 'cutless-loading__card cutless-loading__message';
            texto.textContent = mensaje;
            overlay.appendChild(texto);
        }

        document.body.appendChild(overlay);

        if (window._loadingOverlayTimeoutId) {
            clearTimeout(window._loadingOverlayTimeoutId);
        }
        if (autoCerrar) {
            window._loadingOverlayTimeoutId = setTimeout(function () {
                window.ocultarIndicadorCarga();
            }, 15000);
        }

        return overlay;
    };

    window.ocultarIndicadorCarga = function () {
        var overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.remove();
        }
        if (window._loadingOverlayTimeoutId) {
            clearTimeout(window._loadingOverlayTimeoutId);
            window._loadingOverlayTimeoutId = null;
        }
    };

})();

document.addEventListener('DOMContentLoaded', function () {
    var skipAttr = 'data-cutless-skip-confirm';

    function attachDeleteConfirm(form) {
        if (form.getAttribute('data-cutless-no-confirm') === '1') {
            return;
        }
        form.addEventListener('submit', async function (e) {
            if (form.getAttribute(skipAttr) === '1') {
                form.removeAttribute(skipAttr);
                return;
            }
            e.preventDefault();
            var customMsg = form.getAttribute('data-cutless-mensaje');
            var tipo = form.getAttribute('data-tipo') || 'optimización';
            var ok = await window.confirmarEliminacion(customMsg || null, tipo);
            if (ok) {
                form.setAttribute(skipAttr, '1');
                form.requestSubmit();
            }
        });
    }

    var deleteForms = document.querySelectorAll('form[data-confirm-delete], form.delete-form-inline, form[action*="borrar"], form[action*="eliminar"], form:has(button[type="submit"][data-action="delete"])');
    deleteForms.forEach(attachDeleteConfirm);

    var generateForms = document.querySelectorAll('form[action*="index"], form[action*="optimizar"], form[data-loading-optimization]');
    generateForms.forEach(function (form) {
        form.addEventListener('submit', function (event) {
            if (form.getAttribute('aria-busy') === 'true') { event.preventDefault(); return; }
            // Esperar al resto de validadores antes de presentar la espera.
            queueMicrotask(function () {
                if (event.defaultPrevented) return;
                if (typeof window.mostrarSkeletonOptimizacion === 'function') window.mostrarSkeletonOptimizacion(form);
                else window.mostrarIndicadorCarga('Procesando optimización... Esto puede tardar unos segundos.');
            });
        });
    });
});
