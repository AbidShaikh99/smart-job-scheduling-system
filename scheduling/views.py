from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from auditlog.models import AuditLog
from auditlog.services import record_audit
from accounts.permissions import IsSchedulerRole
from jobs.models import Job
from utils.responses import error_response, success_response

from .services import schedule_job, schedule_pending_jobs


class ScheduleJobAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk)

        try:
            result = schedule_job(job)
        except ValidationError as exc:
            return error_response(
                message="Unable to schedule this job because a booking validation failed.",
                data={"details": exc.messages},
                status_code=status.HTTP_409_CONFLICT,
            )

        if not result["success"]:
            return error_response(
                message=result["message"],
                data={
                    "reason_code": result["reason_code"],
                    "conflicts": result.get("conflicts", []),
                },
                status_code=status.HTTP_409_CONFLICT,
            )

        return success_response(
            message=result["message"],
            data=result,
            status_code=status.HTTP_200_OK,
        )


class SchedulePendingJobsAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    def post(self, request):
        results = schedule_pending_jobs()

        scheduled_count = sum(
            1 for result in results if result["success"]
        )

        failed_count = len(results) - scheduled_count

        return success_response(
            message="Pending jobs processed by priority.",
            data={
                "total_processed": len(results),
                "scheduled_count": scheduled_count,
                "failed_count": failed_count,
                "results": results,
            },
            status_code=status.HTTP_200_OK,
        )
