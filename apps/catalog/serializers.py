from rest_framework import serializers

from .models import ServiceCategory


class PublicServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ["id", "name", "slug", "group", "short_description", "display_order"]
