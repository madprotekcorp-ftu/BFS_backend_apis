from rest_framework import serializers


class EnumField(serializers.ChoiceField):
    """Returns {"code": ..., "label": ...}; accepts the bare code."""

    def to_representation(self, value):
        if value in ("", None):
            return None
        return {"code": value, "label": self.choices.get(value, value)}


class OptionalCharField(serializers.CharField):
    """Optional text: missing, null and "" are all accepted; null is stored as ""."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_blank", True)
        kwargs.setdefault("allow_null", True)
        super().__init__(**kwargs)

    def validate_empty_values(self, data):
        if data is None:
            return True, ""
        return super().validate_empty_values(data)


def user_ref(user):
    if user is None:
        return None
    return {"id": user.pk, "name": user.get_full_name() or user.get_username()}


def employee_ref(employee):
    if employee is None:
        return None
    return {"id": employee.pk, "name": employee.name}
