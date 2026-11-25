from django.contrib import admin

from .models import ImportBatch


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ["filename", "status", "imported_by", "created_at", "successful_rows", "failed_rows"]
    list_filter = ["status"]
