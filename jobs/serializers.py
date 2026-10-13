from datetime import date
from django.utils import timezone
from rest_framework import serializers

from .models import Job


ALLOWED_RESOURCE_TYPES = {
    "TECHNICIAN",
    "MACHINE",
    "VEHICLE",
    "LABORATORY",
    "ROOM",
}


class JobCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Job
        fields = [
            "id",
            "job_type",
            "priority",
            "estimated_duration_minutes",
            "preferred_date",
            "preferred_time",
            "location",
            "required_resource_types",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def validate_job_type(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Job type is required."
            )

        return value

    def validate_estimated_duration_minutes(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Duration must be greater than zero."
            )

        if value > 7 * 24 * 60:
            raise serializers.ValidationError(
                "Duration cannot exceed 7 days."
            )

        return value

    def validate_preferred_date(self, value):
        if value < date.today():
            raise serializers.ValidationError(
                "Preferred date cannot be in the past."
            )

        return value

    def validate_location(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Location is required."
            )

        return value

    def validate_required_resource_types(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError(
                "At least one resource type is required."
            )

        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError(
                "Each resource type must be a string."
            )

        normalized = [item.strip().upper() for item in value]

        if len(normalized) != len(set(normalized)):
            raise serializers.ValidationError(
                "Duplicate resource types are not allowed."
            )

        invalid = set(normalized) - ALLOWED_RESOURCE_TYPES

        if invalid:
            raise serializers.ValidationError({
                "required_resource_types": (
                    f"Invalid resource types: "
                    f"{', '.join(sorted(invalid))}."
                )
            })

        return normalized
    

class JobStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=Job.Status.choices
    )

class JobRescheduleSerializer(serializers.Serializer):
    preferred_date = serializers.DateField()
    preferred_time = serializers.TimeField()

    def validate_preferred_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError(
                "Preferred date cannot be in the past."
            )
        return value

class StartJobSerializer(serializers.Serializer):
    def validate(self, attrs):
        job = self.context.get("job")

        if job is None:
            raise serializers.ValidationError(
                "Job information is required."
            )

        if job.status != Job.Status.ASSIGNED:
            raise serializers.ValidationError(
                "Only assigned jobs can be started."
            )

        return attrs


class CompleteJobSerializer(serializers.Serializer):
    def validate(self, attrs):
        job = self.context.get("job")

        if job is None:
            raise serializers.ValidationError(
                "Job information is required."
            )

        if job.status != Job.Status.IN_PROGRESS:
            raise serializers.ValidationError(
                "Only jobs in progress can be completed."
            )

        return attrs

class JobConflictSerializer(serializers.Serializer):
    resource_id = serializers.IntegerField()
    resource_name = serializers.CharField()
    reason = serializers.CharField()