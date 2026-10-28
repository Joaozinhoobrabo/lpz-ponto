from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["role"] = self.model.Role.ADMIN
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        HR = "hr", "RH ou gestor"
        EMPLOYEE = "employee", "Funcionário"

    role = models.CharField(max_length=12, choices=Role.choices, default=Role.EMPLOYEE)
    objects = UserManager()

    def __str__(self):
        return self.get_full_name() or self.username