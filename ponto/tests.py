from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ponto.models import Department, Employee, PunchDay, PunchEvent, WorkSchedule
from ponto.services import journey_status, record_punch, worked_duration


User = get_user_model()


class PunchFlowTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Montagem")
        self.schedule = WorkSchedule.objects.create(name="Administrativa", expected_work_minutes=480)
        self.user = User.objects.create_user(username="ana", password="senha-segura-123", role=User.Role.EMPLOYEE)
        self.employee = Employee.objects.create(
            user=self.user, full_name="Ana Silva", enrollment="LPZ-001", email="ana@example.com",
            position="Montadora", department=self.department, hire_date=timezone.localdate(), schedule=self.schedule,
        )

    def punch(self, kind):
        return record_punch(self.employee.pk, kind, {"status": PunchEvent.LocationStatus.SKIPPED, "reason": "Não compartilhada"})

    def test_records_full_day_with_server_timestamps(self):
        entry = self.punch(PunchEvent.Kind.ENTRY)
        self.punch(PunchEvent.Kind.BREAK_START)
        self.punch(PunchEvent.Kind.BREAK_END)
        exit_event = self.punch(PunchEvent.Kind.EXIT)
        self.assertLessEqual(entry.recorded_at, exit_event.recorded_at)
        self.assertEqual(self.employee.punch_days.get().events.count(), 4)
        self.assertEqual(journey_status(list(self.employee.punch_days.get().events.all())), ("finished", "Finalizada"))

    def test_can_start_another_work_session_after_exit_on_same_day(self):
        self.punch(PunchEvent.Kind.ENTRY)
        self.punch(PunchEvent.Kind.EXIT)
        self.punch(PunchEvent.Kind.ENTRY)
        events = list(self.employee.punch_days.get().events.all())
        self.assertEqual([event.kind for event in events], [
            PunchEvent.Kind.ENTRY,
            PunchEvent.Kind.EXIT,
            PunchEvent.Kind.ENTRY,
        ])
        self.assertEqual(journey_status(events), ("working", "Em andamento"))

    def test_finished_day_offers_new_session_in_punch_page(self):
        self.punch(PunchEvent.Kind.ENTRY)
        self.punch(PunchEvent.Kind.EXIT)
        self.client.login(username="ana", password="senha-segura-123")
        response = self.client.get(reverse("punch"))
        self.assertContains(response, "Iniciar nova jornada")

    def test_rejects_duplicate_and_invalid_sequence(self):
        with self.assertRaises(ValidationError):
            self.punch(PunchEvent.Kind.EXIT)
        self.punch(PunchEvent.Kind.ENTRY)
        with self.assertRaises(ValidationError):
            self.punch(PunchEvent.Kind.ENTRY)
        self.punch(PunchEvent.Kind.BREAK_START)
        with self.assertRaises(ValidationError):
            self.punch(PunchEvent.Kind.EXIT)

    def test_calculates_worked_time_and_open_journey(self):
        day = PunchDay.objects.create(employee=self.employee, work_date=timezone.localdate())
        start = timezone.now() - timedelta(hours=5)
        PunchEvent.objects.create(day=day, kind=PunchEvent.Kind.ENTRY, recorded_at=start)
        PunchEvent.objects.create(day=day, kind=PunchEvent.Kind.BREAK_START, recorded_at=start + timedelta(hours=2))
        PunchEvent.objects.create(day=day, kind=PunchEvent.Kind.BREAK_END, recorded_at=start + timedelta(hours=3))
        events = list(day.events.all())
        self.assertEqual(worked_duration(events, now=start + timedelta(hours=5)), timedelta(hours=4))
        self.assertEqual(journey_status(events), ("working", "Em andamento"))

    def test_employee_can_only_view_own_history(self):
        other_user = User.objects.create_user(username="bruno", password="senha-segura-123")
        other_employee = Employee.objects.create(
            user=other_user, full_name="Bruno Souza", enrollment="LPZ-002", email="bruno@example.com",
            position="Técnico", department=self.department, hire_date=timezone.localdate(), schedule=self.schedule,
        )
        self.punch(PunchEvent.Kind.ENTRY)
        other_day = PunchDay.objects.create(employee=other_employee, work_date=timezone.localdate() - timedelta(days=1))
        PunchEvent.objects.create(
            day=other_day,
            kind=PunchEvent.Kind.EXIT,
            recorded_at=timezone.now(),
        )
        self.client.login(username="ana", password="senha-segura-123")
        response = self.client.get(reverse("history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrada")
        self.assertNotContains(response, "Saída")

    def test_inactive_employee_cannot_punch(self):
        self.employee.is_active = False
        self.employee.save()
        with self.assertRaises(ValidationError):
            self.punch(PunchEvent.Kind.ENTRY)

    def test_employee_can_render_punch_page_and_submit_entry(self):
        self.client.login(username="ana", password="senha-segura-123")
        response = self.client.get(reverse("punch"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registrar marcação")
        response = self.client.post(reverse("punch"), {
            "kind": PunchEvent.Kind.ENTRY,
            "location_status": PunchEvent.LocationStatus.SKIPPED,
            "location_reason": "Não compartilhada",
        })
        self.assertRedirects(response, reverse("punch"))
        self.assertEqual(self.employee.punch_days.get().events.count(), 1)

    def test_employee_cannot_open_employee_management(self):
        self.client.login(username="ana", password="senha-segura-123")
        self.assertEqual(self.client.get(reverse("employee_list")).status_code, 403)

    def test_admin_can_create_employee_with_unique_enrollment(self):
        admin = User.objects.create_superuser(username="admin", password="senha-segura-123", email="admin@example.com")
        new_user = User.objects.create_user(username="caio", password="senha-segura-123")
        self.client.force_login(admin)
        response = self.client.post(reverse("employee_create"), {
            "user": new_user.pk,
            "full_name": "Caio Souza",
            "enrollment": "LPZ-003",
            "email": "caio@example.com",
            "position": "Técnico",
            "department": self.department.pk,
            "hire_date": timezone.localdate().isoformat(),
            "schedule": self.schedule.pk,
            "is_active": "on",
        })
        self.assertRedirects(response, reverse("employee_list"))
        self.assertTrue(Employee.objects.filter(enrollment="LPZ-003", user=new_user).exists())

    def test_employee_form_rejects_duplicate_enrollment(self):
        admin = User.objects.create_superuser(username="admin", password="senha-segura-123", email="admin@example.com")
        new_user = User.objects.create_user(username="caio", password="senha-segura-123")
        self.client.force_login(admin)
        response = self.client.post(reverse("employee_create"), {
            "user": new_user.pk,
            "full_name": "Caio Souza",
            "enrollment": self.employee.enrollment,
            "email": "caio@example.com",
            "position": "Técnico",
            "department": self.department.pk,
            "hire_date": timezone.localdate().isoformat(),
            "schedule": self.schedule.pk,
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Funcionário com este Matrícula já existe.")

    @override_settings(PUNCH_REQUIRE_GEOLOCATION=True)
    def test_required_geolocation_accepts_zero_coordinates(self):
        event = record_punch(self.employee.pk, PunchEvent.Kind.ENTRY, {
            "latitude": 0,
            "longitude": 0,
            "accuracy_meters": 25,
            "status": PunchEvent.LocationStatus.CAPTURED,
        })
        self.assertEqual(event.latitude, 0)
        self.assertEqual(event.longitude, 0)

    @override_settings(PUNCH_REQUIRE_GEOLOCATION=True)
    def test_required_geolocation_rejects_missing_coordinates(self):
        with self.assertRaises(ValidationError):
            self.punch(PunchEvent.Kind.ENTRY)