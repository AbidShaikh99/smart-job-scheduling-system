
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from accounts.permissions import IsSchedulerRole
from auditlog.models import AuditLog
from auditlog.serializers import JobHistorySerializer
from jobs.models import Job
from utils.responses import success_response


class JobHistoryAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    def get(self, request, pk):
        job = get_object_or_404(Job, pk=pk)

        history = AuditLog.objects.filter(
            target_model="Job",
            target_id=str(job.pk),
        ).select_related(
            "performed_by",
        ).order_by(
            "created_at",
            "id",
        )

        serializer = JobHistorySerializer(
            history,
            many=True,
        )

        return success_response(
            message="Job history retrieved successfully.",
            data={
                "job_id": job.pk,
                "job_type": job.job_type,
                "current_status": job.status,
                "total_events": history.count(),
                "history": serializer.data,
            },
            status_code=status.HTTP_200_OK,
        )
