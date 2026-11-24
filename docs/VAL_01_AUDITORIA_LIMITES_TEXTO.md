# VAL-01 · Auditoría inicial de límites de texto y plan de corrección

**Fecha:** 24/11/2026. **Base:** `gy0kuroo/optimizador_materiales:main` en `55df10e766b90098d1e50244b5371d8f729747e1`. **Alcance:** lectura de modelos y formularios Python; no se ejecutaron pruebas ni se consultó el contenido de la base de datos de producción. No se modificó código ni esquema.

## 1. Hallazgo y objetivo

La revisión académica detectó límites poco adecuados para nombres y campos breves, entre ellos nombre del trabajo de 100 caracteres y nombre de usuario al registrar una cuenta de hasta 150. Se debe implementar un **contrato de límites por propósito**, coherente en formulario HTML y servidor, sin truncar datos existentes ni bloquear modificaciones no relacionadas.

Un límite de HTML (`maxlength`) **no es suficiente**: una petición manual puede omitirlo. La validación definitiva debe ejecutarse en Django. Reducir el `max_length` de una columna en PostgreSQL exige antes revisar datos históricos y planificar una migración; no se hará automáticamente en VAL-01.

## 2. Inventario confirmado en código

| Campo visible / módulo | Límite o comportamiento actual | Evidencia | Límite de nueva entrada propuesto |
| --- | --- | --- | --- |
| Nombre de trabajo, inicio/optimización | 100 caracteres, `NombreOptimizacionForm` | [Formulario](../cut/cutless/forms/optimization.py), [modelo](../cut/cutless/models.py) | 50 |
| Nombre de pieza, optimización | 50 caracteres, `PiezaForm` | [Formulario](../cut/cutless/forms/optimization.py) | **Conservar 50**, salvo justificación |
| Usuario al registrar cuenta | Límite heredado del modelo `django.contrib.auth.models.User.username`: 150 caracteres, sin redefinición en `RegistroForm` | [Registro](../cut/usuarios/forms.py) | 30; política explícita consistente |
| Usuario al editar perfil | `PerfilForm` fija 15 caracteres y solo letras | [Perfil](../cut/usuarios/forms.py) | Reconciliar **15/30** antes de implementar; no dejar dos contratos diferentes |
| Cliente: nombre o razón social | 200 caracteres en `Cliente.nombre` | [Modelo](../cut/cutless/models.py), [formulario](../cut/cutless/forms/clients.py) | 120; razón social puede necesitar más caracteres que un nombre personal |
| Cliente nuevo escrito desde Presupuestos | 200 caracteres en `nombre_cliente_nuevo`; puede crear `Cliente` automáticamente | [Formulario](../cut/cutless/forms/budgets.py), [vista](../cut/cutless/views/budgets.py) | 120, **idéntico** al formulario de Clientes; preservar integridad y evitar alta parcial |
| Nombre de Proyecto | 200 caracteres | [Modelo](../cut/cutless/models.py), [formulario](../cut/cutless/forms/projects.py) | 80 |
| Nombre de Material | 100 caracteres | [Modelo](../cut/cutless/models.py), [formulario](../cut/cutless/forms/materials.py) | 80 |
| Nombre de Plantilla | 200 caracteres | [Modelo](../cut/cutless/models.py), [formulario](../cut/cutless/forms/plantillas.py) | 80 |
| Descripción de material/proyecto/plantilla; notas de cliente/presupuesto | Campos `TextField` sin `max_length` específico en modelos | [Modelo](../cut/cutless/models.py) | Proponer entre 500 y 1000 según finalidad; **no aplicar un valor universal sin revisar contenido y usos** |
| Dirección heredada y campos de dirección estructurada | Texto legado libre y campos estructurados con límites específicos de 2 a 240 | [Modelo](../cut/cutless/models.py), [direcciones CLI-01/CLI-02](CLI_02_DIRECCIONES_SIMPLIFICADAS_CLIENTES.md) | **Conservar por defecto**: el texto legado no debe cortarse y los campos postales cumplen otra función |
| RUT, email y teléfono | Validadores o campos especializados, con sus límites actuales | [Clientes](../cut/cutless/forms/clients.py) y [validación de contacto](../cut/cutless/validacion_contacto.py) | Mantener validación propia de cada dato; no tratarlos como nombres cortos |
| Contraseña / datos internos / serialización de piezas | Contratos funcionales y de seguridad distintos | Formularios de usuarios y [serialización](../cut/cutless/pieces.py) | Fuera del recorte genérico de nombres; requieren límites y pruebas específicos |

**Advertencia:** el inventario cubre los formularios y modelos principales revisados. Antes de declarar “todos los inputs corregidos”, efectuar búsqueda adicional de entradas en plantillas HTML, administración Django, pantallas dinámicas y JavaScript, y clasificar también las entradas no vinculadas directamente a los formularios anteriores.

## 3. Reglas propuestas para la implementación

1. **Servidor como fuente de verdad:** fijar `max_length` en campos Django de creación y edición. Añadir `maxlength` y, cuando ayude, contador al HTML, pero exigir la misma validación en POST.
2. **Consistencia entre caminos:** si el mismo dato puede nacer desde Clientes, Presupuestos, Admin o un formulario de alta rápida, todos usan la misma regla; incluir los accesos de edición y duplicación.
3. **Registros históricos largos:** preservar literalmente el valor existente cuando el usuario edite otros campos. Si pretende cambiar ese nombre, exigir el nuevo máximo con un mensaje claro. No aplicar `strip` o truncamiento silencioso a texto histórico que no esté siendo editado.
4. **Cuenta de usuario:** no cambiar el `User.username` de Django sin evaluación previa. Es posible restringir el nuevo ingreso con `RegistroForm` y adaptar la edición, pero antes se necesita decidir si el objetivo es 15 o 30 caracteres, ya que el perfil hoy admite 15 y registro 150. Evitar bloquear a cuentas históricas que necesiten editar su correo.
5. **Campos largos:** mantener límites explícitos apropiados en notas y descripciones, con un criterio sustentado. No mezclar datos técnicos estructurados (`piezas`), identificadores, direcciones heredadas, correos o contraseñas con nombres de presentación.
6. **No introducir migraciones por defecto:** el primer paso será una validación por formulario; considerar reducir tamaños de columna solo luego de una consulta de longitudes y revisión de riesgos sobre las dos bases aisladas y, posteriormente, aprobación para cualquier cambio en producción.

## 4. Matriz mínima de pruebas antes de fusionar

- **Límite exacto:** aceptar exactamente N caracteres y rechazar N+1, tanto desde navegador como desde POST manual.
- **Normalización:** comprobar espacios, caracteres acentuados, Unicode, nombres de razón social y mensajes de error en español.
- **Alta / edición / duplicación:** validar nombre de trabajo, proyecto, material, plantilla, cliente y usuario, incluidos métodos alternativos de creación desde Presupuestos.
- **Históricos:** crear fixtures con valores mayores al nuevo máximo permitido; editar otros campos sin que se borre el nombre, y comprobar que renombrar exige el límite nuevo.
- **Seguridad e integridad:** nombre inválido no debe crear clientes automáticamente desde Presupuestos ni dejar un presupuesto parcialmente escrito. No modificar objetos de otras cuentas.
- **UX:** verificar la indicación de máximo, `maxlength`, mensajes, foco, conservación de datos introducidos y comportamiento en 320, 390 y 1280 px, temas claro/oscuro.
- **Regresión:** Django con SQLite y PostgreSQL locales, JavaScript, pruebas de navegador y `makemigrations --check --dry-run`. Si se cambia un modelo, revisar de forma explícita la necesidad de migración.

## 5. Siguientes tareas y límites del lote

**VAL-01A (este documento):** auditoría inicial y contrato propuesto. **VAL-01B:** implementación en ramas de código con tests. **VAL-01C:** barrido completo de HTML/JS y regresión de entradas secundarias. Solo se fusionarán una vez que las pruebas y el impacto histórico estén registrados.

**Otros hallazgos de la revisión**, separados de VAL-01: VAL-02 (fechas de Proyectos), PRE-03 (ciclo de estados de Presupuestos), CLI-03 (validación y creación de Clientes) y UX-06 (búsqueda de países/prefijos mientras se escribe). No se modifican en esta rama.

## 6. Frase para la evaluación

“Revisamos los formularios porque varios aceptaban textos demasiado largos para su propósito. Definimos límites distintos para nombres, descripciones y datos de contacto, con validación real en Django y ayuda visual en el navegador. La corrección debe respetar los registros anteriores y evitar perder información cuando se edita un campo no relacionado.”

**Estado actual:** propuesta documental; todavía **no** existe un cambio funcional ni evidencia de pruebas nuevas para VAL-01.
