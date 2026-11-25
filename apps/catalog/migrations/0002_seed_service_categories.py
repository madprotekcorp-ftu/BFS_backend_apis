"""Seed the 15 service categories (10 loans, 5 insurance).

Names, slugs and descriptions are a starting point: confirm them against the SRS
and adjust through the Django admin or a follow-up migration.
"""

from django.db import migrations

SERVICES = [
    ("Personal Loan", "personal-loan", "loan", "Quick funds for personal needs with minimal paperwork."),
    ("Business Loan", "business-loan", "loan", "Finance to start, run or grow your business."),
    ("Home Loan", "home-loan", "loan", "Buy, build or renovate your home with flexible repayment."),
    ("Loan Against Property", "loan-against-property", "loan", "Unlock the value of your property for larger needs."),
    ("Car Loan", "car-loan", "loan", "Finance for new and used cars."),
    ("Two-Wheeler Loan", "two-wheeler-loan", "loan", "Easy finance for bikes and scooters."),
    ("Gold Loan", "gold-loan", "loan", "Instant funds against your gold jewellery."),
    ("Education Loan", "education-loan", "loan", "Fund studies in India or abroad."),
    ("Balance Transfer & Top-up", "balance-transfer-top-up", "loan", "Move your loan to a lower rate and top it up."),
    ("Working Capital / MSME Loan", "working-capital-msme-loan", "loan", "Keep day-to-day operations of your MSME running."),
    ("Life Insurance", "life-insurance", "insurance", "Protect your family's financial future."),
    ("Term Insurance", "term-insurance", "insurance", "High cover at an affordable premium."),
    ("Health Insurance", "health-insurance", "insurance", "Cover for hospital and medical expenses."),
    ("Motor Insurance", "motor-insurance", "insurance", "Cover for your car or two-wheeler."),
    ("General Insurance", "general-insurance", "insurance", "Cover for home, shop and other assets."),
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
