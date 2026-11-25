"""Neutral short descriptions: no promises about approval, speed or terms (lenders decide those).

Only texts still equal to the earlier defaults are changed, so wording BFS edits in the
Django admin is never overwritten.
"""

from django.db import migrations

# slug: (old default, new neutral text)
DESCRIPTIONS = {
    "personal-loan": ("Quick funds for personal needs with minimal paperwork.",
                      "Funds for planned or unexpected personal expenses."),
    "business-loan": ("Finance to start, run or grow your business.",
                      "Finance options to start, run or grow a business."),
    "home-loan": ("Buy, build or renovate your home with flexible repayment.",
                  "Finance to buy, build or renovate a home."),
    "plot-loan": ("Finance to buy a residential plot.",
                  "Finance to buy a residential plot."),
    "car-loan": ("Finance for new and used cars.",
                 "Finance options for new and used cars."),
    "commercial-vehicle-loan": ("Finance for trucks, buses and other commercial vehicles.",
                                "Finance for trucks, buses and other commercial vehicles."),
    "education-loan": ("Fund studies in India or abroad.",
                       "Finance for studies in India or abroad."),
    "gold-loan": ("Instant funds against your gold jewellery.",
                  "Loans against gold jewellery."),
    "msme-loan": ("Working capital and term loans for small businesses.",
                  "Working capital and term loan options for small businesses."),
    "top-up-loan": ("Extra funds on top of your existing loan.",
                    "Additional funds on top of an existing loan."),
    "life-insurance": ("Protect your family's financial future.",
                       "Life cover for your family."),
    "health-insurance": ("Cover for hospital and medical expenses.",
                         "Cover for hospital and medical expenses, as per policy terms."),
    "vehicle-insurance": ("Cover for your car, two-wheeler or commercial vehicle.",
                          "Cover for cars, two-wheelers and commercial vehicles."),
    "home-insurance": ("Protect your home and belongings.",
                       "Cover for your home and belongings."),
    "personal-accident-insurance": ("Financial cover against accidental injury or death.",
                                    "Cover against accidental injury or death, as per policy terms."),
}


def forwards(apps, schema_editor):
    ServiceCategory = apps.get_model("catalog", "ServiceCategory")
    for slug, (old, new) in DESCRIPTIONS.items():
        ServiceCategory.objects.filter(slug=slug, short_description=old).update(short_description=new)


def backwards(apps, schema_editor):
    ServiceCategory = apps.get_model("catalog", "ServiceCategory")
    for slug, (old, new) in DESCRIPTIONS.items():
        ServiceCategory.objects.filter(slug=slug, short_description=new).update(short_description=old)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_correct_service_categories")]

    operations = [migrations.RunPython(forwards, backwards)]
