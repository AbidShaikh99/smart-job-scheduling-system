
from django.conf import settings
from django.db import models


class AuditLog(models.Model):

    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        DELETED = "DELETED", "Deleted"

        JOB_SCHEDULED = "JOB_SCHEDULED", "Job Scheduled"
        JOB_RESCHEDULED = "JOB_RESCHEDULED", "Job Rescheduled"
        JOB_STARTED = "JOB_STARTED", "Job Started"
        JOB_COMPLETED = "JOB_COMPLETED", "Job Completed"
        JOB_CANCELLED = "JOB_CANCELLED", "Job Cancelled"
        JOB_FAILED = "JOB_FAILED", "Job Failed"

        RESOURCE_UNAVAILABLE = (
            "RESOURCE_UNAVAILABLE",
            "Resource Unavailable",
        )

        RESOURCE_AVAILABLE = (
            "RESOURCE_AVAILABLE",
            "Resource Available",
        )

        STATUS_CHANGED = "STATUS_CHANGED", "Status Changed"
        SCHEDULING_FAILED = "SCHEDULING_FAILED", "Scheduling Failed"
        LOGIN = "LOGIN", "Login"
        LOGOUT = "LOGOUT", "Logout"

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    action = models.CharField(
        max_length=40,
        choices=Action.choices,
        db_index=True,
    )

    target_model = models.CharField(
        max_length=100,
        db_index=True,
    )

    target_id = models.CharField(
        max_length=100,
        db_index=True,
    )

    description = models.TextField()

    changes = models.JSONField(
        default=dict,
        blank=True,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return (
            f"{self.action} - "
            f"{self.target_model} #{self.target_id}"
        )
