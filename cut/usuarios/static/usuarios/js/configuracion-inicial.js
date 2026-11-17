document.addEventListener('DOMContentLoaded', () => {
    // Iconos Lucide en SVG inline: se mantiene un único estilo sin cargar otra librería.
    const toolIcons = {
        materiales: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/></svg>',
        clientes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M20 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
        proyectos: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>',
        presupuestos: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M8 13h3M8 17h2"/><circle cx="16" cy="16" r="3.5"/><path d="M16 14.5v3M17 15.3c0-.45-.45-.8-1-.8s-1 .35-1 .8.45.7 1 .7 1 .35 1 .8-.45.8-1 .8-1-.35-1-.8"/></svg>',
        plantillas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" focusable="false"><rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>',
        costos: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" focusable="false"><circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M8 5v6M10 6.5c0-.83-.9-1.5-2-1.5s-2 .67-2 1.5S6.9 8 8 8s2 .67 2 1.5S9.1 11 8 11"/></svg>',
        comparar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" focusable="false"><rect x="3" y="4" width="7" height="16" rx="1.5"/><rect x="14" y="4" width="7" height="16" rx="1.5"/><path d="M10 9h4m-2-2 2 2-2 2M14 15h-4m2-2-2 2 2 2"/></svg>',
        estadisticas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="M3 3v18h18"/><rect x="7" y="13" width="3" height="5" rx="1"/><rect x="13" y="9" width="3" height="9" rx="1"/><rect x="19" y="5" width="2" height="13" rx="1"/></svg>',
        fallback: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" focusable="false"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>',
    };

    const form = document.getElementById('setup-form');
    if (!form) return;
    form.querySelectorAll('[data-tool-icon]').forEach(element => {
        element.innerHTML = toolIcons[element.dataset.toolIcon] || toolIcons.fallback;
    });
    const sections = Array.from(form.querySelectorAll('[data-step]'));
    const previous = document.getElementById('setup-prev');
    const next = document.getElementById('setup-next');
    const save = document.getElementById('setup-save');
    const tools = Array.from(form.querySelectorAll('#optional-tools input[type="checkbox"]'));
    const choice = name => form.querySelector(`input[name="${name}"]:checked`)?.value;
    const draftKey = `cutless:setup-draft:v1:${form.dataset.userId}`;
    const savedMarkerKey = `${draftKey}:saved`;
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
    let step = 0;
    let hasUnsavedChanges = false;
    let submitting = false;

    function readPreferences() {
        const mode = choice('modo') || 'esencial';
        return {
            mode,
            tools: tools.filter(input => input.checked).map(input => input.name).sort(),
            theme: choice('tema_preferido') || 'auto',
            fontSize: choice('tamanio_fuente') || 'normal',
        };
    }

    function storeDraft() {
        hasUnsavedChanges = true;
        try {
            localStorage.setItem(draftKey, JSON.stringify(readPreferences()));
        } catch (_) {
            // Si el navegador bloquea el almacenamiento local, el formulario sigue funcionando.
        }
    }

    function restoreDraft() {
        const initialPreferences = JSON.stringify(readPreferences());
        try {
            if (form.dataset.hasErrors === 'true') {
                localStorage.removeItem(savedMarkerKey);
                storeDraft();
                return;
            }
            if (localStorage.getItem(savedMarkerKey) === '1') {
                localStorage.removeItem(savedMarkerKey);
                localStorage.removeItem(draftKey);
                return;
            }
            const rawDraft = localStorage.getItem(draftKey);
            if (!rawDraft) return;
            const draft = JSON.parse(rawDraft);
            if (!draft || typeof draft !== 'object') throw new Error('Borrador inválido');
            if (JSON.stringify(draft) === initialPreferences) {
                localStorage.removeItem(draftKey);
                return;
            }

            const setChoice = (name, value) => {
                const input = Array.from(form.querySelectorAll(`input[name="${name}"]`))
                    .find(candidate => candidate.value === value);
                if (input) input.checked = true;
            };
            setChoice('modo', draft.mode);
            setChoice('tema_preferido', draft.theme);
            setChoice('tamanio_fuente', draft.fontSize);
            tools.forEach(input => {
                input.checked = Array.isArray(draft.tools)
                    && draft.tools.includes(input.name);
            });
            hasUnsavedChanges = true;
        } catch (_) {
            try { localStorage.removeItem(draftKey); } catch (__) { /* almacenamiento no disponible */ }
        }
    }

    function renderStep(focus = false) {
        sections.forEach((section, index) => { section.hidden = index !== step; });
        document.querySelectorAll('[data-progress]').forEach((item, index) => {
            if (index === step) item.setAttribute('aria-current', 'step');
            else item.removeAttribute('aria-current');
        });
        previous.hidden = step === 0;
        next.hidden = step === sections.length - 1;
        save.hidden = step !== sections.length - 1;
        document.getElementById('setup-step-text').textContent = `Paso ${step + 1} de 2 · Puedes cambiar estas preferencias después.`;
        if (focus) sections[step].querySelector('h2').focus();
    }

    function preview() {
        const custom = choice('modo') === 'personalizado';
        document.getElementById('optional-tools').hidden = !custom;
        const selected = custom ? tools.filter(input => input.checked) : [];
        document.getElementById('tools-count').textContent = `${selected.length} seleccionadas`;
        tools.forEach(input => {
            const state = input.closest('label')?.querySelector('.setup-tool-state');
            if (state) state.textContent = input.checked ? 'Seleccionada' : 'Seleccionar';
        });
        const theme = choice('tema_preferido') || 'auto';
        document.documentElement.dataset.theme = theme === 'auto' ? (systemTheme.matches ? 'dark' : 'light') : theme;
        const sizes = {small: '15px', normal: '16px', large: '18px', xlarge: '20px'};
        document.documentElement.style.fontSize = sizes[choice('tamanio_fuente')] || sizes.normal;
        document.getElementById('setup-summary').textContent = selected.length
            ? `Tu menú incluirá Optimización, Historial y ${selected.length} herramientas adicionales.`
            : 'Tu menú incluirá Optimización e Historial. Las demás herramientas podrán activarse más adelante.';
    }

    previous.addEventListener('click', () => { step = Math.max(0, step - 1); renderStep(true); });
    next.addEventListener('click', () => { step = Math.min(sections.length - 1, step + 1); renderStep(true); });
    form.addEventListener('change', () => { preview(); storeDraft(); });
    // Enter en el primer paso avanza; nunca guarda antes de revisar la apariencia.
    form.addEventListener('submit', event => {
        if (event.submitter?.value === 'skip') {
            try { localStorage.setItem(savedMarkerKey, '1'); } catch (_) { /* el servidor guarda el modo esencial */ }
            submitting = true;
            hasUnsavedChanges = false;
            return;
        }
        if (step === 0) { event.preventDefault(); step = 1; renderStep(true); }
        else {
            try { localStorage.setItem(savedMarkerKey, '1'); } catch (_) { /* el servidor conserva la configuración */ }
            submitting = true;
            hasUnsavedChanges = false;
        }
    });
    window.addEventListener('beforeunload', event => {
        if (!hasUnsavedChanges || submitting) return;
        event.preventDefault();
        event.returnValue = '';
    });
    systemTheme.addEventListener('change', preview);
    restoreDraft();
    renderStep();
    preview();
});
