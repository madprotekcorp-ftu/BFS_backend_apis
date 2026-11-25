from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from common.choices import ServiceGroup

from .models import ServiceCategory
from .serializers import PublicServiceSerializer


@extend_schema(parameters=[OpenApiParameter("group", enum=ServiceGroup.values, required=False)])
class PublicServiceListView(generics.ListAPIView):
    """Active service categories, sorted by display_order. Not paginated."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicServiceSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = ServiceCategory.objects.filter(is_active=True)
        group = self.request.query_params.get("group")
        if group:
            if group not in ServiceGroup.values:
                raise ValidationError({"group": [f"Must be one of: {', '.join(ServiceGroup.values)}."]})
            queryset = queryset.filter(group=group)
        return queryset
