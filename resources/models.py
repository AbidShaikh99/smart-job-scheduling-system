from django.db import models


class Resource(models.Model):

    class ResourceType(models.TextChoices):
        TECHNICIAN = "TECHNICIAN", "Technician"
        MACHINE = "MACHINE", "Machine"
        VEHICLE = "VEHICLE", "Vehicle"
        LABORATORY = "LABORATORY", "Laboratory"
        ROOM = "ROOM", "Room"

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        BUSY = "BUSY", "Busy"
        ON_LEAVE = "ON_LEAVE", "On leave"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        INACTIVE = "INACTIVE", "Inactive"

    name = models.CharField(max_length=150)

    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )

    location = models.CharField(max_length=255)

    description = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.resource_type})"


class ResourceWorkingHour(models.Model):

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="working_hours",
    )

    weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices,
    )

    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "weekday"],
                name="unique_resource_working_day",
            ),
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="working_hour_start_before_end",
            ),
        ]

    def __str__(self):
        return (
            f"{self.resource.name} - "
            f"{self.get_weekday_display()}"
        )


class ResourceBreak(models.Model):

    working_hour = models.ForeignKey(
        ResourceWorkingHour,
        on_delete=models.CASCADE,
        related_name="breaks",
    )

    name = models.CharField(
        max_length=100,
        default="Break",
    )

    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="resource_break_start_before_end",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            raise ValidationError(
                "Break start time must be before end time."
            )

        if self.working_hour_id:
            working_hour = self.working_hour

            if (
                self.start_time < working_hour.start_time
                or self.end_time > working_hour.end_time
            ):
                raise ValidationError(
                    "Break must fall within working hours."
                )

    def __str__(self):
        return f"{self.working_hour} - {self.name}"


class ResourceHoliday(models.Model):

    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="holidays",
    )

    date = models.DateField()

    # Both empty means the resource is unavailable all day.
    # If both are set, only that time interval is blocked.
    start_time = models.TimeField(
        null=True,
        blank=True,
    )

    end_time = models.TimeField(
        null=True,
        blank=True,
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    class Meta:
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "date"],
                condition=models.Q(
                    start_time__isnull=True,
                    end_time__isnull=True,
                ),
                name="unique_full_day_resource_holiday",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        start_time__isnull=True,
                        end_time__isnull=True,
                    )
                    | models.Q(
                        start_time__isnull=False,
                        end_time__isnull=False,
                        start_time__lt=models.F("end_time"),
                    )
                ),
                name="valid_resource_holiday_times",
            ),
        ]

    def clean(self):
        super().clean()

        if (self.start_time is None) != (self.end_time is None):
            raise ValidationError(
                "Provide both start and end times, or neither."
            )

        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            raise ValidationError(
                "Holiday start time must be before end time."
            )

    def __str__(self):
        return f"{self.resource.name} - {self.date}"



class ResourceBooking(models.Model):
    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Booked"
        CANCELLED = "CANCELLED", "Cancelled"

    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.PROTECT,
        related_name="resource_bookings",
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.BOOKED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_datetime"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    start_datetime__lt=models.F("end_datetime")
                ),
                name="booking_start_before_end",
            ),
        ]

    def __str__(self):
        return f"Job {self.job_id} - {self.resource.name}"