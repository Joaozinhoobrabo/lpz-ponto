from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("ponto/", views.punch, name="punch"),
    path("ponto/registrar-facial/", views.facial_punch, name="facial_punch"),
    path("funcionarios/", views.employee_list, name="employee_list"),
    path("funcionarios/novo/", views.employee_create, name="employee_create"),
    path("funcionarios/<int:employee_id>/biometria/", views.employee_face_enroll, name="employee_face_enroll"),
    path("historico/", views.history, name="history"),
]