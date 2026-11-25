from django.contrib import admin

from .models import Lead, LeadRemark


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["lead_code", "customer_name", "service", "source", "status", "assigned_employee", "is_deleted"]
    list_filter = ["status", "source", "is_deleted"]
    search_fields = ["lead_code", "customer_name"]
    raw_id_fields = ["assigned_employee", "import_batch", "created_by"]


@admin.register(LeadRemark)
class LeadRemarkAdmin(admin.ModelAdmin):
    list_display = ["lead", "created_by", "created_at"]
    raw_id_fields = ["lead"]
