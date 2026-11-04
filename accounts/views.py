import secrets

from django.contrib.auth import login, logout
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView

from .forms import AccessCodeForm
from .models import User


class LoginView(FormView):
    template_name = "registration/login.html"
    form_class = AccessCodeForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", self.request.POST.get("next", ""))
        return context

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.is_superuser:
                return redirect("home")
            logout(request)
            request.session["employee_kiosk_access"] = True
            return redirect("kiosk")
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        request = self.request
        code = form.cleaned_data["code"]
        developer_code = self.configured_code("DEVELOPER_ACCESS_CODE")
        employee_code = self.configured_code("EMPLOYEE_ACCESS_CODE")

        if developer_code and employee_code and secrets.compare_digest(developer_code, employee_code):
            raise ImproperlyConfigured("Developer and employee access codes must be different.")

        if developer_code and secrets.compare_digest(code, developer_code):
            username = self.configured_code("DEVELOPER_USERNAME") or "admin"
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "password": make_password(None),
                        "role": User.Role.ADMIN,
                        "is_staff": True,
                        "is_superuser": True,
                    },
                )
                if not created and not user.is_superuser:
                    if user.role != User.Role.ADMIN:
                        raise ImproperlyConfigured(
                            "DEVELOPER_USERNAME belongs to a non-administrator account."
                        )
                    user.is_staff = True
                    user.is_superuser = True
                    user.save(update_fields=["is_staff", "is_superuser"])
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            request.session.pop("employee_kiosk_access", None)
            return self.get_code_redirect(request, "home")

        if employee_code and secrets.compare_digest(code, employee_code):
            logout(request)
            request.session["employee_kiosk_access"] = True
            request.session.cycle_key()
            return redirect("kiosk")

        if not developer_code and not employee_code:
            form.add_error(None, "O acesso ainda não foi configurado. Defina os códigos no ambiente do site.")
        else:
            form.add_error("code", "Código inválido.")
        return self.form_invalid(form)

    @staticmethod
    def configured_code(setting_name):
        from django.conf import settings

        return getattr(settings, setting_name, "")

    @staticmethod
    def get_code_redirect(request, fallback_url_name):
        destination = request.POST.get("next", "")
        if destination and url_has_allowed_host_and_scheme(
            destination,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(destination)
        return redirect(fallback_url_name)
