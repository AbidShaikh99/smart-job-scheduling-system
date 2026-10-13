from rest_framework import serializers
from auditlog.models import AuditLog


class JobHistorySerializer(serializers.ModelSerializer):
    performed_by_username = serializers.CharField(
        source="performed_by.username",
        read_only=True,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "action",
            "target_model",
            "target_id",
            "description",
            "changes",
            "performed_by",
            "performed_by_username",
            "created_at",
        ]
        read_only_fields = fields
