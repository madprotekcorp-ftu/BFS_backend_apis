from rest_framework import serializers

from apps.catalog.models import ServiceCategory
from apps.employees.models import Employee
from common.choices import LeadSource, LeadStatus
from common.fields import EnumField, OptionalCharField, employee_ref, user_ref
from common.validators import MobileField

from .models import Lead, LeadRemark

WEBSITE_SOURCE_RESERVED = "Website is reserved for enquiries submitted through the website form."

# --- Output -------------------------------------------------------------------


class LeadListSerializer(serializers.ModelSerializer):
    """List-row shape, also used by the dashboard lists."""

    service = serializers.SerializerMethodField()
    source = EnumField(choices=LeadSource.choices, read_only=True)
    status = EnumField(choices=LeadStatus.choices, read_only=True)
    assigned_employee = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",
            "lead_code",
            "customer_name",
            "mobile",
            "service",
            "location",
            "source",
            "status",
            "assigned_employee",
            "created_at",
            "next_followup_date",
        ]

    def get_service(self, obj) -> dict:
        return {"id": obj.service_id, "name": obj.service.name}

    def get_assigned_employee(self, obj) -> dict | None:
        return employee_ref(obj.assigned_employee)


class LeadDetailSerializer(LeadListSerializer):
    """Expects the queryset from leads.views.lead_detail_queryset() (annotated counts)."""

    created_by = serializers.SerializerMethodField()
    import_batch_id = serializers.UUIDField(read_only=True, allow_null=True)
    document_count = serializers.IntegerField(read_only=True)
    remark_count = serializers.IntegerField(read_only=True)
    possible_duplicate = serializers.BooleanField(read_only=True)

    class Meta(LeadListSerializer.Meta):
        fields = LeadListSerializer.Meta.fields + [
            "loan_amount",
            "occupation",
            "message",
            "consent",
            "consent_at",
            "assigned_at",
            "last_followup_date",
            "created_by",
            "import_batch_id",
            "updated_at",
            "document_count",
            "remark_count",
            "possible_duplicate",
        ]

    def get_created_by(self, obj) -> dict | None:
        return user_ref(obj.created_by)


# --- Input --------------------------------------------------------------------


class LeadInputSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=150)
    mobile = MobileField()
    location = OptionalCharField(max_length=120)
    service_id = serializers.IntegerField()
    loan_amount = OptionalCharField(max_length=50)
    occupation = OptionalCharField(max_length=120)
    message = OptionalCharField(max_length=2000)

    require_active_service = False

    def validate_service_id(self, value):
        services = ServiceCategory.objects.filter(pk=value)
        if self.require_active_service:
            services = services.filter(is_active=True)
        if not services.exists():
            raise serializers.ValidationError("Select a valid service.")
        return value


class EnquirySerializer(LeadInputSerializer):
    """Public website form. Source/status sent by the client are ignored."""

    require_active_service = True
    consent = serializers.BooleanField()
    website = OptionalCharField(max_length=200, help_text="Honeypot. Must be empty.")

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError("Please agree to be contacted so we can respond to your enquiry.")
        return value


class AdminLeadCreateSerializer(LeadInputSerializer):
    consent = serializers.BooleanField(required=False, default=False)
    source = serializers.ChoiceField(choices=LeadSource.choices)
    status = serializers.ChoiceField(choices=LeadStatus.choices, required=False, default=LeadStatus.NEW)
    assigned_employee_id = serializers.IntegerField(required=False, allow_null=True)
    next_followup_date = serializers.DateField(required=False, allow_null=True)
    allow_duplicate = serializers.BooleanField(required=False, default=False)

    def validate_source(self, value):
        if value == LeadSource.WEBSITE:
            raise serializers.ValidationError(WEBSITE_SOURCE_RESERVED)
        return value

    def validate_assigned_employee_id(self, value):
        if value is not None and not Employee.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Employee not found.")
        return value


class LeadUpdateSerializer(LeadInputSerializer):
    """PATCH: every field optional. Assignment is changed only via /assign/."""

    source = serializers.ChoiceField(choices=LeadSource.choices, required=False)
    status = serializers.ChoiceField(choices=LeadStatus.choices, required=False)
    next_followup_date = serializers.DateField(required=False, allow_null=True)
    last_followup_date = serializers.DateField(required=False, allow_null=True)

    def validate_source(self, value):
        current = self.instance.source
        if value != current and LeadSource.WEBSITE in (value, current):
            raise serializers.ValidationError("Source cannot be changed to or from Website.")
        return value

    def validate(self, attrs):
        blocked = {"assigned_employee_id", "assigned_employee"} & set(self.initial_data)
        if blocked:
            raise serializers.ValidationError(
                {key: ["Use the assign endpoint to change the assigned employee."] for key in blocked}
            )
        return attrs


class RemarkSerializer(serializers.ModelSerializer):
    text = serializers.CharField(max_length=2000)
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = LeadRemark
        fields = ["id", "text", "created_by", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_created_by(self, obj) -> dict | None:
        return user_ref(obj.created_by)
