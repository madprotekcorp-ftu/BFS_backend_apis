"""Enums. The database stores the code; the API returns {"code", "label"}."""

from django.db import models


class LeadStatus(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    INTERESTED = "interested", "Interested"
    FOLLOW_UP = "follow_up", "Follow-up"
    CONVERTED = "converted", "Converted"
    CLOSED = "closed", "Closed / Not Interested"


# Converted and closed leads are finished: they never count as "follow-up due".
CLOSED_STATUSES = (LeadStatus.CONVERTED.value, LeadStatus.CLOSED.value)
OPEN_STATUSES = tuple(s for s in LeadStatus.values if s not in CLOSED_STATUSES)


class LeadSource(models.TextChoices):
    WEBSITE = "website", "Website"
    PHONE = "phone", "Phone Call"
    WHATSAPP = "whatsapp", "WhatsApp"
    WALK_IN = "walk_in", "Walk-in"
    REFERRAL = "referral", "Referral"
    SOCIAL_MEDIA = "social_media", "Social Media"
    CAMPAIGN = "campaign", "Campaign"
    EXISTING_DB = "existing_db", "Existing Database / Import"
    OTHER = "other", "Other"


class ServiceGroup(models.TextChoices):
    LOAN = "loan", "Loan"
    INSURANCE = "insurance", "Insurance"


class DocumentCategory(models.TextChoices):
    KYC = "kyc", "Identity / KYC"
    INCOME = "income", "Income / Financial"
    LOAN = "loan", "Loan-related"
    OTHER = "other", "Other"


class ImportBatchStatus(models.TextChoices):
    PREVIEW = "preview", "Preview"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class ImportRowResult(models.TextChoices):
    VALID = "valid", "Valid"
    INVALID = "invalid", "Invalid"
    DUPLICATE = "duplicate", "Duplicate"
    IMPORTED = "imported", "Imported"
