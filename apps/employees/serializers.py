from rest_framework import serializers

from common.fields import OptionalCharField, employee_ref, user_ref
from common.validators import MobileField

from .models import Employee, LeadAssignment


class EmployeeSerializer(serializers.ModelSerializer):
    """Expects the annotated queryset from employees.views.employee_queryset()."""

    employee_code = serializers.CharField(max_length=20)
    mobile = MobileField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    lead_counts = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_code",
            "name",
            "mobile",
            "email",
            "is_active",
            "lead_counts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_lead_counts(self, obj) -> dict:
        return {
            "total": getattr(obj, "lead_total", 0),
            "open": getattr(obj, "lead_open", 0),
            "converted": getattr(obj, "lead_converted", 0),
        }

    def validate_employee_code(self, value):
        value = value.strip()
        clash = Employee.objects.filter(employee_code__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("An employee with this Employee ID already exists.")
        return value


class AssignSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField(allow_null=True, help_text="null unassigns the lead.")
    note = OptionalCharField(max_length=300)


class LeadAssignmentSerializer(serializers.ModelSerializer):
    previous_employee = serializers.SerializerMethodField()
    new_employee = serializers.SerializerMethodField()
    assigned_by = serializers.SerializerMethodField()

    class Meta:
        model = LeadAssignment
        fields = ["id", "previous_employee", "new_employee", "assigned_by", "assigned_at", "note"]

    def get_previous_employee(self, obj) -> dict | None:
        return employee_ref(obj.previous_employee)

    def get_new_employee(self, obj) -> dict | None:
        return employee_ref(obj.new_employee)

    def get_assigned_by(self, obj) -> dict | None:
        return user_ref(obj.assigned_by)
