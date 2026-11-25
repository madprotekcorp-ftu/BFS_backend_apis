from rest_framework import status as http_status
from rest_framework.response import Response


def success(data=None, message=None, status=http_status.HTTP_200_OK, **extra):
    body = {"success": True, "data": data}
    if message:
        body["message"] = message
    body.update(extra)
    return Response(body, status=status)


def no_content():
    return Response(status=http_status.HTTP_204_NO_CONTENT)
