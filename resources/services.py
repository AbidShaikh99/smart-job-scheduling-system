
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from jobs.models import Job
from .models import (
    Resource,
    ResourceBooking,
    ResourceBreak,
    ResourceHoliday,
    ResourceWorkingHour,
)


from django.db.models import Q


def models_q_holiday_overlap(start_time, end_time):
    return (
        Q(start_time__isnull=True, end_time__isnull=True)
        | Q(
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
    )
@transaction.atomic
def create_resource_booking(job, resource, start_datetime, end_datetime):
    """
    Create one booking after validating the job, resource,
    working hours, breaks, holidays, and existing bookings.
    """

    # Lock the resource row to reduce concurrent booking conflicts.
    try:
        resource = Resource.objects.select_for_update().get(pk=resource.pk)
    except Resource.DoesNotExist:
        raise ValidationError("Resource not found.")

    if end_datetime <= start_datetime:
        raise ValidationError("End time must be after start time.")

    if resource.status != Resource.Status.AVAILABLE:
        raise ValidationError(
            f"Resource is not available. Current status: {resource.status}."
        )

    if resource.resource_type not in job.required_resource_types:
        raise ValidationError(
            "This resource type is not required by the job."
        )

    if job.status in [
        Job.Status.CANCELLED,
        Job.Status.COMPLETED,
        Job.Status.FAILED,
    ]:
        raise ValidationError(
            "A booking cannot be created for a closed or cancelled job."
        )

    if (
        (end_datetime - start_datetime).total_seconds()
        != job.estimated_duration_minutes * 60
    ):
        raise ValidationError(
            "Booking duration must match the job's estimated duration."
        )

    # Use the project's local timezone for weekday and holiday checks.
    local_start = timezone.localtime(start_datetime)
    local_end = timezone.localtime(end_datetime)

    # This MVP supports bookings contained within one working day.
    if local_start.date() != local_end.date():
        raise ValidationError(
            "Bookings must start and finish on the same local date."
        )

    weekday = local_start.weekday()
    booking_date = local_start.date()
    start_time = local_start.time().replace(tzinfo=None)
    end_time = local_end.time().replace(tzinfo=None)

    try:
        working_hour = ResourceWorkingHour.objects.get(
            resource=resource,
            weekday=weekday,
        )
    except ResourceWorkingHour.DoesNotExist:
        raise ValidationError(
            "The resource has no working hours configured for this weekday."
        )

    if (
        start_time < working_hour.start_time
        or end_time > working_hour.end_time
    ):
        raise ValidationError(
            "The booking falls outside the resource's working hours."
        )

    # Reject bookings overlapping a break.
    break_conflict = ResourceBreak.objects.filter(
        working_hour=working_hour,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).exists()

    if break_conflict:
        raise ValidationError(
            "The booking overlaps a resource break."
        )

    # Reject bookings overlapping a full-day or partial-day holiday.
    holiday_conflict = ResourceHoliday.objects.filter(
        resource=resource,
        date=booking_date,
    ).filter(
        # Full-day holiday, or a partial holiday that overlaps.
        models_q_holiday_overlap(start_time, end_time)
    ).exists()

    if holiday_conflict:
        raise ValidationError(
            "The resource is unavailable during a holiday."
        )

    # Half-open interval check: [start, end).
    # A booking ending at 12:00 does not conflict with one starting at 12:00.
    conflict = ResourceBooking.objects.filter(
        resource=resource,
        status=ResourceBooking.Status.BOOKED,
        start_datetime__lt=end_datetime,
        end_datetime__gt=start_datetime,
    ).exists()

    if conflict:
        raise ValidationError(
            "The resource already has a booking during this time."
        )

    return ResourceBooking.objects.create(
        job=job,
        resource=resource,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        status=ResourceBooking.Status.BOOKED,
    )



@transaction.atomic
def mark_jobs_for_rescheduling(resource_id):
    # Find future bookings for this resource.
    bookings = list(
        ResourceBooking.objects.select_for_update()
        .filter(
            resource_id=resource_id,
            status=ResourceBooking.Status.BOOKED,
            start_datetime__gt=timezone.now(),
            job__status__in=[
                Job.Status.SCHEDULED,
                Job.Status.ASSIGNED,
            ],
        )
        .select_related("job")
        .order_by("job_id")
    )

    # Collect each affected job only once.
    affected_jobs = {}

    for booking in bookings:
        affected_jobs[booking.job_id] = booking.job

    # Mark those jobs as needing a new schedule.
    jobs_to_update = list(affected_jobs.values())

    for job in jobs_to_update:
        job.status = Job.Status.RESCHEDULE_REQUIRED

    if jobs_to_update:
        Job.objects.bulk_update(
            jobs_to_update,
            ["status"],
        )

    return jobs_to_update
