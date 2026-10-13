
from django.core.exceptions import ValidationError
from django.db import transaction
from resources.models import ResourceBooking
from jobs.models import Job,JobDependency

from auditlog.models import AuditLog
from auditlog.services import record_audit


ALLOWED_TRANSITIONS = {
    Job.Status.DRAFT: {
        Job.Status.CANCELLED,
    },
    Job.Status.SCHEDULED: {
        Job.Status.ASSIGNED,
        Job.Status.CANCELLED,
        Job.Status.RESCHEDULE_REQUIRED,
    },
    Job.Status.ASSIGNED: {
        Job.Status.IN_PROGRESS,
        Job.Status.CANCELLED,
        Job.Status.RESCHEDULE_REQUIRED,
    },
    Job.Status.IN_PROGRESS: {
        Job.Status.COMPLETED,
        Job.Status.FAILED,
    },
    Job.Status.RESCHEDULE_REQUIRED: {
        Job.Status.SCHEDULED,
        Job.Status.CANCELLED,
    },
    Job.Status.COMPLETED: set(),
    Job.Status.CANCELLED: set(),
    Job.Status.FAILED: set(),
}




@transaction.atomic
def change_job_status(job, new_status, performed_by=None):
    # Lock the latest job record before changing its status.
    job = Job.objects.select_for_update().get(pk=job.pk)

    if new_status not in Job.Status.values:
        raise ValidationError("Invalid job status.")

    old_status = job.status
    allowed_statuses = ALLOWED_TRANSITIONS.get(old_status, set())

    if new_status not in allowed_statuses:
        raise ValidationError(
            f"Cannot change job status from {old_status} to {new_status}."
        )

    # Update the job status.
    job.status = new_status
    job.save(update_fields=["status", "updated_at"])

    # Select the appropriate audit action.
    if new_status == Job.Status.SCHEDULED:
        if old_status == Job.Status.RESCHEDULE_REQUIRED:
            audit_action = AuditLog.Action.JOB_RESCHEDULED
        else:
            audit_action = AuditLog.Action.JOB_SCHEDULED
    else:
        action_by_status = {
            Job.Status.IN_PROGRESS: AuditLog.Action.JOB_STARTED,
            Job.Status.COMPLETED: AuditLog.Action.JOB_COMPLETED,
            Job.Status.CANCELLED: AuditLog.Action.JOB_CANCELLED,
            Job.Status.FAILED: AuditLog.Action.JOB_FAILED,
        }

        audit_action = action_by_status.get(
            new_status,
            AuditLog.Action.STATUS_CHANGED,
        )

    # Save the audit history.
    record_audit(
        action=audit_action,
        target=job,
        description=(
            f"Job {job.id} status changed from "
            f"{old_status} to {new_status}."
        ),
        performed_by=performed_by,
        changes={
            "status": {
                "old": old_status,
                "new": new_status,
            }
        },
    )

    return job



def create_job_dependency(job, depends_on):
    dependency = JobDependency(
        job=job,
        depends_on=depends_on,
    )

    # Runs clean() and the model's other validation checks.
    dependency.full_clean()

    dependency.save()

    return dependency



@transaction.atomic
def cancel_job(job_id, performed_by=None):
    job = Job.objects.select_for_update().get(pk=job_id)

    old_status = job.status

    cancellable_statuses = [
        Job.Status.DRAFT,
        Job.Status.SCHEDULED,
        Job.Status.ASSIGNED,
        Job.Status.RESCHEDULE_REQUIRED,
    ]

    if old_status not in cancellable_statuses:
        raise ValidationError(
            "This job cannot be cancelled in its current status."
        )

    bookings = list(
        ResourceBooking.objects.select_for_update().filter(
            job=job,
            status=ResourceBooking.Status.BOOKED,
        )
    )

    # Cancel all active bookings associated with this job.
    for booking in bookings:
        booking.status = ResourceBooking.Status.CANCELLED

    if bookings:
        ResourceBooking.objects.bulk_update(
            bookings,
            ["status"],
        )

    # Cancel the job.
    job.status = Job.Status.CANCELLED
    job.save(update_fields=["status", "updated_at"])

    # Save the audit history.
    record_audit(
        action=AuditLog.Action.JOB_CANCELLED,
        target=job,
        description=f"Job {job.id} was cancelled.",
        performed_by=performed_by,
        changes={
            "status": {
                "old": old_status,
                "new": job.status,
            },
            "cancelled_booking_count": len(bookings),
        },
    )

    return job, len(bookings)
