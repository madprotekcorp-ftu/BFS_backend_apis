from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def pagination_meta(self):
        return {
            "page": self.page.number,
            "page_size": self.page.paginator.per_page,
            "total": self.page.paginator.count,
            "total_pages": self.page.paginator.num_pages,
        }

    def get_paginated_response(self, data):
        return Response({"success": True, "data": data, "pagination": self.pagination_meta()})

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "data": schema,
                "pagination": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "example": 1},
                        "page_size": {"type": "integer", "example": 20},
                        "total": {"type": "integer", "example": 143},
                        "total_pages": {"type": "integer", "example": 8},
                    },
                },
            },
        }
