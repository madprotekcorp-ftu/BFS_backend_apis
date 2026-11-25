import uuid

import pytest
from rest_framework.test import APIClient

from .conftest import ADMIN_PASSWORD

pytestmark = pytest.mark.django_db

SOME_UUID = uuid.uuid4()
ADMIN_ENDPOINTS = [
    ("post", "/api/auth/logout/"),
    ("get", "/api/auth/me/"),
    ("get", "/api/admin/dashboard/"),
    ("get", "/api/admin/leads/"),
    ("post", "/api/admin/leads/"),
    ("get", "/api/admin/leads/1/"),
    ("patch", "/api/admin/leads/1/"),
    ("delete", "/api/admin/leads/1/"),
    ("get", "/api/admin/leads/export/"),
    ("get", "/api/admin/leads/1/remarks/"),
    ("post", "/api/admin/leads/1/remarks/"),
    ("post", "/api/admin/leads/1/assign/"),
    ("get", "/api/admin/leads/1/assignments/"),
    ("get", "/api/admin/employees/"),
    ("post", "/api/admin/employees/"),
    ("get", "/api/admin/employees/1/"),
    ("patch", "/api/admin/employees/1/"),
    ("get", "/api/admin/leads/import/template/"),
    ("post", "/api/admin/leads/import/"),
    ("get", f"/api/admin/leads/import/{SOME_UUID}/"),
    ("post", f"/api/admin/leads/import/{SOME_UUID}/confirm/"),
    ("post", f"/api/admin/leads/import/{SOME_UUID}/cancel/"),
    ("get", f"/api/admin/leads/import/{SOME_UUID}/report/"),
    ("get", "/api/admin/leads/1/documents/"),
    ("post", "/api/admin/leads/1/documents/"),
    ("get", f"/api/admin/documents/{SOME_UUID}/download/"),
    ("delete", f"/api/admin/documents/{SOME_UUID}/"),
    ("get", "/api/admin/documents/bin/"),
    ("post", f"/api/admin/documents/{SOME_UUID}/restore/"),
    ("delete", f"/api/admin/documents/{SOME_UUID}/purge/"),
]


@pytest.mark.parametrize("method,url", ADMIN_ENDPOINTS)
def test_admin_endpoints_require_a_session(api_client, method, url):
    response = getattr(api_client, method)(url)
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "not_authenticated"


def test_non_staff_user_is_forbidden(django_user_model):
    user = django_user_model.objects.create_user(username="clerk", password="x-pass-123")
    client = APIClient()
    client.force_login(user)
    response = client.get("/api/admin/leads/")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_csrf_endpoint_sets_cookie_and_returns_token(api_client):
    response = api_client.get("/api/auth/csrf/")
    assert response.status_code == 200
    assert response.json()["data"]["csrf_token"]
    assert "csrftoken" in response.cookies


def test_login_with_username_then_me_then_logout(api_client, admin_user):
    response = api_client.post("/api/auth/login/", {"username": "admin", "password": ADMIN_PASSWORD}, format="json")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["username"] == "admin"
    assert data["full_name"] == "BFS Admin"
    assert "password" not in data

    me = api_client.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.json()["data"] == {"id": admin_user.pk, "username": "admin", "email": "admin@bfs.test", "full_name": "BFS Admin"}

    assert api_client.post("/api/auth/logout/").status_code == 200
    assert api_client.get("/api/auth/me/").status_code == 401


def test_login_with_email(api_client, admin_user):
    response = api_client.post(
        "/api/auth/login/", {"username": "ADMIN@bfs.test", "password": ADMIN_PASSWORD}, format="json"
    )
    assert response.status_code == 200


def test_wrong_password_gives_generic_400(api_client, admin_user):
    response = api_client.post("/api/auth/login/", {"username": "admin", "password": "nope"}, format="json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"] == "Invalid username or password."


def test_non_staff_cannot_log_in(api_client, django_user_model):
    django_user_model.objects.create_user(username="clerk", password="x-pass-123")
    response = api_client.post("/api/auth/login/", {"username": "clerk", "password": "x-pass-123"}, format="json")
    assert response.status_code == 400


def test_login_is_throttled_after_five_failures(api_client, admin_user):
    for _ in range(5):
        response = api_client.post("/api/auth/login/", {"username": "admin", "password": "bad"}, format="json")
        assert response.status_code == 400
    response = api_client.post("/api/auth/login/", {"username": "admin", "password": ADMIN_PASSWORD}, format="json")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "throttled"


def test_login_requires_csrf_token(admin_user):
    client = APIClient(enforce_csrf_checks=True)
    response = client.post("/api/auth/login/", {"username": "admin", "password": ADMIN_PASSWORD}, format="json")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"

    token = client.get("/api/auth/csrf/").json()["data"]["csrf_token"]
    response = client.post(
        "/api/auth/login/",
        {"username": "admin", "password": ADMIN_PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200


def test_admin_post_without_csrf_is_rejected(admin_user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(admin_user)
    response = client.post("/api/admin/employees/", {"employee_code": "E1", "name": "X"}, format="json")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_public_services_lists_active_only_in_order(api_client):
    from apps.catalog.models import ServiceCategory

    ServiceCategory.objects.filter(slug="gold-loan").update(is_active=False)
    response = api_client.get("/api/services/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 14
    assert [s["display_order"] for s in data] == sorted(s["display_order"] for s in data)
    assert "gold-loan" not in [s["slug"] for s in data]
    assert set(data[0]) == {"id", "name", "slug", "group", "short_description", "display_order"}

    loans = api_client.get("/api/services/?group=loan").json()["data"]
    assert {s["group"] for s in loans} == {"loan"}
    assert api_client.get("/api/services/?group=car").status_code == 400


def test_schema_is_generated(api_client):
    assert api_client.get("/api/schema/").status_code == 200
