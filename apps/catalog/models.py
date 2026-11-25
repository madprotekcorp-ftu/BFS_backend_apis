from django.db import models

from common.choices import ServiceGroup
from common.models import TimeStampedModel


class ServiceCategory(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, help_text="Used in URLs and import files.")
    group = models.CharField(max_length=20, choices=ServiceGroup.choices)
    short_description = models.CharField(max_length=300, blank=True, default="")
    is_active = models.BooleanField(default=True, help_text="Inactive services are hidden from the public API.")
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name_plural = "service categories"

    def __str__(self):
        return self.name
