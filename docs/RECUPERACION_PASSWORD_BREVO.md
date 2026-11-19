# Recuperación de contraseña con Brevo

Django sigue seleccionando las cuentas elegibles y generando los enlaces. Los enlaces caducan al cabo de una hora y se invalidan al guardar una contraseña nueva. En producción la aplicación envía las versiones de texto y HTML mediante `POST https://api.brevo.com/v3/smtp/email`. Render gratuito permite este tráfico por HTTPS en el puerto 443 y bloquea los puertos SMTP habituales. El flujo usa las tablas existentes de Django en PostgreSQL. [API de correo transaccional de Brevo](https://developers.brevo.com/reference/send-transac-email) · [Límites de Render gratuito](https://render.com/docs/free)

## Configuración en Render y Brevo

1. En Brevo, autentica el dominio remitente y verifica la dirección de envío. Crea una clave API con el acceso mínimo necesario para enviar correo transaccional. Conserva la clave en el entorno privado de Render. [Configuración de dominio](https://help.brevo.com/hc/en-us/articles/35337929909778-Set-up-your-domain-in-Brevo) · [Permisos de la clave API](https://help.brevo.com/hc/en-us/articles/40158277171474-About-API-key-permissions)
2. En la configuración transaccional de Brevo, selecciona la opción de no guardar previsualizaciones. El mensaje contiene un enlace de un solo uso. CutLess envía `contactPixelTrackingConsent=false`. Brevo lo considera si está habilitado el consentimiento de seguimiento por contacto, y puede seguir recopilando métricas agregadas. Verifica cómo se muestra el enlace en el mensaje recibido antes de habilitar el flujo para usuarios. [Retención de previsualizaciones](https://help.brevo.com/hc/en-us/articles/4415743225746-Configure-a-custom-retention-period-for-your-transactional-logs-and-email-previews) · [Parámetros de la API](https://developers.brevo.com/reference/send-transac-email)
3. Añade las variables al servicio web de Render cuando se autorice aplicar la configuración. Conserva `CUTLESS_ENV=production` y la clave persistente de Django. Incluye el dominio oficial en `CUTLESS_ALLOWED_HOSTS` y su origen HTTPS en `CUTLESS_CSRF_TRUSTED_ORIGINS`. Usa el comando con `gunicorn.conf.py` de la [guía de Render](PREPARACION_RENDER_SUPABASE.md#directorio-y-comandos-acordados). Verifica que el proxy y cualquier herramienta de observabilidad omitan URL, consulta, Referer, cabeceras y cuerpo en las rutas de recuperación.

| Variable | Valor |
| --- | --- |
| `CUTLESS_BREVO_RECOVERY_ENABLED` | `false` por defecto. Solo `true` activa el envío público y requiere los demás valores válidos. Mantenerlo apagado mientras se resuelve la diferencia de tiempos. |
| `CUTLESS_PASSWORD_RESET_HOST` | Dominio oficial, como `cutless.example.com`. Escribe solo el nombre DNS, sin esquema, puerto ni ruta. |
| `CUTLESS_BREVO_API_KEY` | Clave API privada de Brevo. |
| `CUTLESS_BREVO_SENDER_EMAIL` | Dirección verificada, como `recuperacion@example.com`. |
| `CUTLESS_BREVO_SENDER_NAME` | Nombre visible del remitente. Si se omite, se usa `CutLess`. |

En desarrollo se usa el backend de Django, de consola por defecto y en memoria en la suite. Con el interruptor apagado, producción responde con el mensaje genérico sin buscar la cuenta ni reservar cupo. Con el interruptor encendido, una configuración incompleta, un dominio no autorizado o un remitente inválido también impiden el envío. Los enlaces ya emitidos conservan su expiración normal. El correo general conserva SMTP cuando se configura. En producción, su backend predeterminado descarta mensajes.

## Prueba manual local de un solo correo

Ejecuta la herramienta en el mismo computador donde abrirás el enlace, desde la raíz del repositorio y con las dependencias de CutLess instaladas en `.venv`. Usa un remitente verificado en Brevo y un buzón de prueba de tu propiedad.

### Windows 11 y PowerShell

En una terminal nueva de PowerShell con Git y Python 3.13 instalados, crea un clon separado para la prueba. Si ya tienes esta rama en un clon y su entorno usa Python 3.13, continúa con el siguiente bloque desde la raíz de ese clon.

```powershell
git clone --single-branch --branch feature/recuperacion-password-brevo https://github.com/JJBossa/optimizador_materiales.git CutLess-brevo
Set-Location .\CutLess-brevo
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Ejecuta este bloque completo en PowerShell. `Read-Host -AsSecureString` oculta la entrada de la clave. La clave se usa como variable de entorno durante la prueba y `finally` elimina ambas variables incluso al cancelar el script. Usar el ejecutable de Python directamente evita activar el entorno virtual mediante un script de PowerShell.

```powershell
& {
    $claveBrevo = Read-Host 'Clave API de Brevo' -AsSecureString
    try {
        $env:CUTLESS_BREVO_API_KEY = [System.Net.NetworkCredential]::new('', $claveBrevo).Password
        $env:CUTLESS_BREVO_SENDER_EMAIL = Read-Host 'Remitente verificado en Brevo'
        & .\.venv\Scripts\python.exe -I -B .\tools\probar_recuperacion_brevo.py
    }
    finally {
        Remove-Item Env:\CUTLESS_BREVO_API_KEY, Env:\CUTLESS_BREVO_SENDER_EMAIL -ErrorAction SilentlyContinue
        $claveBrevo.Dispose()
    }
}
```

### Bash en Linux, macOS o Git Bash

```bash
(
  set +x
  IFS= read -r -s -p 'Clave API de Brevo (entrada oculta): ' CUTLESS_BREVO_API_KEY || exit 1
  printf '\n'
  IFS= read -r -p 'Remitente verificado en Brevo: ' CUTLESS_BREVO_SENDER_EMAIL || exit 1
  export CUTLESS_BREVO_API_KEY CUTLESS_BREVO_SENDER_EMAIL
  .venv/bin/python -I -B tools/probar_recuperacion_brevo.py
)
```

En Git Bash con un entorno virtual de Windows, usa `.venv/Scripts/python.exe` en la última línea en lugar de `.venv/bin/python`. La clave se lee como variable de entorno del subproceso y el comando se escribe sin incluir su valor.

### Autorizar y comprobar el envío

1. Introduce la dirección del buzón de prueba cuando la herramienta la solicite. Se crea una base SQLite temporal, una clave local de Django y una única cuenta llamada `recuperacion-prueba`. La herramienta aísla la configuración de Django de las variables de base de datos heredadas.
2. Revisa el origen local que aparece en la terminal. Escribe exactamente `ENVIAR UNA VEZ` para autorizar un único intento. El formulario de Django se ejecuta con CSRF, el mensaje se captura en memoria y se comprueba que tenga un solo destinatario y un enlace de restablecimiento local antes de enviarlo a Brevo por HTTPS. Cualquier otra respuesta cancela el envío.
3. Comprueba que Brevo acepte la solicitud y que el mensaje llegue. Abre en este equipo la URL `http://127.0.0.1:<puerto>/usuarios/reset-password/…`. Si el cliente de correo envuelve o bloquea el botón, usa el enlace original en el texto del mensaje. El puerto se elige al iniciar la prueba y el servidor escucha únicamente en `127.0.0.1`. La validación de dominio y HTTPS de producción sigue activa en su propia configuración.
4. Guarda una contraseña nueva y entra como `recuperacion-prueba`. En una ventana privada, abre de nuevo el enlace original y comprueba que Django lo rechace. Cierra la prueba con Ctrl+C para eliminar la base y los archivos temporales.

Si el proveedor no confirma la aceptación, consulta el panel de Brevo antes de autorizar otro intento. Un tiempo de espera puede ocurrir después de que Brevo haya aceptado el mensaje. Registra solo el resultado del intento y de la recepción. Evita conservar el enlace, la contraseña o la clave en capturas o registros.

## Comprobación y diagnóstico

En una prueba de entrega autorizada, solicita el restablecimiento para una cuenta de prueba controlada. Comprueba en el mensaje recibido que el destino es el dominio oficial por HTTPS. El evento `brevo_recuperacion_aceptada entrega=no_confirmada` indica que Brevo respondió `201`. En el panel transaccional de Brevo, busca la etiqueta `cutless-recuperacion` y comprueba el evento `Delivered` para la cuenta de prueba. Ese evento confirma la entrega al servidor de correo del destinatario. Comprueba también la recepción en el buzón. La aplicación registra eventos fijos y códigos de estado. La revisión de logs de los proveedores y del proxy queda pendiente de la prueba autorizada. [Logs transaccionales de Brevo](https://help.brevo.com/hc/en-us/articles/360021533839-Manage-your-transactional-logs-and-email-previews) · [Eventos de entrega](https://developers.brevo.com/docs/transactional-webhooks)

Un `401` o un `403` requiere revisar clave y permisos. Un `429` indica un límite de la API. El plan gratuito permite 300 envíos diarios y puede encolar correo transaccional al alcanzar la cuota, por lo que un enlace podría llegar vencido. La conexión usa un tiempo de espera de cinco segundos por operación de socket. Tras un fallo o un tiempo de espera no se reintenta automáticamente, porque Brevo podría haber aceptado el mensaje antes de que se perdiera la respuesta. [Límites de la API](https://developers.brevo.com/docs/api-limits) · [Cuota del plan gratuito](https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan)

## Solicitudes abusivas

El límite se aplica en producción al `POST /usuarios/recuperar-password/` para correos con formato válido. Cuenta hasta dos solicitudes por dirección normalizada en 30 minutos y hasta 30 solicitudes totales cada cinco minutos, antes de buscar la cuenta. Cada intento de envío reserva además un cupo de hasta 20 intentos en cinco minutos y 240 en 24 horas, incluidos los fallos del proveedor. Las ventanas son móviles. Si falta cupo o falla el contador, se omite el envío y se conserva el mensaje genérico. Si varias cuentas comparten correo, se deja de enviar para esa solicitud al primer error de Brevo.

Los procesos comparten dos filas reservadas de `django_session` mediante transacciones y bloqueos de fila en PostgreSQL. Sus claves tienen menos de ocho caracteres, por lo que Django 5.2 las rechaza como cookies. Una prueba comprueba que presentar una de esas claves al iniciar sesión tampoco modifica ni borra el contador. Las filas contienen marcas de tiempo y HMAC de direcciones normalizadas, sin correos en claro, credenciales ni tokens.

Los contadores descartan entradas vencidas al reservar cupo. La limpieza estándar de Django, `clearsessions`, borra las filas reservadas que hayan expirado y conserva las sesiones vigentes. Si no se ejecuta la limpieza, el limitador reutiliza sus dos filas y reinicia un contador al encontrarlo vencido. La primera inserción concurrente y la escritura de una sesión autenticada mientras se bloquea un contador se verificaron en PostgreSQL aislado.

La sección bajo bloqueo hace una lectura y, si concede cupo, una actualización. La llamada a Brevo queda fuera de la transacción. Las peticiones a un mismo contador se serializan y pueden esperar si hay una ráfaga. Una saturación general de conexiones o una interrupción de PostgreSQL también puede afectar a la aplicación. SQLite sirve para la prueba individual, mientras que la prueba de concurrencia requiere PostgreSQL. El limitador no requiere tablas, migraciones ni otro servicio.

El envío sigue siendo síncrono. En una medición local con Brevo simulado a 180 ms, la mediana antes del limitador fue de 182 ms para una cuenta activa, 1,5 ms para una inactiva y 1 ms para una desconocida, con ocho solicitudes de cada clase. Con el limitador activo, la mediana de las solicitudes admitidas fue de 183 ms para cuentas activas y 1,4 ms para inactivas y desconocidas. Las limitadas tardaron entre 0,8 y 1,4 ms de mediana. Se tomaron diez muestras de cada clase, tanto admitidas como limitadas. El límite reduce las mediciones repetidas por dirección pero una solicitud admitida puede revelar una diferencia. Una demora artificial ocuparía los procesos HTTP de Render y los fallos del proveedor podrían superar esa demora. Una cola duradera con un consumidor independiente permitiría responder antes de consultar la cuenta o enviar correo. Bajo las restricciones actuales no se ha habilitado una cola con garantías de entrega.

Una ráfaga con direcciones distintas todavía puede agotar el límite compartido y retrasar recuperaciones legítimas. Un tercero también puede consumir temporalmente el cupo de recuperación de una dirección. Un límite en el proxy o un desafío permitiría frenar ese tráfico antes de llegar a Django. Cualquier política por IP debe usar una dirección validada por el proxy, ya que las cabeceras aportadas por el cliente se pueden manipular. Mantén `CUTLESS_BREVO_RECOVERY_ENABLED=false` hasta verificar entregas y registros de infraestructura y resolver la enumeración por tiempo.

## Opción gratuita para separar la entrega de la respuesta HTTP

| Alternativa | Evaluación |
| --- | --- |
| Cloudflare Queues y Worker en plan Free | Recomendación para una prueba controlada. Ofrece consumo independiente, reintentos, 10.000 operaciones diarias y retención de 24 h. Cada mensaje pequeño consume normalmente tres operaciones y los reintentos y la cola de fallos consumen más. Requiere configurar un Worker y una cola externa. [Precios](https://developers.cloudflare.com/queues/platform/pricing/) · [Reintentos](https://developers.cloudflare.com/queues/configuration/batching-retries/) |
| Upstash QStash Free | Alternativa más sencilla para tráfico bajo. Hace la entrega HTTPS firmada directamente a Django, con 1.000 mensajes al día incluyendo reintentos. El límite se consume también con solicitudes para direcciones inexistentes. [Precios](https://upstash.com/pricing/qstash) · [Firmas](https://upstash.com/docs/qstash/howto/signature) |
| Supabase Queues | Cola duradera que requiere habilitar `pgmq` y crear estructuras en PostgreSQL. Queda fuera del alcance actual. [Guía de Supabase](https://supabase.com/docs/guides/queues/quickstart) |

Para eliminar la consulta de la cuenta de la respuesta pública, Django publicaría el mismo tipo de trabajo para todas las direcciones bien formadas y admitidas. Confirmaría la publicación duradera antes de devolver el mensaje genérico. El consumidor llamaría por HTTPS a un endpoint autenticado de Django. Ese endpoint comprobaría la vigencia del trabajo y consultaría la cuenta, generaría el token y enviaría el mensaje. La cola llevaría solo un identificador, un vencimiento y el correo cifrado. La clave de Brevo y los tokens permanecerían fuera de la cola.

Antes de habilitarlo habría que probar la firma, las entregas duplicadas, el manejo de resultados ambiguos de Brevo y el arranque en frío de Render. El consumidor debe reconocer la respuesta esperada de Django, ya que una página de arranque del proveedor no confirma que se procesó el trabajo. Los límites diarios de publicación deben dejar margen para reintentos y mantener el plan Free. Esta arquitectura está propuesta y pendiente de validación. Los hilos de Gunicorn y los archivos locales pierden trabajos al reiniciar o dormir la instancia. [Límites de Render gratuito](https://render.com/docs/free)
