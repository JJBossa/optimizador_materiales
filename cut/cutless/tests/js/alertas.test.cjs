const { test } = require('node:test');
const assert = require('node:assert/strict');
const { nombreCampana, respuestaValida } = require('../../static/cutless/js/alertas.js');

const origen = 'http://127.0.0.1:9215';
const opciones = { resumen: false, pagina: 1, origen };
const aviso = {
  id: 'proyectos:3', categoria: 'proyectos', prioridad: 'Alta', icono: '!',
  titulo: 'Proyecto atrasado', mensaje: '<img src=x> Proyecto «Ñ»', url: '/cutless/proyectos/3/',
};
const respuesta = { total: 101, categorias: { proyectos: 'Proyectos' }, siguiente: 2, alertas: [aviso] };

test('el texto accesible conserva el total real, incluido cero y singular', () => {
  assert.equal(nombreCampana(101), 'Notificaciones, 101 alertas activas');
  assert.equal(nombreCampana(0), 'Notificaciones, 0 alertas activas');
  assert.equal(nombreCampana(1), 'Notificaciones, 1 alerta activa');
  assert.equal(nombreCampana(null), 'Notificaciones');
});

test('valida resumen, página y texto especial recibido como datos', () => {
  assert.equal(respuestaValida(respuesta, opciones), true);
  assert.equal(respuestaValida({ total: 0, categorias: {} }, { ...opciones, resumen: true }), true);
  for (const datos of [null, { ...respuesta, total: '101' }, { ...respuesta, total: -1 },
    { ...respuesta, siguiente: 4 }, { ...respuesta, alertas: {} }, { ...respuesta, categorias: {} }]) {
    assert.equal(respuestaValida(datos, opciones), false);
  }
});

test('rechaza destinos externos, rutas de otro módulo y esquemas arbitrarios', () => {
  for (const url of ['//ajeno.example.test/proyectos/3/', 'https://ajeno.example.test/proyectos/3/',
    'javascript:alert(1)', '/\\ajeno.example.test/proyectos/3/', '/cutless/presupuestos/3/',
    '/cutless/proyectos/3/?privado=1', '/cutless/proyectos/0/']) {
    assert.equal(respuestaValida({ ...respuesta, alertas: [{ ...aviso, url }] }, opciones), false, url);
  }
});
