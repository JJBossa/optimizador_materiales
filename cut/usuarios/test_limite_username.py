from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse


class LimiteNombreUsuarioTests(TestCase):
    clave = 'Prueba-local.2-segura'
    datos = {'email': 'persona@example.test', 'password1': clave, 'password2': clave}

    def verificar_exceso(self, url, datos, cliente=None, formulario='form'):
        respuesta = (cliente or self.client).post(url, datos)
        self.assertEqual(respuesta.status_code, 200)
        form = respuesta.context[formulario]
        self.assertTrue(form.has_error('username', 'max_length'), form.errors)
        self.assertEqual(form['username'].value(), datos['username'])
        self.assertContains(respuesta, 'Usa como máximo 30 caracteres')

    def test_registro_publico_y_panel_de_alta_aceptan_hasta_30(self):
        admin = User.objects.create_superuser('administrador')
        privado = Client()
        privado.force_login(admin)
        for cliente, ruta, prefijo, extra in (
            (self.client, 'registro', 'J', {}),
            (privado, 'admin_dashboard', 'M', {'crear_usuario': '1', 'rol': 'usuario'}),
        ):
            with self.subTest(ruta=ruta):
                url = reverse(f'usuarios:{ruta}')
                exacto = prefijo + 'ñ' * 24 + '_@2.-'
                datos = {**self.datos, **extra}
                self.assertContains(cliente.get(url), 'maxlength="30"')
                cantidad = User.objects.count()
                # \uFB00 (ﬀ) pasa de una unidad a dos con NFKC.
                for invalido in (exacto + 'a', exacto[:-1] + 'ﬀ', '𝐀' * 16):
                    self.verificar_exceso(url, {**datos, 'username': invalido}, cliente)
                self.assertEqual(User.objects.count(), cantidad)
                self.assertEqual(cliente.post(url, {**datos, 'username': exacto}).status_code, 302)
                self.assertTrue(User.objects.filter(username=exacto).exists())

    def test_cuenta_historica_inicia_sesion_y_puede_editar_el_correo(self):
        historico = 'titular_27.' + 'ñ' * 139
        self.assertEqual(len(historico), 150)
        usuario = User.objects.create_user(historico, password=self.clave, email=self.datos['email'])
        acceso = reverse('usuarios:login')
        self.assertContains(self.client.get(acceso), 'maxlength="150"')
        respuesta = self.client.post(acceso, {'username': historico, 'password': self.clave})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.client.session['_auth_user_id'], str(usuario.pk))

        perfil = reverse('usuarios:perfil')
        respuesta = self.client.get(perfil)
        self.assertContains(respuesta, 'maxlength="30"')
        self.assertContains(respuesta, 'Puedes conservar el nombre guardado.')
        datos = {'editar_cuenta': '1', 'email': 'otra@example.test'}
        self.verificar_exceso(perfil, {**datos, 'username': 'Q' * 31}, formulario='cuenta_form')
        usuario.refresh_from_db()
        self.assertEqual(usuario.email, self.datos['email'])
        self.assertEqual(self.client.post(perfil, {**datos, 'username': historico}).status_code, 302)
        usuario.refresh_from_db()
        self.assertEqual((usuario.username, usuario.email), (historico, datos['email']))
        exacto = 'ñ' * 25 + '_@2.-'
        self.assertEqual(self.client.post(perfil, {**datos, 'username': exacto}).status_code, 302)
        usuario.refresh_from_db()
        self.assertEqual(usuario.username, exacto)

    def test_edicion_de_usuarios_de_cutless_y_django_preserva_el_valor_literal(self):
        admin = User.objects.create_superuser('administrador')
        # Una importación directa pudo almacenar una grafía que hoy Django normaliza.
        historico = 'Ａ' * 27 + ' @LEGADO'
        usuario = User.objects.create(username=historico)
        datos = {'email': 'administrado@example.test', 'is_active': 'on',
                 'date_joined_0': '2026-01-01', 'date_joined_1': '12:00:00'}
        self.client.force_login(admin)
        for ruta in ('usuarios:editar_usuario', 'admin:auth_user_change'):
            with self.subTest(ruta=ruta):
                url = reverse(ruta, args=[usuario.pk])
                self.assertContains(self.client.get(url), 'maxlength="30"')
                self.assertContains(self.client.get(url), 'Puedes conservar el nombre guardado.')
                invalido = 'X' * 31
                respuesta = self.client.post(url, {**datos, 'username': invalido})
                self.assertContains(respuesta, 'Usa como máximo 30 caracteres')
                self.assertEqual(User.objects.get(pk=usuario.pk).username, historico)
                self.assertEqual(self.client.post(url, {**datos, 'username': historico}).status_code, 302)
                usuario.refresh_from_db()
                self.assertEqual((usuario.username, usuario.email), (historico, datos['email']))
                exacto = 'É' * 25 + '_@3.-'
                self.assertEqual(self.client.post(url, {**datos, 'username': exacto}).status_code, 302)
                usuario.refresh_from_db()
                self.assertEqual(usuario.username, exacto)
                User.objects.filter(pk=usuario.pk).update(username=historico)

        intruso = User.objects.create_user('intruso')
        self.client.force_login(intruso)
        for ruta in ('usuarios:editar_usuario', 'admin:auth_user_change'):
            url = reverse(ruta, args=[usuario.pk])
            self.assertIn('login', self.client.post(url, {**datos, 'username': 'alterado'}).url)
        usuario.refresh_from_db()
        self.assertEqual(usuario.username, historico)

    def test_django_admin_rechaza_alta_excedida_y_acepta_limite(self):
        self.client.force_login(User.objects.create_superuser('administrador'))
        url = reverse('admin:auth_user_add')
        self.assertContains(self.client.get(url), 'maxlength="30"')
        datos = {'usable_password': 'false'}
        self.assertContains(self.client.post(url, {**datos, 'username': 'V' * 31}), 'Usa como máximo 30 caracteres')
        self.assertFalse(User.objects.filter(username='V' * 31).exists())
        self.assertEqual(self.client.post(url, {**datos, 'username': 'V' * 30}).status_code, 302)
        self.assertTrue(User.objects.filter(username='V' * 30).exists())

    def test_createsuperuser_valida_el_nombre_antes_de_crear_la_cuenta(self):
        opciones = {'interactive': False, 'email': 'admin@example.test', 'stdout': StringIO()}
        for invalido in ('ñ' * 31, 'ñ' * 29 + 'ﬀ'):
            with self.subTest(invalido=invalido), self.assertRaisesMessage(CommandError, 'Usa como máximo 30'):
                call_command('createsuperuser', username=invalido, **opciones)
        self.assertFalse(User.objects.exists())
        call_command('createsuperuser', username='ñ' * 30, **opciones)
        self.assertTrue(User.objects.get(username='ñ' * 30).is_superuser)
