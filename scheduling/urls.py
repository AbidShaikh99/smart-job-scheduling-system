
from django.urls import path

from .views import ScheduleJobAPIView, SchedulePendingJobsAPIView

urlpatterns = [
    path(
        "jobs/<int:pk>/schedule/",
        ScheduleJobAPIView.as_view(),
        name="schedule-job",
    ),
    path(
    "queue/",
    SchedulePendingJobsAPIView.as_view(),
    name="schedule-pending-jobs",
),
]
