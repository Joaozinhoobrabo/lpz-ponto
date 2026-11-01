from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Department(models.Model):
    name = models.CharField("nome", max_length=120, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "equipe"
        verbose_name_plural = "equipes"

    def __str__(self):
        return self.name


class WorkSchedule(models.Model):
    name = models.CharField("nome", max_length=120, unique=True)
    expected_work_minutes = models.PositiveSmallIntegerField("minutos previstos por dia", default=480)
    starts_at = models.TimeField("início previsto", null=True, blank=True)
    ends_at = models.TimeField("término previsto", null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "jornada"
        verbose_name_plural = "jornadas"

    def __str__(self):
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="employee",
        verbose_name="usuário",
    )
    full_name = models.CharField("nome completo", max_length=160)
    enrollment = models.CharField("matrícula", max_length=40, unique=True)
    email = models.EmailField("e-mail")
    position = models.CharField("cargo", max_length=120)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="employees", verbose_name="equipe"
    )
    hire_date = models.DateField("data de admissão")
    schedule = models.ForeignKey(
        WorkSchedule, on_delete=models.PROTECT, related_name="employees", verbose_name="jornada"
    )
    is_active = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "funcionário"
        verbose_name_plural = "funcionários"

    def __str__(self):
        return self.full_name


class EmployeeFaceProfile(models.Model):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="face_profile",
        verbose_name="funcionário",
    )
    face_encoding = models.JSONField("vetor facial", default=list, help_text="Lista com 128 valores do encoding facial")
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "perfil facial"
        verbose_name_plural = "perfis faciais"

    def __str__(self):
        return f"Perfil facial - {self.employee}"


class PunchDay(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="punch_days")
    work_date = models.DateField("data")

    class Meta:
        ordering = ["-work_date", "employee__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "work_date"], name="unique_employee_punch_day")
        ]
        indexes = [models.Index(fields=["work_date", "employee"], name="punch_date_employee_idx")]
        verbose_name = "jornada registrada"
        verbose_name_plural = "jornadas registradas"

    def __str__(self):
        return f"{self.employee} - {self.work_date:%d/%m/%Y}"


class PunchEvent(models.Model):
    class Kind(models.TextChoices):
        ENTRY = "entry", "Entrada"
        BREAK_START = "break_start", "Início do intervalo"
        BREAK_END = "break_end", "Retorno do intervalo"
        EXIT = "exit", "Saída"

    class LocationStatus(models.TextChoices):
        CAPTURED = "captured", "Localização coletada"
        DENIED = "denied", "Permissão negada"
        UNAVAILABLE = "unavailable", "Indisponível"
        TIMEOUT = "timeout", "Tempo esgotado"
        UNSUPPORTED = "unsupported", "Não suportada"
        SKIPPED = "skipped", "Não compartilhada"
        NOT_REQUESTED = "not_requested", "Não solicitada"

    day = models.ForeignKey(PunchDay, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField("marcação", max_length=12, choices=Kind.choices)
    recorded_at = models.DateTimeField("registrado em")
    latitude = models.DecimalField("latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_meters = models.PositiveIntegerField("precisão em metros", null=True, blank=True)
    location_status = models.CharField(
        "estado da localização", max_length=16, choices=LocationStatus.choices, default=LocationStatus.NOT_REQUESTED
    )
    location_reason = models.CharField("motivo da ausência", max_length=160, blank=True)

    class Meta:
        ordering = ["recorded_at", "pk"]
        verbose_name = "marcação de ponto"
        verbose_name_plural = "marcações de ponto"
        indexes = [models.Index(fields=["day", "recorded_at"], name="punch_event_day_time_idx")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Marcações originais são imutáveis.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Marcações originais não podem ser apagadas.")

    def __str__(self):
        return f"{self.get_kind_display()} - {self.day}"