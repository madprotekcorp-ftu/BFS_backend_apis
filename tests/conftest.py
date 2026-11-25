import itertools

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import ServiceCategory
from apps.employees.models import Employee
from apps.leads.models import Lead

ADMIN_PASSWORD = "S3cure-pass!"


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_user(
        username="admin",
        email="admin@bfs.test",
        password=ADMIN_PASSWORD,
        is_staff=True,
        first_name="BFS",
        last_name="Admin",
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_login(admin_user)
    return client


@pytest.fixture
def service(db):
    return ServiceCategory.objects.get(slug="home-loan")


@pytest.fixture
def make_lead(db, service):
    numbers = itertools.count(9000000001)

    def _make(**overrides):
        values = {
            "customer_name": "Test Customer",
            "mobile": str(next(numbers)),
            "service": service,
            "source": "phone",
        }
        values.update(overrides)
        return Lead.objects.create(**values)

    return _make


@pytest.fixture
def make_employee(db):
    numbers = itertools.count(1)

    def _make(**overrides):
        n = next(numbers)
        values = {"employee_code": f"EMP{n:03d}", "name": f"Employee {n}"}
        values.update(overrides)
        return Employee.objects.create(**values)

    return _make
