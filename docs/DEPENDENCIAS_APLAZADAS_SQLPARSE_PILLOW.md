# Decisión de mantenimiento: sqlparse y Pillow sin actualización inmediata

- **Fecha de decisión:** 22 de noviembre de 2026 (Chile).
- **Estado:** actualización aplazada por decisión del responsable del proyecto; no significa que los avisos de seguridad estén corregidos o descartados.
- **Base de GitHub:** `gy0kuroo/optimizador_materiales:main`, commit `70d690a7e2f4371b9072e5fb20f655d86a9661df`.
- **Alcance de este registro:** exclusivamente documentación; no modifica código, instalación, configuración, base de datos ni despliegues.

## Motivo de la decisión

Tras la integración de SEC-01 (Django 5.2.19) y la corrección de navegación de visores, el responsable del proyecto prefiere mantener las versiones actuales de `sqlparse` y `Pillow` para no introducir regresiones mientras CutLess funciona correctamente según su comprobación operativa. Se pospone su actualización hasta contar con una evaluación de compatibilidad y pruebas específicas.

Esta decisión acepta **temporalmente un riesgo residual por dependencias antiguas**; no equivale a concluir que la exposición es nula, que esas versiones son seguras o que todas las vulnerabilidades sean explotables en CutLess. Su gravedad real y las rutas de exposición requieren análisis independiente.

## Versiones conservadas

| Dependencia | Versión fijada | Decisión | Posible superficie que se debe examinar |
| --- | --- | --- | --- |
| `sqlparse` | `0.5.1` | Mantener sin actualizar por ahora. | Análisis/formato de SQL y herramientas que dependen de él, incluido Django. Evaluar avisos aplicables, entradas no confiables y llamadas directas. |
| `Pillow` | `11.0.0` | Mantener sin actualizar por ahora. | Apertura, transformación y generación de imágenes; planos PNG, miniaturas y flujos de exportación que realmente la utilicen. |

Las versiones se comprobaron en `cut/requirements.txt` del `main` indicado. No se cambió `requirements.txt` ni se eligieron versiones de destino en esta decisión.

## Riesgos y límites conocidos

- **Seguridad:** siguen pendientes de evaluación los avisos de seguridad publicados para las versiones fijadas. Registrar para cada aviso identificador, versiones afectadas, condiciones de explotación, uso real en CutLess y mitigaciones existentes antes de clasificar su aplicabilidad.
- **Compatibilidad:** actualizar sin pruebas podría introducir diferencias en el análisis de SQL o en procesamiento y presentación de imágenes. Es una posibilidad técnica, no una regresión demostrada.
- **Integridad de resultados:** los datos y planes de corte existentes no se modifican mediante este registro. Una actualización futura de Pillow exige comparar resultados y archivos exportados frente a la línea base.
- **Operación:** la seguridad efectiva de Render y Supabase continúa fuera de esta verificación (SEC-07 pendiente). La confirmación del usuario de que CutLess funciona no sustituye una auditoría de seguridad del entorno.
- **Seguimiento:** aplazamiento sin fecha comprometida de actualización; reabrir antes si aparece un aviso crítico aplicable, una explotación activa relevante, una necesidad funcional o un cambio de soporte que aumente el riesgo.

## Fuentes para la próxima revisión

- [Avisos de seguridad de sqlparse](https://github.com/andialbrecht/sqlparse/security/advisories)
- [Avisos de seguridad de Pillow](https://github.com/python-pillow/Pillow/security/advisories)
- [Notas de versiones de sqlparse](https://github.com/andialbrecht/sqlparse/releases)
- [Notas de versiones de Pillow](https://pillow.readthedocs.io/en/stable/releasenotes/index.html)
- [Informe SEC-01](SEC_01_ACTUALIZACION_DJANGO.md)

Los enlaces son fuentes de consulta para el análisis futuro, **no evidencia de que se hayan evaluado y descartado todos los avisos**.

## Condiciones para retomar el trabajo

1. Trabajar una biblioteca a la vez en una rama independiente basada en el `main` vigente.
2. Inventariar llamadas reales y dependencias transitivas; contrastar los avisos vigentes con el uso específico de CutLess.
3. Seleccionar una versión compatible y justificarla, sin asumir de antemano que la última disponible es adecuada.
4. Ejecutar las suites Django con PostgreSQL y SQLite aislados, pruebas JavaScript y verificaciones relevantes; para Pillow, comparar visualmente PNG, miniaturas y exportaciones con datos sintéticos.
5. Documentar hallazgos, pruebas, riesgos residuales, versión de destino y reversión en `docs/`.
6. Revisar el diff y solicitar autorización antes de publicar o fusionar. Recordar que Render tiene Auto Deploy habilitado y la integración en `main` podría iniciar un despliegue.

## Publicación y reversión de este registro

Este registro solo expresa una decisión de mantenimiento y no instala ni retira paquetes. Publicarlo mediante un PR exclusivamente documental evita mezclarlo con cambios funcionales. Si la decisión cambia, añadir un nuevo informe fechado en vez de reescribir el historial de decisiones.

**Conclusión:** sqlparse 0.5.1 y Pillow 11.0.0 permanecen fijados por ahora, con riesgo residual explícito y revisión futura pendiente.
