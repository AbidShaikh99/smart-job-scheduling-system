from rest_framework import serializers

from .models import Resource, ResourceWorkingHour, ResourceBreak, ResourceHoliday,ResourceBooking

class ResourceSerializer(serializers.ModelSerializer):

    class Meta:
        model = Resource
        fields = [
            "id",
            "name",
            "resource_type",
            "status",
            "location",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Resource name is required."
            )

        return value

    def validate_location(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Resource location is required."
            )

        return value

class ResourceWorkingHourSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceWorkingHour
        fields = [
            "id",
            "resource",
            "weekday",
            "start_time",
            "end_time",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        resource = attrs.get(
            "resource",
            self.instance.resource if self.instance else None,
        )
        weekday = attrs.get(
            "weekday",
            self.instance.weekday if self.instance else None,
        )
        start_time = attrs.get(
            "start_time",
            self.instance.start_time if self.instance else None,
        )
        end_time = attrs.get(
            "end_time",
            self.instance.end_time if self.instance else None,
        )

        if start_time is not None and end_time is not None:
            if start_time >= end_time:
                raise serializers.ValidationError({
                    "end_time": "End time must be after start time."
                })

        duplicate = ResourceWorkingHour.objects.filter(
            resource=resource,
            weekday=weekday,
        )

        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)

        if duplicate.exists():
            raise serializers.ValidationError({
                "weekday": "Working hours already exist for this resource and weekday."
            })

        return attrs


class ResourceBreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceBreak
        fields = [
            "id",
            "working_hour",
            "name",
            "start_time",
            "end_time",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        working_hour = attrs.get(
            "working_hour",
            self.instance.working_hour if self.instance else None,
        )
        start_time = attrs.get(
            "start_time",
            self.instance.start_time if self.instance else None,
        )
        end_time = attrs.get(
            "end_time",
            self.instance.end_time if self.instance else None,
        )

        if start_time is None or end_time is None or working_hour is None:
            raise serializers.ValidationError(
                "Working hour, start time, and end time are required."
            )

        if start_time >= end_time:
            raise serializers.ValidationError({
                "end_time": "Break end time must be after start time."
            })

        if (
            start_time < working_hour.start_time
            or end_time > working_hour.end_time
        ):
            raise serializers.ValidationError({
                "start_time": (
                    "The break must fall completely within the working hours."
                )
            })

        overlapping = ResourceBreak.objects.filter(
            working_hour=working_hour,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )

        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)

        if overlapping.exists():
            raise serializers.ValidationError(
                "This break overlaps another break."
            )

        return attrs


class ResourceHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceHoliday
        fields = [
            "id",
            "resource",
            "date",
            "start_time",
            "end_time",
            "reason",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        resource = attrs.get(
            "resource",
            self.instance.resource if self.instance else None,
        )
        holiday_date = attrs.get(
            "date",
            self.instance.date if self.instance else None,
        )
        start_time = attrs.get(
            "start_time",
            self.instance.start_time if self.instance else None,
        )
        end_time = attrs.get(
            "end_time",
            self.instance.end_time if self.instance else None,
        )

        if (start_time is None) != (end_time is None):
            raise serializers.ValidationError(
                "Provide both start_time and end_time, or leave both null for a full-day holiday."
            )

        if start_time is not None and start_time >= end_time:
            raise serializers.ValidationError({
                "end_time": "Holiday end time must be after start time."
            })

        if resource is not None and holiday_date is not None:
            same_day = ResourceHoliday.objects.filter(
                resource=resource,
                date=holiday_date,
            )

            if self.instance:
                same_day = same_day.exclude(pk=self.instance.pk)

            # A full-day holiday conflicts with every other holiday that day.
            if start_time is None and same_day.exists():
                raise serializers.ValidationError({
                    "date": "A holiday already exists for this resource on this date."
                })

            if start_time is not None:
                for existing in same_day:
                    if existing.start_time is None:
                        raise serializers.ValidationError({
                            "date": "A full-day holiday already exists for this resource on this date."
                        })

                    if (
                        existing.start_time < end_time
                        and existing.end_time > start_time
                    ):
                        raise serializers.ValidationError(
                            "This holiday overlaps another holiday for this resource."
                        )

        return attrs

class ResourceBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceBooking
        fields = [
            "id",
            "job",
            "resource",
            "start_datetime",
            "end_datetime",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def validate(self, attrs):
        start_datetime = attrs.get("start_datetime")
        end_datetime = attrs.get("end_datetime")

        if (
            start_datetime is not None
            and end_datetime is not None
            and end_datetime <= start_datetime
        ):
            raise serializers.ValidationError({
                "end_datetime": "End time must be after start time."
            })

        return attrs


from rest_framework import serializers
from resources.models import ResourceBooking


class ResourceScheduleSerializer(serializers.ModelSerializer):
    job_id = serializers.IntegerField(
        source="job.id",
        read_only=True,
    )
    job_type = serializers.CharField(
        source="job.job_type",
        read_only=True,
    )
    job_status = serializers.CharField(
        source="job.status",
        read_only=True,
    )

    class Meta:
        model = ResourceBooking
        fields = [
            "id",
            "job_id",
            "job_type",
            "job_status",
            "start_datetime",
            "end_datetime",
            "status",
        ]
        read_only_fields = fields
