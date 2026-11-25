from rest_framework import serializers

from common.choices import DocumentCategory
from common.fields import EnumField, user_ref

from .models import LeadDocument


class DocumentSerializer(serializers.ModelSerializer):
    category = EnumField(choices=DocumentCategory.choices, read_only=True)
    uploaded_by = serializers.SerializerMethodField()

    class Meta:
        model = LeadDocument
        fields = ["id", "original_filename", "category", "file_size", "mime_type", "uploaded_by", "uploaded_at"]

    def get_uploaded_by(self, obj) -> dict | None:
        return user_ref(obj.uploaded_by)


class BinnedDocumentSerializer(DocumentSerializer):
    lead = serializers.SerializerMethodField()
    deleted_by = serializers.SerializerMethodField()

    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ["lead", "deleted_at", "deleted_by"]

    def get_lead(self, obj) -> dict:
        return {"id": obj.lead_id, "lead_code": obj.lead.lead_code, "customer_name": obj.lead.customer_name}

    def get_deleted_by(self, obj) -> dict | None:
        return user_ref(obj.deleted_by)


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    category = serializers.ChoiceField(choices=DocumentCategory.choices)
