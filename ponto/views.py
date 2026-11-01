from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from accounts.models import User
from .forms import EmployeeForm, PunchForm
from .face_services import FaceRecognitionUnavailable, InvalidFaceImage, extract_face_encoding, face_matches
from .models import Employee, EmployeeFaceProfile, PunchDay, PunchEvent
from .services import journey_status, record_punch, worked_duration


def _employee_for(user):
    return get_object_or_404(Employee, user=user)


def _is_admin(user):
    return user.is_superuser or user.role == User.Role.ADMIN


def _visible_employees(user):
    employees = Employee.objects.select_related("department", "schedule", "user", "face_profile")
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
    if request.method != "GET":
        messages.error(
            request,
            "A câmera não iniciou. Atualize a página e tente novamente; confirme a permissão de câmera do navegador.",
        )
        return redirect("punch")

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
        "require_geolocation": settings.PUNCH_REQUIRE_GEOLOCATION,
        "has_face_profile": EmployeeFaceProfile.objects.filter(employee=employee).exists(),
    })


@login_required
def facial_punch(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Método não permitido."}, status=405)

    employee = _employee_for(request.user)
    if not employee.is_active:
        return JsonResponse({"detail": "Funcionário inativo não pode registrar ponto."}, status=403)

    profile = EmployeeFaceProfile.objects.filter(employee=employee).first()
    if profile is None:
        return JsonResponse(
            {"detail": "Biometria facial não cadastrada. Solicite ao administrador o cadastro da sua foto."},
            status=409,
        )

    photo = request.FILES.get("foto")
    if photo is None:
        return JsonResponse({"detail": "A imagem da câmera não foi recebida."}, status=400)
    if photo.size > 5 * 1024 * 1024:
        return JsonResponse({"detail": "A imagem deve ter no máximo 5 MB."}, status=400)

    form = PunchForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {"detail": " ".join(str(error) for error in form.errors.values())},
            status=400,
        )

    if settings.PUNCH_REQUIRE_GEOLOCATION and form.cleaned_data["latitude"] is None:
        return JsonResponse({"detail": "A localização é obrigatória para registrar o ponto."}, status=400)

    try:
        submitted_encoding = extract_face_encoding(photo.read())
        if not face_matches(profile.face_encoding, submitted_encoding):
            return JsonResponse({"detail": "Rosto não reconhecido para este usuário."}, status=403)
    except FaceRecognitionUnavailable:
        return JsonResponse(
            {"detail": "Reconhecimento facial indisponível. Instale as dependências do arquivo requirements.txt."},
            status=503,
        )
    except InvalidFaceImage as error:
        return JsonResponse({"detail": str(error)}, status=400)

    location = {
        "latitude": form.cleaned_data["latitude"],
        "longitude": form.cleaned_data["longitude"],
        "accuracy_meters": form.cleaned_data["accuracy_meters"],
        "status": form.cleaned_data["location_status"] or PunchEvent.LocationStatus.NOT_REQUESTED,
        "reason": form.cleaned_data["location_reason"],
    }
    try:
        with transaction.atomic():
            event = record_punch(employee.pk, form.cleaned_data["kind"], location)
    except ValidationError as error:
        return JsonResponse({"detail": " ".join(error.messages)}, status=400)

    messages.success(
        request,
        f"{event.get_kind_display()} registrada às {timezone.localtime(event.recorded_at):%H:%M}.",
    )
    return JsonResponse({
        "message": "Ponto registrado com sucesso.",
        "kind": event.kind,
        "recorded_at": timezone.localtime(event.recorded_at).isoformat(),
    })


@login_required
@ensure_csrf_cookie
def employee_list(request):
    employees = _visible_employees(request.user)
    search = request.GET.get("q", "").strip()
    if search:
        employees = employees.filter(
            Q(full_name__icontains=search) | Q(enrollment__icontains=search) | Q(email__icontains=search)
        )
    return render(request, "ponto/employee_list.html", {"employees": employees, "search": search})


@login_required
@ensure_csrf_cookie
def employee_create(request):
    if not _is_admin(request.user):
        raise PermissionDenied
    form = EmployeeForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        photo = form.cleaned_data["face_photo"]
        encoding = None
        if photo:
            try:
                encoding = extract_face_encoding(photo.read())
            except FaceRecognitionUnavailable:
                form.add_error(
                    "face_photo",
                    "Reconhecimento facial indisponível. Instale as dependências do arquivo requirements.txt.",
                )
            except InvalidFaceImage as error:
                form.add_error("face_photo", str(error))
        if form.errors:
            return render(request, "ponto/employee_form.html", {"form": form})
        with transaction.atomic():
            employee = form.save()
            if encoding is not None:
                EmployeeFaceProfile.objects.update_or_create(
                    employee=employee,
                    defaults={"face_encoding": encoding},
                )
        messages.success(request, "Funcionário cadastrado.")
        return redirect("employee_list")
    return render(request, "ponto/employee_form.html", {"form": form})


@login_required
def employee_face_enroll(request, employee_id):
    if not _is_admin(request.user):
        raise PermissionDenied
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    employee = get_object_or_404(Employee, pk=employee_id)
    photo = request.FILES.get("face_photo")
    if photo is None:
        messages.error(request, "Selecione uma foto para cadastrar a biometria.")
        return redirect("employee_list")
    if photo.size > 5 * 1024 * 1024:
        messages.error(request, "A foto deve ter no máximo 5 MB.")
        return redirect("employee_list")

    try:
        encoding = extract_face_encoding(photo.read())
    except FaceRecognitionUnavailable:
        messages.error(
            request,
            "Reconhecimento facial indisponível. Instale as dependências do arquivo requirements.txt.",
        )
        return redirect("employee_list")
    except InvalidFaceImage as error:
        messages.error(request, str(error))
        return redirect("employee_list")

    EmployeeFaceProfile.objects.update_or_create(
        employee=employee,
        defaults={"face_encoding": encoding},
    )
    messages.success(request, f"Biometria facial de {employee.full_name} cadastrada.")
    return redirect("employee_list")


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