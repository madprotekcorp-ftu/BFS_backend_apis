import re

from rest_framework import serializers

MOBILE_ERROR = "Enter a valid 10-digit Indian mobile number."
_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


def normalize_mobile(value) -> str:
    """Return the 10-digit mobile number or raise ValueError.

    Strips spaces and dashes and a leading +91, 91 or 0. The same function is used
    for website enquiries, manual leads and imports.
    """
    digits = re.sub(r"[\s\-]", "", str(value or ""))
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not _MOBILE_RE.match(digits):
        raise ValueError(MOBILE_ERROR)
    return digits


class MobileField(serializers.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 20)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_mobile(value)
        except ValueError:
            raise serializers.ValidationError(MOBILE_ERROR)
