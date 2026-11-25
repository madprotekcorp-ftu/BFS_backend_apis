import logging

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.authentication import enforce_csrf
from common.responses import success

from .serializers import CurrentUserSerializer, LoginSerializer
from .throttles import check_login_allowed, record_login_failure

logger = logging.getLogger(__name__)

INVALID_LOGIN = "Invalid username or password."

CsrfResponse = inline_serializer("CsrfResponse", {"csrf_token": serializers.CharField()})


class CsrfView(APIView):
    """Sets the CSRF cookie and returns the token to send as X-CSRFToken."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=CsrfResponse)
    def get(self, request):
        return success({"csrf_token": get_token(request._request)})


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=LoginSerializer, responses=CurrentUserSerializer)
    def post(self, request):
        enforce_csrf(request)
        check_login_allowed(request)

        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"]

        username = identifier
        if "@" in identifier:
            match = get_user_model().objects.filter(email__iexact=identifier, is_active=True).order_by("id").first()
            if match is not None:
                username = match.get_username()

        user = authenticate(request._request, username=username, password=password)
        if user is None or not user.is_staff:
            record_login_failure(request)
            logger.warning("Failed admin login attempt")
            raise ValidationError({"non_field_errors": [INVALID_LOGIN]})

        login(request._request, user)
        data = CurrentUserSerializer(user).data
        # Django rotates the CSRF token on login; hand the new one to the frontend.
        data["csrf_token"] = get_token(request._request)
        return success(data, "Logged in")


class LogoutView(APIView):
    @extend_schema(request=None, responses=None)
    def post(self, request):
        logout(request._request)  # flushes the session server-side
        return success(None, "Logged out")


class MeView(APIView):
    @extend_schema(responses=CurrentUserSerializer)
    def get(self, request):
        return success(CurrentUserSerializer(request.user).data)
