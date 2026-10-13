from django.conf import settings
from django.db import models


class Job(models.Model):

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SCHEDULED = "SCHEDULED", "Scheduled"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        FAILED = "FAILED", "Failed"
        RESCHEDULE_REQUIRED = "RESCHEDULE_REQUIRED", "Reschedule required"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="jobs",
    )

    job_type = models.CharField(max_length=100)

    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    estimated_duration_minutes = models.PositiveIntegerField()

    preferred_date = models.DateField()
    preferred_time = models.TimeField()

    location = models.CharField(max_length=255)

    required_resource_types = models.JSONField(default=list)

    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job #{self.pk} - {self.job_type}"



class JobDependency(models.Model):
    """
    A job that must be completed before another job can proceed.
    """

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="dependencies",
    )

    depends_on = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="dependent_jobs",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "depends_on"],
                name="unique_job_dependency",
            ),
            models.CheckConstraint(
                condition=~models.Q(job=models.F("depends_on")),
                name="job_cannot_depend_on_itself",
            ),
        ]

    
    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()

        if not self.job_id or not self.depends_on_id:
            return

        if self.job_id == self.depends_on_id:
            raise ValidationError(
                "A job cannot depend on itself."
            )

        if self.creates_cycle():
            raise ValidationError(
                "This dependency would create a circular dependency."
            )

    
    def creates_cycle(self):
        """
        Return True if this dependency would create a cycle.
        """
        if not self.job_id or not self.depends_on_id:
            return False

        if self.job_id == self.depends_on_id:
            return True

        # Starting from the prerequisite, follow its own
        # prerequisites. If we reach this job, a cycle exists.
        pending = [self.depends_on_id]
        visited = set()

        while pending:
            current_id = pending.pop()

            if current_id == self.job_id:
                return True

            if current_id in visited:
                continue

            visited.add(current_id)

            prerequisite_ids = JobDependency.objects.filter(
                job_id=current_id
            ).values_list("depends_on_id", flat=True)

            pending.extend(prerequisite_ids)

        return False

    def __str__(self):
        return f"Job {self.job_id} depends on Job {self.depends_on_id}"
