from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import AccesoForm, RegistroForm


class AuthFeedbackTests(TestCase):
    def data(self, **changes):
        data = {'username':'persona_nueva', 'email':'persona@example.com',
                'password1':'Madera!Temporal9274', 'password2':'Madera!Temporal9274'}
        data.update(changes)
        return data

    def test_registro_invalido_conserva_datos_y_explicacion_accesible(self):
        response = self.client.post(reverse('usuarios:registro'), self.data(email='mal', password2='Otra'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Escribe un correo válido')
        self.assertContains(response, 'Las contraseñas no coinciden')
        self.assertContains(response, 'value="persona_nueva"')
        self.assertNotContains(response, 'value="Madera!Temporal9274"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'id="id_email_errors"')
        self.assertFalse(User.objects.filter(username='persona_nueva').exists())

    def test_validadores_de_contrasena_siguen_activos(self):
        form = RegistroForm(self.data(password1='123', password2='123'))
        self.assertFalse(form.is_valid())
        self.assertIn('password_too_short', [e.code for e in form.errors.as_data()['password2']])
        self.assertIn('Usa al menos 8 caracteres.', form.errors['password2'])
        self.assertIn('Esta contraseña es muy común.', str(form.errors))

    def test_usuario_repetido_recibe_mensaje_concreto(self):
        User.objects.create_user('persona_nueva')
        form = RegistroForm(self.data())
        self.assertFalse(form.is_valid())
        self.assertIn('Este nombre de usuario ya está en uso. Prueba con otro.', form.errors['username'])

    def test_ayuda_permanente_explica_espacios_y_caracteres(self):
        response = self.client.get(reverse('usuarios:registro'))
        self.assertContains(response, 'data-auth-help-permanent', count=1)
        self.assertContains(response, 'Sin espacios. Usa letras, números o los símbolos @ . + - _.')
        self.assertContains(response, 'aria-describedby="id_username_help id_username_errors"')

    def test_espacios_internos_conservan_usuario_y_correo_sin_devolver_contrasenas(self):
        for username in ('Ana Pérez', 'Ana\u00a0Pérez', 'Ana\tPérez'):
            with self.subTest(username=username):
                data = self.data(username=username)
                response = self.client.post(reverse('usuarios:registro'), data)
                self.assertContains(response, 'El nombre de usuario no puede contener espacios.', count=2)
                self.assertEqual(response.context['form']['username'].value(), username)
                self.assertContains(response, 'value="persona@example.com"')
                self.assertNotContains(response, data['password1'])
                self.assertFalse(User.objects.exists())

    def test_conserva_caracteres_validos_y_recorte_exterior_de_django(self):
        form = RegistroForm(self.data(username='  José_27@equipo.+-  '))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['username'], 'José_27@equipo.+-')

    def test_otros_caracteres_invalidos_mantienen_mensaje_de_caracteres(self):
        form = RegistroForm(self.data(username='persona!nueva'))
        self.assertFalse(form.is_valid())
        self.assertIn('Usa letras, números o estos símbolos: @ . + - _', form.errors['username'])
        self.assertNotIn('no puede contener espacios', str(form.errors['username']))

    def test_cuenta_creada_muestra_una_sola_confirmacion_en_panel_login(self):
        response = self.client.post(reverse('usuarios:registro'), self.data(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tu cuenta está lista. Ahora inicia sesión.', count=1)
        self.assertContains(response, 'auth-notice')
        self.assertFalse('_auth_user_id' in self.client.session)
        user = User.objects.get(username='persona_nueva')
        self.assertTrue(user.check_password(self.data()['password1']))

    def test_login_no_revela_si_el_usuario_existe(self):
        User.objects.create_user('existente', password='Madera!Temporal9274')
        errors = []
        for username in ['existente', 'desconocido']:
            form = AccesoForm(data={'username':username, 'password':'incorrecta'})
            self.assertFalse(form.is_valid())
            errors.append(list(form.non_field_errors()))
        self.assertEqual(errors[0], errors[1])
        self.assertIn('No pudimos iniciar sesión.', errors[0][0])

    @override_settings(AUTH_PASSWORD_VALIDATORS=[{
        'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS':{'min_length':12},
    }])
    def test_guia_utiliza_la_longitud_configurada_en_servidor(self):
        self.assertEqual(RegistroForm().password_min_length, 12)
        response = self.client.get(reverse('usuarios:registro'))
        self.assertContains(response, 'data-min-password="12"')
        self.assertContains(response, 'Al menos 12 caracteres.')
        self.assertNotContains(response, 'data-password-rule="numeric"')
