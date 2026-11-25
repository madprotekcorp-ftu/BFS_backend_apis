from django.db import models


class TimeStampedModel(models.Model):
    """Adds timezone-aware created_at / updated_at (stored in UTC)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
