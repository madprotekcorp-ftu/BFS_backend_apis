from django.contrib import admin

from .models import Employee, LeadAssignment


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["employee_code", "name", "mobile", "email", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["employee_code", "name"]


@admin.register(LeadAssignment)
class LeadAssignmentAdmin(admin.ModelAdmin):
    list_display = ["lead", "previous_employee", "new_employee", "assigned_by", "assigned_at"]
    raw_id_fields = ["lead"]
