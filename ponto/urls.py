from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("ponto/", views.punch, name="punch"),
    path("funcionarios/", views.employee_list, name="employee_list"),
    path("funcionarios/novo/", views.employee_create, name="employee_create"),
    path("historico/", views.history, name="history"),
]