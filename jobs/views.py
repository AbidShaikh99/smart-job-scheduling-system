from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from resources.models import ResourceBooking
from django.utils import timezone
from datetime import datetime, timedelta
from accounts.permissions import IsAdminOrCustomer, IsSchedulerRole
from utils.responses import error_response, success_response
from jobs.services import change_job_status, cancel_job
from resources.models import Resource
from .models import Job

from auditlog.models import AuditLog
from auditlog.services import record_audit
from .serializers import( JobCreateSerializer, JobStatusUpdateSerializer, JobRescheduleSerializer,StartJobSerializer, CompleteJobSerializer
, JobConflictSerializer)


class JobListCreateAPIView(APIView):
    permission_classes = [IsAdminOrCustomer]

    def get(self, request):
        if request.user.role == "ADMIN" or request.user.is_superuser:
            jobs = Job.objects.all().order_by("-created_at")
        else:
            jobs = Job.objects.filter(
                customer=request.user
            ).order_by("-created_at")

        serializer = JobCreateSerializer(jobs, many=True)

        return success_response(
            message="Jobs retrieved successfully.",
            data=serializer.data,
        )

    def post(self, request):
        serializer = JobCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        job = serializer.save(
            customer=request.user,
            status=Job.Status.DRAFT,
        )

        # Record job creation in the audit log.
        record_audit(
            action=AuditLog.Action.CREATED,
            target=job,
            description=f"Job {job.id} was created.",
            performed_by=request.user,
            changes={
                "status": {
                    "old": None,
                    "new": Job.Status.DRAFT,
                }
            },
        )

        return success_response(
            message="Job created successfully.",
            data=JobCreateSerializer(job).data,
            status_code=status.HTTP_201_CREATED,
        )

    
class JobStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSchedulerRole]

    def post(self, request, pk):
        serializer = JobStatusUpdateSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            job = get_object_or_404(
                Job.objects.select_for_update(),
                pk=pk,
            )

            try:
                job = change_job_status(
                    job,
                    serializer.validated_data["status"],
                    performed_by=request.user,
                )
            except ValidationError as exc:
                return error_response(
                    message="Invalid job status transition.",
                    data={"details": exc.messages},
                    status_code=status.HTTP_409_CONFLICT,
                )

        return success_response(
            message="Job status updated successfully.",
            data={
                "job_id": job.id,
                "status": job.status,
            },
            status_code=status.HTTP_200_OK,
        )

class JobCancelAPIView(APIView):
    permission_classes = [IsSchedulerRole]


    @transaction.atomic
    def post(self, request, pk):
        try:
            job, cancelled_booking_count = cancel_job(
                pk,
                performed_by=request.user,
            )

        except Job.DoesNotExist:
            return error_response(
                message="Job not found.",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as exc:
            return error_response(
                message="This job cannot be cancelled in its current status.",
                data={"details": exc.messages},
                status_code=status.HTTP_409_CONFLICT,
            )

        return success_response(
            message="Job cancelled and resource bookings released successfully.",
            data={
                "job_id": job.id,
                "status": job.status,
                "cancelled_booking_count": cancelled_booking_count,
            },
            status_code=status.HTTP_200_OK,
        )



class JobRescheduleAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    @transaction.atomic
    def post(self, request, pk):
        serializer = JobRescheduleSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        job = get_object_or_404(
            Job.objects.select_for_update(),
            pk=pk,
        )

        allowed_statuses = [
            Job.Status.SCHEDULED,
            Job.Status.ASSIGNED,
            Job.Status.RESCHEDULE_REQUIRED,
        ]

        if job.status not in allowed_statuses:
            return error_response(
                message="This job cannot be rescheduled in its current status.",
                data={"current_status": job.status},
                status_code=status.HTTP_409_CONFLICT,
            )

        # Save the old values before making changes.
        old_status = job.status
        old_preferred_date = job.preferred_date
        old_preferred_time = job.preferred_time

        # Lock and cancel existing bookings.
        bookings = list(
            ResourceBooking.objects.select_for_update().filter(
                job=job,
                status=ResourceBooking.Status.BOOKED,
            )
        )

        for booking in bookings:
            booking.status = ResourceBooking.Status.CANCELLED

        if bookings:
            ResourceBooking.objects.bulk_update(
                bookings,
                ["status", "updated_at"],
            )

        # Update the job's preferred date, time, and status.
        job.preferred_date = serializer.validated_data["preferred_date"]
        job.preferred_time = serializer.validated_data["preferred_time"]
        job.status = Job.Status.RESCHEDULE_REQUIRED

        job.save(
            update_fields=[
                "preferred_date",
                "preferred_time",
                "status",
                "updated_at",
            ]
        )

        # Record the rescheduling request in the audit log.
        record_audit(
            action=AuditLog.Action.JOB_RESCHEDULED,
            target=job,
            description=(
                f"Job {job.id} was requested for rescheduling."
            ),
            performed_by=request.user,
            changes={
                "status": {
                    "old": old_status,
                    "new": job.status,
                },
                "preferred_date": {
                    "old": (
                        str(old_preferred_date)
                        if old_preferred_date is not None
                        else None
                    ),
                    "new": str(job.preferred_date),
                },
                "preferred_time": {
                    "old": (
                        old_preferred_time.strftime("%H:%M:%S")
                        if old_preferred_time is not None
                        else None
                    ),
                    "new": (
                        job.preferred_time.strftime("%H:%M:%S")
                        if job.preferred_time is not None
                        else None
                    ),
                },
                "cancelled_booking_count": len(bookings),
            },
        )

        return success_response(
            message=(
                "Reschedule request saved. Run the scheduling API "
                "to find a new slot."
            ),
            data={
                "job_id": job.id,
                "status": job.status,
                "preferred_date": str(job.preferred_date),
                "preferred_time": (
                    job.preferred_time.strftime("%H:%M:%S")
                ),
                "cancelled_booking_count": len(bookings),
            },
            status_code=status.HTTP_200_OK,
        )


class StartJobAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk)

        serializer = StartJobSerializer(
            data=request.data,
            context={"job": job},
        )

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            
            job = change_job_status(
                job,
                Job.Status.IN_PROGRESS,
                performed_by=request.user,
            )
        except ValidationError as exc:
            return error_response(
                message="Unable to start this job.",
                data={"details": exc.messages},
                status_code=status.HTTP_409_CONFLICT,
            )

        return success_response(
            message="Job started successfully.",
            data={
                "job_id": job.id,
                "status": job.status,
            },
            status_code=status.HTTP_200_OK,
        )


class CompleteJobAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk)

        # Step 1: Validate the job using the serializer
        serializer = CompleteJobSerializer(
            data=request.data,
            context={"job": job},
        )

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Step 2: Change the job status through the service
        try:
            
            job = change_job_status(
                job,
                Job.Status.COMPLETED,
                performed_by=request.user,
            )

        except ValidationError as exc:
            return error_response(
                message="Unable to complete this job.",
                data={"details": exc.messages},
                status_code=status.HTTP_409_CONFLICT,
            )

        # Step 3: Return the successful response
        return success_response(
            message="Job completed successfully.",
            data={
                "job_id": job.id,
                "status": job.status,
            },
            status_code=status.HTTP_200_OK,
        )



class JobConflictsAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    def get(self, request, pk):
        job = get_object_or_404(Job, pk=pk)

        if not job.preferred_date or not job.preferred_time:
            return success_response(
                message="Job conflicts retrieved successfully.",
                data={
                    "job_id": job.id,
                    "has_conflicts": False,
                    "conflicts": [],
                    "note": (
                        "The job has no preferred date or time. "
                        "A specific conflict check cannot be performed."
                    ),
                },
                status_code=status.HTTP_200_OK,
            )


        local_start = timezone.make_aware(
            datetime.combine(
                job.preferred_date,
                job.preferred_time,
            ),
            timezone.get_current_timezone(),
        )
        local_end = local_start + timedelta(
            minutes=job.estimated_duration_minutes
        )

        conflicts = []

        required_types = job.required_resource_types or []

        for resource_type in required_types:
            resources = Resource.objects.filter(
                resource_type=resource_type,
            ).order_by("id")

            if not resources.exists():
                conflicts.append({
                    "resource_id": 0,
                    "resource_name": str(resource_type),
                    "reason": (
                        f"No resource exists for type {resource_type}."
                    ),
                })
                continue

            for resource in resources:
                if resource.status != Resource.Status.AVAILABLE:
                    conflicts.append({
                        "resource_id": resource.id,
                        "resource_name": resource.name,
                        "reason": (
                            f"Resource status is {resource.status}."
                        ),
                    })
                    continue

                overlap = ResourceBooking.objects.filter(
                    resource=resource,
                    status=ResourceBooking.Status.BOOKED,
                    start_datetime__lt=local_end,
                    end_datetime__gt=local_start,
                ).exists()

                if overlap:
                    conflicts.append({
                        "resource_id": resource.id,
                        "resource_name": resource.name,
                        "reason": (
                            "The resource already has a booking "
                            "during this time."
                        ),
                    })

        serializer = JobConflictSerializer(
            conflicts,
            many=True,
        )

        return success_response(
            message="Job conflicts retrieved successfully.",
            data={
                "job_id": job.id,
                "has_conflicts": bool(conflicts),
                "conflicts": serializer.data,
            },
            status_code=status.HTTP_200_OK,
        )
