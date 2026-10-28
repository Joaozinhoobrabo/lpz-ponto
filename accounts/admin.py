from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Acesso LPZ", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Acesso LPZ", {"fields": ("role",)}),)
    list_display = UserAdmin.list_display + ("role",)