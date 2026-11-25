"""Seed the 15 service categories (10 loans, 5 insurance).

Slugs are fixed by the frontend contract. On a fresh database the ids come out
1-15 in display order. Databases seeded with the earlier draft list are corrected
by 0003_correct_service_categories.
"""

from django.db import migrations

SERVICES = [
    ("Personal Loan", "personal-loan", "loan", "Quick funds for personal needs with minimal paperwork."),
    ("Business Loan", "business-loan", "loan", "Finance to start, run or grow your business."),
    ("Home Loan", "home-loan", "loan", "Buy, build or renovate your home with flexible repayment."),
    ("Plot Loan", "plot-loan", "loan", "Finance to buy a residential plot."),
    ("Car Loan", "car-loan", "loan", "Finance for new and used cars."),
    ("Commercial Vehicle Loan", "commercial-vehicle-loan", "loan", "Finance for trucks, buses and other commercial vehicles."),
    ("Education Loan", "education-loan", "loan", "Fund studies in India or abroad."),
    ("Gold Loan", "gold-loan", "loan", "Instant funds against your gold jewellery."),
    ("MSME Loan", "msme-loan", "loan", "Working capital and term loans for small businesses."),
    ("Top-up Loan", "top-up-loan", "loan", "Extra funds on top of your existing loan."),
    ("Life Insurance", "life-insurance", "insurance", "Protect your family's financial future."),
    ("Health Insurance", "health-insurance", "insurance", "Cover for hospital and medical expenses."),
    ("Vehicle Insurance", "vehicle-insurance", "insurance", "Cover for your car, two-wheeler or commercial vehicle."),
    ("Home Insurance", "home-insurance", "insurance", "Protect your home and belongings."),
    ("Personal Accident Insurance", "personal-accident-insurance", "insurance", "Financial cover against accidental injury or death."),
]


def seed(apps, schema_editor):
    ServiceCategory = apps.get_model("catalog", "ServiceCategory")
    for order, (name, slug, group, description) in enumerate(SERVICES, start=1):
        ServiceCategory.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "group": group, "short_description": description, "display_order": order},
        )


def unseed(apps, schema_editor):
    ServiceCategory = apps.get_model("catalog", "ServiceCategory")
    ServiceCategory.objects.filter(slug__in=[s[1] for s in SERVICES], leads__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
