from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.db import DataError, connection, transaction
from django.test import Client, TestCase
from django.urls import reverse

from cutless.models import Optimizacion


class LoteOptimizacionTests(TestCase):
    def setUp(self):
        self.propietario = User.objects.create_user("propietario-sintetico")
        self.otro = User.objects.create_user("otro-sintetico")
        self.limite = Optimizacion._meta.get_field("nombre").max_length

    def plan(self, propietario, nombre):
        return Optimizacion(
            usuario=propietario, nombre=nombre, ancho_tablero=122, alto_tablero=244,
            piezas="Pieza,40,50,1",
        )

    def test_lote_al_limite_conserva_nombres_y_correlativos_por_propietario(self):
        nombre = "ñ" * self.limite
        lote = Optimizacion.objects.bulk_create([
            self.plan(self.propietario, nombre),
            self.plan(self.otro, nombre),
            self.plan(self.propietario, "Segundo"),
        ], batch_size=1)
        self.assertEqual([plan.correlativo for plan in lote], [1, 1, 2])
        self.assertEqual(
            list(Optimizacion.objects.filter(usuario=self.propietario).order_by("correlativo")
                 .values_list("nombre", flat=True)),
            [nombre, "Segundo"],
        )

    def test_lote_fuera_del_limite_conserva_registros_y_reserva_al_revertir(self):
        if connection.vendor not in {"postgresql", "sqlite"}:
            self.skipTest("Contratos de longitud verificados para PostgreSQL y SQLite")
        Optimizacion.objects.bulk_create([self.plan(self.propietario, "Existente")])
        validos_e_invalido = [
            self.plan(self.propietario, "Primero del lote"),
            self.plan(self.propietario, "x" * (self.limite + 1)),
            self.plan(self.otro, "Otro propietario"),
        ]
        if connection.vendor == "postgresql":
            with self.assertRaises(DataError):
                Optimizacion.objects.bulk_create(validos_e_invalido, batch_size=1)
        else:
            # SQLite no aplica el límite VARCHAR. Revertimos explícitamente el ensayo.
            with transaction.atomic():
                lote = Optimizacion.objects.bulk_create(validos_e_invalido, batch_size=1)
                self.assertEqual(Optimizacion.objects.get(pk=lote[1].pk).nombre, lote[1].nombre)
                transaction.set_rollback(True)
        self.assertEqual(
            list(Optimizacion.objects.values_list("usuario_id", "nombre", "correlativo")),
            [(self.propietario.pk, "Existente", 1)],
        )
        lote = Optimizacion.objects.bulk_create([
            self.plan(self.propietario, "Siguiente"), self.plan(self.otro, "Primero"),
        ])
        self.assertEqual([plan.correlativo for plan in lote], [2, 1])


class HttpYSesionTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.login_url = reverse("usuarios:login")
        self.actividad_url = reverse("usuarios:actividad_sesion")
        self.historial_url = reverse("cutless:historial")
        self.datos = {"username": "cuenta-sintetica", "password": "SoloParaPruebas-LTS-42"}
        self.usuario = User.objects.create_user(**self.datos)
        self.usuario.perfil.timeout_sesion = 1
        self.usuario.perfil.save(update_fields=["timeout_sesion"])

    def token_csrf(self):
        return self.client.cookies[settings.CSRF_COOKIE_NAME].value

    def iniciar_sesion(self):
        self.assertEqual(self.client.get(self.login_url).status_code, 200)
        respuesta = self.client.post(self.login_url, {
            **self.datos, "csrfmiddlewaretoken": self.token_csrf(),
        })
        self.assertEqual(respuesta.status_code, 302)
        clave = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertEqual(Session.objects.get(pk=clave).get_decoded()[SESSION_KEY], str(self.usuario.pk))
        return clave

    def test_login_multipart_valido_con_cabeceras_acotadas(self):
        respuesta = self.client.get(
            self.login_url, HTTP_ACCEPT_LANGUAGE="es-CL,es;q=0.8",
            HTTP_ACCEPT='text/html; profile="' + "x" * 128 + '"',
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.client.post(self.login_url, {
            **self.datos, "csrfmiddlewaretoken": self.token_csrf(),
        }).status_code, 302)
        self.assertEqual(self.client.get(self.historial_url).status_code, 200)

    def test_multipart_sin_delimitador_devuelve_400_y_no_crea_sesion(self):
        self.assertEqual(self.client.get(self.login_url).status_code, 200)
        sesiones = list(Session.objects.values_list("pk", "session_data", "expire_date"))
        respuesta = self.client.post(self.login_url, b"datos sinteticos",
                                     content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(list(Session.objects.values_list("pk", "session_data", "expire_date")), sesiones)
        self.assertRedirects(self.client.get(self.historial_url),
                             f"{self.login_url}?next={self.historial_url}", fetch_redirect_response=False)

    def test_actividad_renueva_sesion_y_la_inactividad_posterior_expira(self):
        inicio = datetime(2026, 11, 22, 12, tzinfo=UTC)
        with patch("django.utils.timezone.now", return_value=inicio) as reloj:
            clave = self.iniciar_sesion()
            # La primera plantilla consume la marca de bienvenida de la sesión.
            self.assertEqual(self.client.get(self.historial_url).status_code, 200)
            vence = inicio + timedelta(minutes=1)
            self.assertEqual(Session.objects.get(pk=clave).expire_date, vence)
            reloj.return_value = inicio + timedelta(seconds=30)
            self.assertEqual(self.client.post(self.actividad_url, HTTP_ACCEPT="application/json").status_code, 403)
            self.assertEqual(self.client.get(self.historial_url).status_code, 200)
            self.assertEqual(Session.objects.get(pk=clave).expire_date, vence)
            respuesta = self.client.post(self.actividad_url, HTTP_X_CSRFTOKEN=self.token_csrf())
            self.assertEqual(respuesta.json(), {"active": True})
            vence += timedelta(seconds=30)
            self.assertEqual(Session.objects.get(pk=clave).expire_date, vence)
            reloj.return_value = vence - timedelta(seconds=1)
            self.assertEqual(self.client.get(self.historial_url).status_code, 200)
            reloj.return_value = vence + timedelta(seconds=1)
            self.assertRedirects(self.client.get(self.historial_url),
                                 f"{self.login_url}?next={self.historial_url}", fetch_redirect_response=False)
            self.assertEqual(self.client.post(self.actividad_url,
                             HTTP_X_CSRFTOKEN=self.token_csrf()).status_code, 401)

    def test_logout_invalida_sesion_antes_del_vencimiento(self):
        with patch("django.utils.timezone.now", return_value=datetime(2026, 11, 22, 12, tzinfo=UTC)):
            clave = self.iniciar_sesion()
            respuesta = self.client.post(reverse("usuarios:logout"), HTTP_X_CSRFTOKEN=self.token_csrf())
            self.assertRedirects(respuesta, self.login_url, fetch_redirect_response=False)
            self.assertFalse(Session.objects.filter(pk=clave).exists())
            self.client.cookies[settings.SESSION_COOKIE_NAME] = clave
            self.assertRedirects(self.client.get(self.historial_url),
                                 f"{self.login_url}?next={self.historial_url}", fetch_redirect_response=False)
