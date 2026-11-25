"""Fill a development database with clearly fake demo data. Never use real customer records."""

import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import ServiceCategory
from apps.employees.models import Employee
from apps.employees.services import assign_lead
from apps.leads.models import Lead, LeadRemark
from common.choices import LeadSource, LeadStatus

FIRST_NAMES = ["Ravi", "Priya", "Arun", "Divya", "Karthik", "Meena", "Suresh", "Lakshmi", "Vijay", "Anitha",
               "Ganesh", "Kavya", "Manoj", "Deepa", "Rahul", "Sneha", "Prakash", "Revathi", "Ajay", "Nisha"]
LAST_NAMES = ["Kumar", "S", "R", "Raj", "Murugan", "Devi", "Babu", "Nair", "Reddy", "Iyer"]
LOCATIONS = ["Hosur", "Krishnagiri", "Bengaluru", "Dharmapuri", "Salem", "Chennai", "Vellore", ""]
OCCUPATIONS = ["Salaried", "Business", "Self-employed", "Farmer", "Professional", ""]
AMOUNTS = ["2 lakh", "5 lakh", "5-10 lakh", "15 lakh", "25 lakh", "50 lakh", ""]
REMARKS = ["Called, asked for salary slips", "Customer will visit the office on Monday",
           "Sent document checklist on WhatsApp", "Not reachable, try again tomorrow",
           "Interested, comparing rates with another bank"]
EMPLOYEES = [("EMP001", "Priya Sharma"), ("EMP002", "Arjun Menon"), ("EMP003", "Kavitha Rao"),
             ("EMP004", "Sanjay Patel"), ("EMP005", "Farah Khan")]


class Command(BaseCommand):
    help = "Create fake employees, leads, remarks and assignments for local development."

    def add_arguments(self, parser):
        parser.add_argument("--leads", type=int, default=60)
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG is off.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError("seed_demo is for development only. Use --force if you really mean it.")

        rng = random.Random(42)
        services = list(ServiceCategory.objects.filter(is_active=True))
        if not services:
            raise CommandError("No service categories found. Run migrate first.")

        employees = [
            Employee.objects.get_or_create(
                employee_code=code,
                defaults={"name": name, "mobile": f"9{rng.randint(100000000, 999999999)}",
                          "email": f"{code.lower()}@example.com"},
            )[0]
            for code, name in EMPLOYEES
        ]
        admin = get_user_model().objects.filter(is_staff=True).order_by("id").first()
        today = timezone.localdate()
        sources = [s for s in LeadSource.values if s != LeadSource.EXISTING_DB]

        for _ in range(options["leads"]):
            status = rng.choice(LeadStatus.values)
            source = rng.choice(sources)
            lead = Lead.objects.create(
                customer_name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                mobile=f"{rng.choice('6789')}{rng.randint(100000000, 999999999)}",
                location=rng.choice(LOCATIONS),
                service=rng.choice(services),
                loan_amount=rng.choice(AMOUNTS),
                occupation=rng.choice(OCCUPATIONS),
                message="Demo enquiry (fake data)",
                consent=source == LeadSource.WEBSITE,
                consent_at=timezone.now() if source == LeadSource.WEBSITE else None,
                source=source,
                status=status,
                next_followup_date=today + timedelta(days=rng.randint(-5, 10)) if rng.random() < 0.6 else None,
                created_by=None if source == LeadSource.WEBSITE else admin,
            )
            # Spread created_at over the last 60 days for realistic dashboards.
            Lead.objects.filter(pk=lead.pk).update(
                created_at=timezone.now() - timedelta(days=rng.randint(0, 60), hours=rng.randint(0, 23))
            )
            if rng.random() < 0.75:
                assign_lead(lead=lead, employee=rng.choice(employees), user=admin, note="Demo assignment")
            for _ in range(rng.randint(0, 3)):
                LeadRemark.objects.create(lead=lead, text=rng.choice(REMARKS), created_by=admin)

        self.stdout.write(
            self.style.SUCCESS(f"Created {options['leads']} demo leads and {len(employees)} employees.")
        )
