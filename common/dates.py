from datetime import date, datetime, time, timedelta

from django.utils import timezone
from rest_framework import serializers


def parse_date_param(value, field):
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        raise serializers.ValidationError({field: ["Enter a date in YYYY-MM-DD format."]})


def start_of_day(day):
    """Midnight at the start of `day` in the server time zone (IST)."""
    return timezone.make_aware(datetime.combine(day, time.min))


def start_of_next_day(day):
    return start_of_day(day + timedelta(days=1))
