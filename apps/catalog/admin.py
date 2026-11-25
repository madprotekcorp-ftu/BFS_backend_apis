from django.contrib import admin

from .models import ServiceCategory


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "group", "is_active", "display_order"]
    list_filter = ["group", "is_active"]
    prepopulated_fields = {"slug": ["name"]}
