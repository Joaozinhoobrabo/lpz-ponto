from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Employee, PunchDay, PunchEvent


NEXT_EVENTS = {
    None: PunchEvent.Kind.ENTRY,
    PunchEvent.Kind.ENTRY: PunchEvent.Kind.BREAK_START,
    PunchEvent.Kind.BREAK_START: PunchEvent.Kind.BREAK_END,
    PunchEvent.Kind.BREAK_END: PunchEvent.Kind.BREAK_START,
    PunchEvent.Kind.EXIT: PunchEvent.Kind.ENTRY,
}


@transaction.atomic
def record_punch(employee_id, kind, location=None):
    employee = Employee.objects.select_for_update().get(pk=employee_id)
    if not employee.is_active:
        raise ValidationError("Funcionário inativo não pode registrar ponto.")

    today = timezone.localdate()
    day = PunchDay.objects.filter(employee=employee, work_date=today).first()
    events = list(day.events.all()) if day else []
    last_kind = events[-1].kind if events else None
    expected_kind = NEXT_EVENTS.get(last_kind)
    if kind == PunchEvent.Kind.EXIT:
        valid = last_kind in (PunchEvent.Kind.ENTRY, PunchEvent.Kind.BREAK_END)
    else:
        valid = kind == expected_kind
    if not valid:
        expected = expected_kind or "nenhuma marcação adicional"
        raise ValidationError(f"Sequência inválida. Próxima ação permitida: {expected}.")

    if settings.PUNCH_REQUIRE_GEOLOCATION and location.get("latitude") is None:
        raise ValidationError("A localização é obrigatória para registrar o ponto.")

    if day is None:
        day = PunchDay.objects.create(employee=employee, work_date=today)
    return PunchEvent.objects.create(
        day=day,
        kind=kind,
        recorded_at=timezone.now(),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        accuracy_meters=location.get("accuracy_meters"),
        location_status=location.get("status", PunchEvent.LocationStatus.NOT_REQUESTED),
        location_reason=location.get("reason", ""),
    )


def journey_status(events):
    if not events:
        return "not_started", "Não iniciada"
    last_kind = events[-1].kind
    if last_kind == PunchEvent.Kind.EXIT:
        return "finished", "Finalizada"
    if last_kind == PunchEvent.Kind.BREAK_START:
        return "break", "Em intervalo"
    return "working", "Em andamento"


def worked_duration(events, now=None):
    now = now or timezone.now()
    started_at = None
    total = timedelta()
    for event in events:
        if event.kind in (PunchEvent.Kind.ENTRY, PunchEvent.Kind.BREAK_END):
            started_at = event.recorded_at
        elif event.kind in (PunchEvent.Kind.BREAK_START, PunchEvent.Kind.EXIT) and started_at:
            total += event.recorded_at - started_at
            started_at = None
    if started_at and events and events[-1].kind != PunchEvent.Kind.EXIT:
        total += now - started_at
    return total