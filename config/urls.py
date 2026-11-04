from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.views import LoginView


urlpatterns = [
    path("admin/login/", LoginView.as_view(), name="admin-code-login"),
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("ponto.urls")),
]