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
| `CUTLESS_RECOVERY_QUEUE_CONSUMER_ENABLED` | `false` por defecto. Habilita el endpoint de entrega firmado y permite probar una sonda con el envío público apagado. |
| `CUTLESS_RECOVERY_QUEUE_ACCOUNT_ID`, `CUTLESS_RECOVERY_QUEUE_ID` | ID de la cuenta Cloudflare y de la cola existente `cutless-recuperacion`. Son IDs hexadecimales, separados del nombre de la cola. |
| `CUTLESS_RECOVERY_QUEUE_API_TOKEN` | Token de la API de Cloudflare limitado a esa cuenta con permiso **Queues Edit**. |
| `CUTLESS_RECOVERY_QUEUE_ENCRYPTION_KEY` | 32 bytes aleatorios en hexadecimal. Solo Django cifra y descifra con esta clave. |
| `CUTLESS_RECOVERY_QUEUE_HMAC_KEY` | Otros 32 bytes aleatorios en hexadecimal, compartidos solo entre Django y el Worker. |

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

Antes de integrar la cola, con Brevo simulado a 180 ms, las peticiones admitidas para cuentas activas tardaban 183 ms de mediana y las inactivas o desconocidas 1,4 ms. La publicación en la cola elimina de esa petición la consulta de la cuenta y la comunicación con Brevo. La latencia aún puede variar por los límites aplicados y la disponibilidad de Cloudflare. La activación pública requiere una verificación desde el entorno real.

Una ráfaga con direcciones distintas todavía puede agotar el límite compartido y retrasar recuperaciones legítimas. Un tercero también puede consumir temporalmente el cupo de recuperación de una dirección. Un límite en el proxy o un desafío permitiría frenar ese tráfico antes de llegar a Django. Cualquier política por IP debe usar una dirección validada por el proxy, ya que las cabeceras aportadas por el cliente se pueden manipular. Mantén `CUTLESS_BREVO_RECOVERY_ENABLED=false` hasta verificar entregas y registros de infraestructura y resolver la enumeración por tiempo.

## Arquitectura de Cloudflare Queues

1. En producción, el formulario con CSRF verifica el formato y aplica los límites antes de cualquier consulta de la cuenta. Si está habilitado, Django publica de forma síncrona en la API de Queues y devuelve el mensaje genérico, incluso si falla la publicación. El límite adicional es de 1.000 intentos de publicación por 24 horas. El entorno local sigue usando el correo en memoria para la prueba manual con Brevo. [Publicación mediante HTTP](https://developers.cloudflare.com/queues/examples/publish-to-a-queue-via-http/)
2. La cola contiene un identificador aleatorio, un vencimiento de 15 minutos, un nonce y el correo cifrado con AES-256-GCM. El cifrado autentica también el identificador y el vencimiento. El Worker carece de la clave de cifrado y de las credenciales de Brevo. Solo tiene la URL HTTPS exacta y la clave de firma del callback.
3. El Worker firma la marca de tiempo y el cuerpo con HMAC-SHA-256. Django exige HTTPS, una firma válida con hasta cinco minutos de diferencia y un sobre vigente. El callback se autentica sin cookies. La excepción CSRF corresponde solo a este endpoint de máquina. El formulario público conserva CSRF.
4. Django reclama cada identificador dentro de una transacción PostgreSQL, antes de buscar la cuenta. El registro `reset:j` y el contador `reset:q` son filas técnicas de `django_session`, con claves que Django rechaza como cookies. Solo guardan identificadores y vencimientos o marcas de tiempo. Después de confirmar la transacción, Django comprueba la elegibilidad, genera el token y entrega por Brevo. El límite de envíos existente sigue vigente.
5. El Worker solo reconoce un `204` acompañado por `X-Cutless-Queue: ack-v1`. Reintenta si la instancia está arrancando, el callback falla o el acuse falta. Una reentrega de un trabajo reclamado recibe el acuse sin repetir el envío.

**Límite de entrega.** Si el proceso se interrumpe después de confirmar el reclamo y antes de enviar, ese correo puede perderse. Una respuesta ambigua de Brevo tampoco se reintenta automáticamente, porque el proveedor puede haber aceptado el mensaje. El acuse del Worker termina el procesamiento del trabajo. Para confirmar la entrega del correo se requiere el evento `Delivered` de Brevo.

La configuración usa un consumidor concurrente, lotes de un mensaje y hasta tres reintentos con 90 segundos de espera. Con sobres pequeños, 1.000 publicaciones y tres reintentos por mensaje implican hasta aproximadamente 6.000 operaciones. El plan Free incluye 10.000 operaciones diarias compartidas por cuenta y retención de 24 horas. El vencimiento de 15 minutos de CutLess se aplica aunque Cloudflare conserve el sobre más tiempo. Los trabajos pueden descartarse cuando se agotan los reintentos. Esta configuración solo utiliza `cutless-recuperacion`, sin cola adicional para fallos. [Precios](https://developers.cloudflare.com/queues/platform/pricing/) · [Reintentos de Cloudflare](https://developers.cloudflare.com/queues/configuration/batching-retries/)

## Prueba controlada con la cola existente

La integración se verifica localmente con servicios simulados. Los pasos siguientes se ejecutan por separado cuando decidas conectar el Worker real. Mantén `CUTLESS_BREVO_RECOVERY_ENABLED=false`. La sonda cifrada no lleva un correo. El servidor de prueba usa SQLite temporal, funciona sin credenciales de Brevo y rechaza los trabajos que contienen una dirección, incluso con firma válida. No se necesita modificar Render o Supabase.

1. En **Cloudflare → Queues → cutless-recuperacion**, comprueba que la cola está en el plan Free, sin trabajos reales pendientes ni otro consumidor que deba conservarse. Wrangler usará esa cola por nombre desde [wrangler.jsonc](../cloudflare/recuperacion/wrangler.jsonc).
2. Desde una terminal, abre un túnel temporal al puerto de la sonda. Copia el host `*.trycloudflare.com` que aparece en la salida. Mantén esa terminal abierta. [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8765
   ```

3. Desde la raíz de la rama local, con las dependencias de `requirements.txt` instaladas, usa PowerShell para generar claves de prueba y abrir el receptor en otra ventana. Introduce únicamente el host del túnel, sin `https://`.

   ```powershell
   $hostTunel = Read-Host 'Host de Quick Tunnel'
   $env:CUTLESS_RECOVERY_QUEUE_ENCRYPTION_KEY = & .\.venv\Scripts\python.exe -I -B -c "import secrets; print(secrets.token_hex(32))"
   $env:CUTLESS_RECOVERY_QUEUE_HMAC_KEY = & .\.venv\Scripts\python.exe -I -B -c "import secrets; print(secrets.token_hex(32))"
   Start-Process -FilePath .\.venv\Scripts\python.exe -ArgumentList '-I','-B','.\tools\probar_cola_recuperacion.py','servir','--host',$hostTunel
   ```

4. Cuando autorices el despliegue de prueba, inicia sesión en la cuenta Free correcta y ejecuta el bloque siguiente. Wrangler conecta el Worker a `cutless-recuperacion` a partir de la configuración. El Worker carece de una ruta HTTP pública. La clave AES queda en tu terminal de prueba. El archivo de secretos vive fuera del repositorio y se elimina al salir. [Secretos de Wrangler](https://developers.cloudflare.com/workers/configuration/secrets/)

   ```powershell
   npx.cmd --yes wrangler@4.165.0 login
   npx.cmd --yes wrangler@4.165.0 queues info cutless-recuperacion
   if ($LASTEXITCODE -ne 0) { throw 'La cola existente no está disponible en esta cuenta.' }
   $archivo = Join-Path ([IO.Path]::GetTempPath()) ('cutless-' + [guid]::NewGuid().ToString() + '.json')
   try {
       @{
           CUTLESS_RECOVERY_QUEUE_HMAC_KEY = $env:CUTLESS_RECOVERY_QUEUE_HMAC_KEY
           CUTLESS_RECOVERY_CALLBACK_URL = "https://$hostTunel/usuarios/interno/recuperacion-cola/"
       } | ConvertTo-Json -Compress | Set-Content -LiteralPath $archivo -Encoding ascii
       npx.cmd --yes wrangler@4.165.0 deploy --config cloudflare/recuperacion/wrangler.jsonc --secrets-file $archivo
       if ($LASTEXITCODE -ne 0) { throw 'Wrangler no confirmó el despliegue de prueba.' }
   } finally {
       Remove-Item -LiteralPath $archivo -ErrorAction SilentlyContinue
   }
   ```

5. En el panel de la cola comprueba que **Consumers** muestre `cutless-recuperacion-consumer`. Genera el mensaje justo antes de enviarlo y copia el JSON completo. En **Queues → cutless-recuperacion → Messages → Send**, selecciona **JSON**, pega el sobre y envíalo una sola vez. Es el sobre, sin envolverlo con un campo `body` al usar el panel. [Enviar mensajes desde el panel](https://developers.cloudflare.com/queues/examples/send-messages-from-dash/)

   ```powershell
   & .\.venv\Scripts\python.exe -I -B .\tools\probar_cola_recuperacion.py mensaje
   ```

6. Confirma `cola_recuperacion_sonda_confirmada` en la ventana del receptor y que el mensaje se consumió en las métricas de la cola. Si queda pendiente, comprueba que el túnel sigue visible, que se usó el mismo HMAC y que la sonda no caducó. Al finalizar, quita el consumidor temporal desde el panel conservando la cola. Cierra el receptor y el túnel con Ctrl+C y elimina las variables de prueba.

   ```powershell
   Remove-Item Env:\CUTLESS_RECOVERY_QUEUE_ENCRYPTION_KEY, Env:\CUTLESS_RECOVERY_QUEUE_HMAC_KEY -ErrorAction SilentlyContinue
   ```

La sonda comprueba la entrega firmada a través de Cloudflare. La activación pública y la entrega real por Brevo quedan pendientes de verificar por separado con claves de producción, el host oficial y el comportamiento del arranque en frío de Render. [Límites de Render gratuito](https://render.com/docs/free)
