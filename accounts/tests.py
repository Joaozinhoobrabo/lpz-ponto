from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


class AccessCodeLoginTests(TestCase):
    @override_settings(DEVELOPER_ACCESS_CODE="dev-code-strong", EMPLOYEE_ACCESS_CODE="worker-code-strong")
    def test_developer_code_opens_admin_and_creates_admin_user(self):
        response = self.client.post(reverse("login"), {"code": "dev-code-strong"})

        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(username="admin")
        self.assertTrue(user.is_superuser)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(self.client.get(reverse("admin:index")).wsgi_request.user.is_superuser)

    @override_settings(DEVELOPER_ACCESS_CODE="dev-code-strong", EMPLOYEE_ACCESS_CODE="worker-code-strong")
    def test_employee_code_opens_face_kiosk(self):
        response = self.client.post(reverse("login"), {"code": "worker-code-strong"})

        self.assertRedirects(response, reverse("kiosk"))
        self.assertEqual(self.client.get(reverse("kiosk")).status_code, 200)

    @override_settings(DEVELOPER_ACCESS_CODE="dev-code-strong", EMPLOYEE_ACCESS_CODE="worker-code-strong")
    def test_employee_code_clears_an_existing_admin_session(self):
        admin = User.objects.create_superuser(username="admin", password="safe-test-password")
        self.client.force_login(admin)

        response = self.client.post(reverse("login"), {"code": "worker-code-strong"})

        self.assertRedirects(response, reverse("kiosk"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(self.client.session.get("employee_kiosk_access"))

    @override_settings(DEVELOPER_ACCESS_CODE="dev-code-strong", EMPLOYEE_ACCESS_CODE="worker-code-strong")
    def test_invalid_code_does_not_authenticate(self):
        response = self.client.post(reverse("login"), {"code": "wrong-code"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Código inválido.")
        self.assertFalse(User.objects.exists())

    @override_settings(DEVELOPER_ACCESS_CODE="", EMPLOYEE_ACCESS_CODE="")
    def test_missing_codes_show_configuration_error(self):
        response = self.client.post(reverse("login"), {"code": "any-code"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "O acesso ainda não foi configurado.")

    @override_settings(DEVELOPER_ACCESS_CODE="same-code", EMPLOYEE_ACCESS_CODE="same-code")
    def test_codes_must_be_different(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "must be different"):
            self.client.post(reverse("login"), {"code": "same-code"})

    def test_first_admin_route_no_longer_exists(self):
        response = self.client.get("/configurar-administrador/")
        self.assertEqual(response.status_code, 404)
