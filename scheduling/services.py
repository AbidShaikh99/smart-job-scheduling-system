from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.db.models import Case, When, Value, IntegerField
from auditlog.models import AuditLog
from auditlog.services import record_audit
from jobs.models import Job, JobDependency
from resources.models import Resource, ResourceBooking
from resources.services import create_resource_booking




def find_candidate(job, search_date=None, max_days=30, return_diagnostics=False):
    """
    Find the earliest valid slot without creating bookings.

    When return_diagnostics=True, also return conflict explanations.
    """
    required_types = job.required_resource_types or []

    if not required_types or max_days < 1:
        return (None, []) if return_diagnostics else None

    duration = timedelta(minutes=job.estimated_duration_minutes)

    if duration.total_seconds() <= 0:
        return (None, []) if return_diagnostics else None

    tz = timezone.get_current_timezone()
    first_date = search_date or job.preferred_date
    conflicts = []
    seen_conflicts = set()

    def record_conflict(resource_name, reason):
        key = (resource_name, reason)
        if key not in seen_conflicts and len(conflicts) < 20:
            seen_conflicts.add(key)
            conflicts.append({
                "resource": resource_name,
                "reason": reason,
            })

    for day_offset in range(max_days):
        current_date = first_date + timedelta(days=day_offset)
        start_time = (
            job.preferred_time if day_offset == 0 else time(0, 0)
        )

        current = timezone.make_aware(
            datetime.combine(current_date, start_time), tz
        )
        day_end = timezone.make_aware(
            datetime.combine(current_date, time(23, 59)), tz
        )

        while current + duration <= day_end:
            candidate_end = current + duration
            selected_resources = []
            used_resource_ids = set()
            valid = True

            for resource_type in required_types:
                all_resources = Resource.objects.filter(
                    resource_type=resource_type
                ).order_by("id")

                resources = all_resources.filter(
                    status=Resource.Status.AVAILABLE
                ).exclude(id__in=used_resource_ids)

                matching_resource = None

                for resource in resources:
                    try:
                        _validate_candidate(
                            resource, current, candidate_end
                        )
                        matching_resource = resource
                        break
                    except ValidationError as exc:
                        reason = (
                            exc.messages[0]
                            if exc.messages
                            else "Resource is unavailable."
                        )
                        record_conflict(resource.name, reason)

                if matching_resource is None:
                    valid = False

                    if not all_resources.exists():
                        record_conflict(
                            resource_type,
                            "No resource of this type exists.",
                        )
                    elif not resources.exists():
                        record_conflict(
                            resource_type,
                            "No unused resource of this type is available.",
                        )
                    else:
                        # All available resources failed validation.
                        # Their individual reasons were recorded above.
                        pass

                    break

                selected_resources.append(matching_resource)
                used_resource_ids.add(matching_resource.id)

            if valid:
                candidate = {
                    "start_datetime": current,
                    "end_datetime": candidate_end,
                    "resources": selected_resources,
                }
                if return_diagnostics:
                    return candidate, conflicts
                return candidate

            current += timedelta(minutes=30)

    if return_diagnostics:
        return None, conflicts

    return None




def _validate_candidate(resource, start_datetime, end_datetime):
    """Raise ValidationError if a resource cannot serve this time slot."""
    local_start = timezone.localtime(start_datetime)
    local_end = timezone.localtime(end_datetime)

    if local_start.date() != local_end.date():
        raise ValidationError("The booking must fit within one day.")

    try:
        working_hour = resource.working_hours.get(
            weekday=local_start.weekday()
        )
    except Exception:
        raise ValidationError("No working hours configured.")

    start_time = local_start.time().replace(tzinfo=None)
    end_time = local_end.time().replace(tzinfo=None)

    if (
        start_time < working_hour.start_time
        or end_time > working_hour.end_time
    ):
        raise ValidationError("Outside working hours.")

    if working_hour.breaks.filter(
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).exists():
        raise ValidationError("Overlaps a break.")

    holidays = resource.holidays.filter(date=local_start.date())
    for holiday in holidays:
        if holiday.start_time is None:
            raise ValidationError("Full-day holiday.")

        if (
            holiday.start_time < end_time
            and holiday.end_time > start_time
        ):
            raise ValidationError("Overlaps a holiday.")

    if ResourceBooking.objects.filter(
        resource=resource,
        status=ResourceBooking.Status.BOOKED,
        start_datetime__lt=end_datetime,
        end_datetime__gt=start_datetime,
    ).exists():
        raise ValidationError("Resource already booked.")

    return True



@transaction.atomic
def schedule_job(job, performed_by=None):
    """Schedule a job and record the scheduling result in audit history."""
    job = Job.objects.select_for_update().get(pk=job.pk)

    old_status = job.status

    if job.status not in [
        Job.Status.DRAFT,
        Job.Status.RESCHEDULE_REQUIRED,
    ]:
        result = {
            "success": False,
            "reason_code": "INVALID_JOB_STATUS",
            "message": "This job cannot be scheduled in its current status.",
        }

        record_audit(
            action=AuditLog.Action.SCHEDULING_FAILED,
            target=job,
            description=(
                f"Scheduling failed for Job {job.id}: "
                f"{result['reason_code']}."
            ),
            performed_by=performed_by,
            changes={
                "status": {
                    "old": old_status,
                    "new": old_status,
                },
                "reason_code": result["reason_code"],
            },
        )
        return result

    dependency_error = validate_job_dependencies(job)

    if dependency_error is not None:
        record_audit(
            action=AuditLog.Action.SCHEDULING_FAILED,
            target=job,
            description=(
                f"Scheduling failed for Job {job.id}: "
                f"{dependency_error['reason_code']}."
            ),
            performed_by=performed_by,
            changes={
                "status": {
                    "old": old_status,
                    "new": old_status,
                },
                "reason_code": dependency_error["reason_code"],
                "message": dependency_error["message"],
            },
        )
        return dependency_error

    candidate, conflicts = find_candidate(
        job,
        return_diagnostics=True,
    )

    if candidate is None:
        result = {
            "success": False,
            "reason_code": "NO_VALID_SLOT",
            "message": (
                "No valid scheduling slot was found "
                "on the preferred date."
            ),
            "conflicts": conflicts,
        }

        record_audit(
            action=AuditLog.Action.SCHEDULING_FAILED,
            target=job,
            description=(
                f"Scheduling failed for Job {job.id}: "
                "no valid slot was found."
            ),
            performed_by=performed_by,
            changes={
                "status": {
                    "old": old_status,
                    "new": old_status,
                },
                "reason_code": result["reason_code"],
                "conflicts": conflicts,
            },
        )
        return result

    created_bookings = []

    try:
        for resource in candidate["resources"]:
            booking = create_resource_booking(
                job=job,
                resource=resource,
                start_datetime=candidate["start_datetime"],
                end_datetime=candidate["end_datetime"],
            )
            created_bookings.append(booking)

        job.status = Job.Status.SCHEDULED
        job.save(update_fields=["status", "updated_at"])

        record_audit(
            action=(
                AuditLog.Action.JOB_RESCHEDULED
                if old_status == Job.Status.RESCHEDULE_REQUIRED
                else AuditLog.Action.JOB_SCHEDULED
            ),
            target=job,
            description=f"Job {job.id} was scheduled successfully.",
            performed_by=performed_by,
            changes={
                "status": {
                    "old": old_status,
                    "new": job.status,
                },
                "start_datetime": (
                    candidate["start_datetime"].isoformat()
                ),
                "end_datetime": (
                    candidate["end_datetime"].isoformat()
                ),
                "resource_ids": [
                    resource.id
                    for resource in candidate["resources"]
                ],
            },
        )

    except ValidationError:
        # Preserve the existing behavior: let the atomic transaction
        # roll back booking and job changes when validation fails.
        raise

    return {
        "success": True,
        "reason_code": None,
        "message": "Job scheduled successfully.",
        "start_datetime": candidate["start_datetime"].isoformat(),
        "end_datetime": candidate["end_datetime"].isoformat(),
        "resource_ids": [
            resource.id for resource in candidate["resources"]
        ],
    }



def schedule_pending_jobs():
    priority_order = Case(
        When(priority=Job.Priority.CRITICAL, then=Value(1)),
        When(priority=Job.Priority.HIGH, then=Value(2)),
        When(priority=Job.Priority.NORMAL, then=Value(3)),
        When(priority=Job.Priority.LOW, then=Value(4)),
        default=Value(5),
        output_field=IntegerField(),
    )

    pending_jobs = Job.objects.filter(
        status__in=[
            Job.Status.DRAFT,
            Job.Status.RESCHEDULE_REQUIRED,
        ]
    ).order_by(
        priority_order,
        "preferred_date",
        "preferred_time",
        "created_at",
        "id",
    )

    results = []

    for job in pending_jobs:
        result = schedule_job(job)

        results.append({
            "job_id": job.id,
            "priority": job.priority,
            "success": result["success"],
            "message": result["message"],
            "reason_code": result.get("reason_code"),
        })

    return results

def validate_job_dependencies(job):
    """
    Return an error if any prerequisite job is not completed.
    """
    dependencies = JobDependency.objects.filter(
        job=job
    ).select_related("depends_on")

    for dependency in dependencies:
        prerequisite = dependency.depends_on

        if prerequisite.status != Job.Status.COMPLETED:
            return {
                "success": False,
                "reason_code": "DEPENDENCY_NOT_COMPLETED",
                "message": (
                    f"Job {job.id} cannot be scheduled because "
                    f"prerequisite Job {prerequisite.id} "
                    f"is currently {prerequisite.status}."
                ),
            }

    return None