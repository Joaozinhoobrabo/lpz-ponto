from django.contrib import admin

from .models import Department, Employee, PunchDay, PunchEvent, WorkSchedule


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "enrollment", "department", "position", "is_active")
    list_filter = ("department", "is_active", "schedule")
    search_fields = ("full_name", "enrollment", "email")


@admin.register(PunchEvent)
class PunchEventAdmin(admin.ModelAdmin):
    list_display = ("day", "kind", "recorded_at", "location_status")
    list_filter = ("kind", "location_status", "day__work_date")
    readonly_fields = tuple(field.name for field in PunchEvent._meta.fields)
    search_fields = ("day__employee__full_name", "day__employee__enrollment")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Department)
admin.site.register(WorkSchedule)
admin.site.register(PunchDay)