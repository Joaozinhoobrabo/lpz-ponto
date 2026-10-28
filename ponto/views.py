from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from .forms import EmployeeForm, PunchForm
from .models import Employee, PunchDay, PunchEvent
from .services import journey_status, record_punch, worked_duration


def _employee_for(user):
    return get_object_or_404(Employee, user=user)


def _is_admin(user):
    return user.is_superuser or user.role == User.Role.ADMIN


def _visible_employees(user):
    employees = Employee.objects.select_related("department", "schedule", "user")
    if _is_admin(user):
        return employees
    if user.role == User.Role.HR:
        profile = _employee_for(user)
        return employees.filter(department=profile.department)
    raise PermissionDenied


@login_required
def home(request):
    if request.user.role == User.Role.EMPLOYEE and not _is_admin(request.user):
        return redirect("punch")
    employees = _visible_employees(request.user)
    today = timezone.localdate()
    days = PunchDay.objects.filter(employee__in=employees, work_date=today)
    latest_event_kind = PunchEvent.objects.filter(day_id=OuterRef("pk")).order_by(
        "-recorded_at", "-pk"
    ).values("kind")[:1]
    incomplete_days = days.annotate(last_kind=Subquery(latest_event_kind)).exclude(
        last_kind=PunchEvent.Kind.EXIT
    ).count()
    context = {
        "active_count": employees.filter(is_active=True).count(),
        "registered_today": days.count(),
        "incomplete_today": incomplete_days,
        "today": today,
    }
    return render(request, "ponto/dashboard.html", context)


@login_required
def punch(request):
    employee = _employee_for(request.user)
    day = PunchDay.objects.filter(employee=employee, work_date=timezone.localdate()).first()
    events = list(day.events.all()) if day else []
    status_key, status_label = journey_status(events)
    labels = dict(PunchEvent.Kind.choices)
    allowed = {
        "not_started": [(PunchEvent.Kind.ENTRY, labels[PunchEvent.Kind.ENTRY])],
        "working": [
            (PunchEvent.Kind.BREAK_START, labels[PunchEvent.Kind.BREAK_START]),
            (PunchEvent.Kind.EXIT, labels[PunchEvent.Kind.EXIT]),
        ],
        "break": [(PunchEvent.Kind.BREAK_END, labels[PunchEvent.Kind.BREAK_END])],
        "finished": [(PunchEvent.Kind.ENTRY, "Iniciar nova jornada")],
    }[status_key]
    error_message = None
    if request.method == "POST":
        form = PunchForm(request.POST)
        if form.is_valid():
            if not employee.is_active:
                error_message = "Funcionário inativo não pode registrar novas marcações."
            else:
                location = {
                    "latitude": form.cleaned_data["latitude"],
                    "longitude": form.cleaned_data["longitude"],
                    "accuracy_meters": form.cleaned_data["accuracy_meters"],
                    "status": form.cleaned_data["location_status"] or PunchEvent.LocationStatus.NOT_REQUESTED,
                    "reason": form.cleaned_data["location_reason"],
                }
                try:
                    event = record_punch(employee.pk, form.cleaned_data["kind"], location)
                    messages.success(request, f"{event.get_kind_display()} registrada às {timezone.localtime(event.recorded_at):%H:%M}.")
                    return redirect("punch")
                except ValidationError as error:
                    error_message = " ".join(error.messages)
        else:
            error_message = " ".join(
                message for field_errors in form.errors.values() for message in field_errors
            )
    duration = worked_duration(events)
    return render(request, "ponto/punch.html", {
        "employee": employee,
        "events": events,
        "status_key": status_key,
        "status_label": status_label,
        "allowed": allowed if employee.is_active else [],
        "duration": duration,
        "duration_display": f"{int(duration.total_seconds() // 3600):02d}:{int(duration.total_seconds() % 3600 // 60):02d}",
        "now": timezone.localtime(),
        "require_geolocation": __import__("django.conf", fromlist=["settings"]).settings.PUNCH_REQUIRE_GEOLOCATION,
        "error_message": error_message,
    })


@login_required
def employee_list(request):
    employees = _visible_employees(request.user)
    search = request.GET.get("q", "").strip()
    if search:
        employees = employees.filter(
            Q(full_name__icontains=search) | Q(enrollment__icontains=search) | Q(email__icontains=search)
        )
    return render(request, "ponto/employee_list.html", {"employees": employees, "search": search})


@login_required
def employee_create(request):
    if not _is_admin(request.user):
        raise PermissionDenied
    form = EmployeeForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Funcionário cadastrado.")
        return redirect("employee_list")
    return render(request, "ponto/employee_form.html", {"form": form})


@login_required
def history(request):
    if request.user.role == User.Role.EMPLOYEE:
        employees = Employee.objects.filter(user=request.user)
    else:
        employees = _visible_employees(request.user)
    days = PunchDay.objects.filter(employee__in=employees).select_related("employee", "employee__department").prefetch_related("events")
    start = request.GET.get("from", "")
    end = request.GET.get("to", "")
    search = request.GET.get("q", "").strip()
    if start:
        try:
            days = days.filter(work_date__gte=datetime.strptime(start, "%Y-%m-%d").date())
        except ValueError:
            start = ""
    if end:
        try:
            days = days.filter(work_date__lte=datetime.strptime(end, "%Y-%m-%d").date())
        except ValueError:
            end = ""
    if search and request.user.role != User.Role.EMPLOYEE:
        days = days.filter(Q(employee__full_name__icontains=search) | Q(employee__enrollment__icontains=search))
    rows = []
    for day in days:
        events = list(day.events.all())
        _, status = journey_status(events)
        duration = worked_duration(events, now=timezone.now())
        rows.append({"day": day, "events": events, "status": status, "duration": f"{int(duration.total_seconds() // 3600):02d}:{int(duration.total_seconds() % 3600 // 60):02d}"})
    return render(request, "ponto/history.html", {"rows": rows, "start": start, "end": end, "search": search})