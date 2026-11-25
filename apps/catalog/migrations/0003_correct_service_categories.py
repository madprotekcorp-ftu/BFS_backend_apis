"""Replace the draft service list with the agreed 15 categories.

Databases migrated before the list was agreed hold draft slugs (loan-against-property,
two-wheeler-loan, ...). Each draft row is renamed in place, by position, so ids stay
1-15 in display order and no lead is left pointing at a removed service (only dev/demo
data existed then). On a fresh database this is a no-op.
"""

from django.db import migrations

DRAFT_SLUGS = [
    "personal-loan", "business-loan", "home-loan", "loan-against-property", "car-loan",
    "two-wheeler-loan", "gold-loan", "education-loan", "balance-transfer-top-up", "working-capital-msme-loan",
    "life-insurance", "term-insurance", "health-insurance", "motor-insurance", "general-insurance",
]

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


def correct(apps, schema_editor):
    ServiceCategory = apps.get_model("catalog", "ServiceCategory")
    draft_only = set(DRAFT_SLUGS) - {s[1] for s in SERVICES}
    if ServiceCategory.objects.filter(slug__in=draft_only).exists():
        # Two passes so renamed slugs/names never collide on the unique constraints.
        rows = [ServiceCategory.objects.filter(slug=slug).first() for slug in DRAFT_SLUGS]
        for row in rows:
            if row is not None:
                row.slug, row.name = f"tmp-{row.pk}", f"tmp-{row.pk}"
                row.save()
        for row, (name, slug, group, description) in zip(rows, SERVICES):
            if row is not None:
                row.name, row.slug, row.group, row.short_description = name, slug, group, description
                row.save()

    for order, (name, slug, group, description) in enumerate(SERVICES, start=1):
        ServiceCategory.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "group": group, "short_description": description, "display_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_seed_service_categories")]

    operations = [migrations.RunPython(correct, migrations.RunPython.noop)]
