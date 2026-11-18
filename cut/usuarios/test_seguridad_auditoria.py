from datetime import datetime, timedelta
from unittest.mock import patch

from django.core import mail
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


class JerarquiaAdministrativaTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('operador')
        self.admin.perfil.rol = 'admin'
        self.admin.perfil.save(update_fields=['rol'])
        self.superusuario = User.objects.create_superuser('supervisor', password='clave-original-29')
        self.cuenta = User.objects.create_user('cuenta', email='cuenta@example.test')
        self.client.force_login(self.admin)

    def test_administrador_no_puede_modificar_ni_eliminar_superusuario(self):
        datos = {'username': 'alterado', 'password1': 'clave-nueva-31',
                 'password2': 'clave-nueva-31', 'rol': 'usuario'}
        for accion in ('editar_usuario', 'actualizar_rol', 'eliminar_usuario'):
            with self.subTest(accion=accion):
                respuesta = self.client.post(reverse('usuarios:' + accion, args=[self.superusuario.pk]), datos)
                self.assertEqual(respuesta.status_code, 403)
        self.superusuario.refresh_from_db()
        self.assertTrue(self.superusuario.is_superuser)
        self.assertTrue(self.superusuario.is_staff)
        self.assertEqual(self.superusuario.username, 'supervisor')
        self.assertTrue(self.superusuario.check_password('clave-original-29'))

    def test_roles_desconocidos_y_promocion_sin_autorizar(self):
        url = reverse('usuarios:actualizar_rol', args=[self.cuenta.pk])
        self.assertEqual(self.client.post(url, {'rol': 'admin'}).status_code, 403)
        self.assertEqual(self.client.post(url, {'rol': 'superuser'}).status_code, 400)
        self.assertEqual(self.client.post(reverse('usuarios:admin_dashboard'), {
            'crear_usuario': '1', 'rol': 'admin', 'username': 'nueva',
        }).status_code, 403)
        self.cuenta.refresh_from_db()
        self.assertFalse(self.cuenta.is_staff)
        self.assertFalse(User.objects.filter(username='nueva').exists())

    def test_superusuario_puede_editar_y_aplica_validadores(self):
        self.client.force_login(self.superusuario)
        url = reverse('usuarios:editar_usuario', args=[self.cuenta.pk])
        datos = {'username': 'renombrada', 'email': 'cuenta@example.test'}
        respuesta = self.client.post(url, {**datos, 'password1': '12345678', 'password2': '12345678'})
        self.assertIn('password1', respuesta.context['form'].errors)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.username, 'cuenta')
        requisitos = {'password1': 'Bosque-41-Magnolia', 'password2': 'Bosque-41-Magnolia'}
        self.assertEqual(self.client.post(url, {**datos, **requisitos}).status_code, 302)
        self.cuenta.refresh_from_db()
        self.assertTrue(self.cuenta.check_password(requisitos['password1']))

    def test_edicion_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.superusuario)
        url = reverse('usuarios:editar_usuario', args=[self.cuenta.pk])
        self.assertEqual(cliente.post(url, {'username': 'alterado'}).status_code, 403)


class RecuperacionTests(TestCase):
    def test_respuesta_generica_y_cuentas_elegibles_con_correo_compartido(self):
        for nombre in ('primera', 'segunda'):
            User.objects.create_user(nombre, email='comun@example.test', password='original-27')
        User.objects.create_user('inactiva', email='inactiva@example.test', password='original-28', is_active=False)
        url = reverse('usuarios:recuperar_password')
        esperado = 'Si el correo existe en nuestro sistema'
        for correo in ('comun@example.test', 'inactiva@example.test', 'sin-cuenta@example.test'):
            with self.subTest(correo=correo):
                respuesta = self.client.post(url, {'email': correo}, follow=True)
                self.assertContains(respuesta, esperado)
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotEqual(mail.outbox[0].body, mail.outbox[1].body)

    @override_settings(PASSWORD_RESET_TIMEOUT=60)
    def test_token_valido_expirado_invalido_y_de_un_solo_uso(self):
        usuario = User.objects.create_user('recuperar', password='original-28')
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        with patch.object(default_token_generator, '_now', return_value=datetime.now() - timedelta(minutes=2)):
            vencido = default_token_generator.make_token(usuario)

        def url(token):
            return reverse('usuarios:reset_password_confirm', args=[uid, token])

        for token in (vencido, 'invalido'):
            self.assertRedirects(self.client.get(url(token)), reverse('usuarios:recuperar_password'))
        valido = default_token_generator.make_token(usuario)
        respuesta = self.client.get(url(valido))
        self.assertNotIn(valido, respuesta.url)
        nueva = 'Bosque-26-Abedul'
        self.assertRedirects(self.client.post(respuesta.url, {
            'new_password1': nueva, 'new_password2': nueva,
        }), reverse('usuarios:login'))
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(nueva))
        self.assertRedirects(self.client.get(url(valido)), reverse('usuarios:recuperar_password'))


class AccionesPostTests(TestCase):
    def test_cerrar_sesion_y_completar_tutorial_exigen_post_y_csrf(self):
        usuario = User.objects.create_user('carpinteria')
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(usuario)
        for ruta in ('usuarios:logout', 'usuarios:completar_tutorial'):
            url = reverse(ruta)
            self.assertEqual(cliente.get(url).status_code, 405)
            self.assertEqual(cliente.post(url).status_code, 403)
        usuario.perfil.refresh_from_db()
        self.assertFalse(usuario.perfil.tutorial_completado)
        self.client.force_login(usuario)
        self.assertEqual(self.client.post(reverse('usuarios:completar_tutorial')).status_code, 200)
        usuario.perfil.refresh_from_db()
        self.assertTrue(usuario.perfil.tutorial_completado)
        self.assertRedirects(self.client.post(reverse('usuarios:logout')), reverse('usuarios:login'))
        self.assertNotIn('_auth_user_id', self.client.session)
