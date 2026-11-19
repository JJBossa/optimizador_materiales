import assert from "node:assert/strict";
import { createHmac, randomBytes } from "node:crypto";
import { test } from "node:test";
import worker from "./worker.mjs";

const url = "https://cutless.example.test/usuarios/interno/recuperacion-cola/";
const clave = randomBytes(32);
const env = {
  CUTLESS_RECOVERY_CALLBACK_URL: url,
  CUTLESS_RECOVERY_QUEUE_HMAC_KEY: clave.toString("hex"),
};

function mensaje(cambios = {}) {
  const acciones = [];
  return {
    body: {
      v: 1,
      id: randomBytes(16).toString("hex"),
      nonce: randomBytes(12).toString("base64url"),
      data: randomBytes(32).toString("base64url"),
      exp: Math.floor(Date.now() / 1000) + 300,
      ...cambios,
    },
    acciones,
    ack: () => acciones.push("ack"),
    retry: (opciones) => acciones.push(opciones ? ["retry", opciones.delaySeconds] : "retry"),
  };
}

test("firma el cuerpo exacto y confirma el acuse explícito de Django", async (t) => {
  const trabajo = mensaje();
  const fetch = t.mock.method(globalThis, "fetch", async (destino, opciones) => {
    assert.equal(destino, url);
    assert.equal(opciones.method, "POST");
    assert.equal(opciones.redirect, "manual");
    assert.deepEqual(JSON.parse(opciones.body), trabajo.body);
    const fecha = opciones.headers["X-Cutless-Timestamp"];
    const entrada = `cutless.queue.callback.v1\n${fecha}\n${opciones.body}`;
    const firma = createHmac("sha256", clave).update(entrada).digest("hex");
    assert.equal(opciones.headers["X-Cutless-Signature"], firma);
    return new Response(null, {status: 204, headers: {"X-Cutless-Queue": "ack-v1"}});
  });
  await worker.queue({messages: [trabajo]}, env);
  assert.equal(fetch.mock.callCount(), 1);
  assert.deepEqual(trabajo.acciones, ["ack"]);
});

test("reintenta sin seguir redirects ni tomar la página de arranque por un acuse", async (t) => {
  for (const respuesta of [
    () => new Response("Iniciando", {status: 200}),
    () => new Response(null, {status: 204}),
    () => new Response(null, {status: 302, headers: {Location: "https://otro.example.test/"}}),
    () => new Response(null, {status: 503}),
    () => { throw new Error("error simulado"); },
  ]) {
    const trabajo = mensaje();
    const fetch = t.mock.method(globalThis, "fetch", respuesta);
    await worker.queue({messages: [trabajo]}, env);
    assert.equal(fetch.mock.callCount(), 1);
    assert.deepEqual(trabajo.acciones, ["retry"]);
    fetch.mock.restore();
  }
});

test("descarta sobres inválidos, demasiado grandes o vencidos sin llamar a Django", async (t) => {
  const trabajos = [
    mensaje({exp: Math.floor(Date.now() / 1000) - 1}),
    mensaje({id: "malformado"}),
    mensaje({data: "a".repeat(2048)}),
    mensaje({email: "dato@example.test"}),
  ];
  const fetch = t.mock.method(globalThis, "fetch");
  await worker.queue({messages: trabajos}, env);
  assert.equal(fetch.mock.callCount(), 0);
  assert.ok(trabajos.every((trabajo) => trabajo.acciones.join() === "ack"));
});

test("una URL insegura o una firma sin configurar impiden la entrega", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch");
  for (const cambios of [
    {CUTLESS_RECOVERY_CALLBACK_URL: url.replace("https:", "http:")},
    {CUTLESS_RECOVERY_CALLBACK_URL: `${url}?dato=1`},
    {CUTLESS_RECOVERY_QUEUE_HMAC_KEY: ""},
  ]) {
    const trabajo = mensaje();
    await worker.queue({messages: [trabajo]}, {...env, ...cambios});
    assert.deepEqual(trabajo.acciones, ["retry"]);
  }
  assert.equal(fetch.mock.callCount(), 0);
  assert.equal(worker.fetch, undefined);
});

test("los errores del callback registran solo un evento fijo", async (t) => {
  const trabajo = mensaje();
  const aviso = t.mock.method(console, "warn", () => {});
  t.mock.method(globalThis, "fetch", async () => {
    throw new Error(`dato@example.test ${env.CUTLESS_RECOVERY_QUEUE_HMAC_KEY} ${trabajo.body.data}`);
  });
  await worker.queue({messages: [trabajo]}, env);
  assert.deepEqual(trabajo.acciones, ["retry"]);
  assert.deepEqual(aviso.mock.calls.map(({arguments: args}) => args), [["cola_recuperacion_sin_acuse"]]);
});

test("403 reintenta sin registrar el contenido de la respuesta", async (t) => {
  const trabajo = mensaje();
  const aviso = t.mock.method(console, "warn", () => {});
  t.mock.method(globalThis, "fetch", async () => new Response("dato@example.test", {status: 403}));
  await worker.queue({messages: [trabajo]}, env);
  assert.deepEqual(trabajo.acciones, ["retry"]);
  assert.deepEqual(aviso.mock.calls.map(({arguments: args}) => args), [
    ["cola_recuperacion_acceso_rechazado"], ["cola_recuperacion_sin_acuse"],
  ]);
});

test("429 y 503 respetan Retry-After válido y dejan de insistir al vencer el sobre", async (t) => {
  const aviso = t.mock.method(console, "warn", () => {});
  for (const [estado, cabecera, esperado] of [
    [429, "25", [["retry", 25]]],
    [503, "70", [["retry", 70]]],
    [503, "inválido", ["retry"]],
    [429, "400", ["ack"]],
  ]) {
    const trabajo = mensaje();
    const fetch = t.mock.method(globalThis, "fetch", async () => (
      new Response(null, {status: estado, headers: {"Retry-After": cabecera}})
    ));
    await worker.queue({messages: [trabajo]}, env);
    assert.deepEqual(trabajo.acciones, esperado);
    fetch.mock.restore();
  }
  assert.deepEqual(aviso.mock.calls.at(-1).arguments, ["cola_recuperacion_reintento_fuera_de_vigencia"]);
});

test("el timeout permite otra entrega del mismo id y respeta el acuse terminal", async (t) => {
  const trabajo = mensaje();
  const repetido = mensaje(trabajo.body);
  const aviso = t.mock.method(console, "warn", () => {});
  const senal = t.mock.method(AbortSignal, "timeout", () => AbortSignal.abort(
    new DOMException("Tiempo simulado", "TimeoutError"),
  ));
  const fetch = t.mock.method(globalThis, "fetch", async (_, opciones) => {
    assert.deepEqual(JSON.parse(opciones.body), trabajo.body);
    opciones.signal.throwIfAborted();
  });
  await worker.queue({messages: [trabajo]}, env);
  assert.deepEqual(senal.mock.calls[0].arguments, [20000]);
  assert.deepEqual(trabajo.acciones, ["retry"]);
  senal.mock.restore();
  fetch.mock.mockImplementation(async (_, opciones) => {
    assert.deepEqual(JSON.parse(opciones.body), trabajo.body);
    return new Response(null, {status: 204, headers: {
      "X-Cutless-Queue": "ack-v1", "X-Cutless-Outcome": "ambiguo",
    }});
  });
  await worker.queue({messages: [repetido]}, env);
  assert.deepEqual(repetido.acciones, ["ack"]);
  assert.deepEqual(aviso.mock.calls.map(({arguments: args}) => args), [
    ["cola_recuperacion_sin_acuse"], ["cola_recuperacion_entrega_ambigua"],
  ]);
});
