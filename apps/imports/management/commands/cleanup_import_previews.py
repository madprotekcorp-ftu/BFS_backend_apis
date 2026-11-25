from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.imports.models import ImportBatch
from common.choices import ImportBatchStatus


class Command(BaseCommand):
    help = "Cancel import previews older than 24 hours. Run hourly from cron."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=settings.IMPORT_PREVIEW_TTL_HOURS)
        count = ImportBatch.objects.filter(status=ImportBatchStatus.PREVIEW, created_at__lt=cutoff).update(
            status=ImportBatchStatus.CANCELLED, updated_at=timezone.now()
        )
        self.stdout.write(self.style.SUCCESS(f"Cancelled {count} stale import preview(s)."))
