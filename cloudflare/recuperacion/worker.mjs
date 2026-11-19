const RUTA = "/usuarios/interno/recuperacion-cola/";
const encoder = new TextEncoder();
const VIGENCIA_SEGUNDOS = 900;
const MAX_CUERPO = 2048;

function urlConsumo(valor) {
  try {
    const url = new URL(valor);
    if (url.protocol === "https:" && !url.port && !url.username && !url.password &&
        !url.search && !url.hash && url.pathname === RUTA) {
      return url.href;
    }
  } catch {
    // La configuración puede faltar. La entrega se reintentará sin exponer su valor.
  }
  return null;
}

function sobreValido(sobre, ahora) {
  return sobre !== null && typeof sobre === "object" && Object.keys(sobre).length === 5 &&
    sobre.v === 1 && Number.isSafeInteger(sobre.exp) &&
    sobre.exp > ahora && sobre.exp <= ahora + VIGENCIA_SEGUNDOS + 30 &&
    typeof sobre.id === "string" && /^[0-9a-f]{32}$/.test(sobre.id) &&
    typeof sobre.nonce === "string" && /^[A-Za-z0-9_-]{16}$/.test(sobre.nonce) &&
    typeof sobre.data === "string" && sobre.data.length <= MAX_CUERPO &&
    /^[A-Za-z0-9_-]+={0,2}$/.test(sobre.data);
}

async function entregar(url, claveHex, cuerpo, ahora) {
  const clave = Uint8Array.from(claveHex.match(/../g), (par) => Number.parseInt(par, 16));
  const firmante = await crypto.subtle.importKey(
    "raw", clave, {name: "HMAC", hash: "SHA-256"}, false, ["sign"],
  );
  const firmado = encoder.encode(`cutless.queue.callback.v1\n${ahora}\n${cuerpo}`);
  const mac = new Uint8Array(await crypto.subtle.sign("HMAC", firmante, firmado));
  const firma = Array.from(mac, (byte) => byte.toString(16).padStart(2, "0")).join("");
  const respuesta = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Cutless-Timestamp": String(ahora),
      "X-Cutless-Signature": firma,
    },
    body: cuerpo,
    redirect: "manual",
    signal: AbortSignal.timeout(20000),
  });
  const confirmado = respuesta.status === 204 && respuesta.headers.get("X-Cutless-Queue") === "ack-v1";
  await respuesta.body?.cancel();
  return confirmado;
}

export default {
  async queue(lote, env) {
    const url = urlConsumo(env.CUTLESS_RECOVERY_CALLBACK_URL);
    const clave = env.CUTLESS_RECOVERY_QUEUE_HMAC_KEY;
    for (const mensaje of lote.messages) {
      const ahora = Math.floor(Date.now() / 1000);
      if (!sobreValido(mensaje.body, ahora)) {
        mensaje.ack();
        continue;
      }
      const cuerpo = JSON.stringify(mensaje.body);
      if (encoder.encode(cuerpo).length > MAX_CUERPO) {
        mensaje.ack();
        continue;
      }
      try {
        if (url && typeof clave === "string" && /^[0-9a-fA-F]{64}$/.test(clave) &&
            await entregar(url, clave, cuerpo, ahora)) {
          mensaje.ack();
          console.info("cola_recuperacion_confirmada");
          continue;
        }
      } catch {
        // Un error de red puede ocurrir tras procesar el trabajo. Django conserva su identificador.
      }
      mensaje.retry();
      console.warn("cola_recuperacion_sin_acuse");
    }
  },
};
