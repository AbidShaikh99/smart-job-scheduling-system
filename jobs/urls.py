from django.urls import path

from .views import (JobListCreateAPIView, JobStatusUpdateAPIView, JobCancelAPIView, JobRescheduleAPIView ,
StartJobAPIView,CompleteJobAPIView,JobConflictsAPIView)


urlpatterns = [
    path("jobs/", JobListCreateAPIView.as_view(), name="job-list-create"),
    path("jobs/<int:pk>/status/",JobStatusUpdateAPIView.as_view(),name="job-status-update"),
    path("jobs/<int:pk>/cancel/",JobCancelAPIView.as_view(),name="job-cancel"),
    path("jobs/<int:pk>/reschedule/",JobRescheduleAPIView.as_view(),name="job-reschedule"),
    path("jobs/<int:pk>/start/", StartJobAPIView.as_view(), name = "job-start"),
    path("jobs/<int:pk>/complete/",CompleteJobAPIView.as_view(),name="complete-job"),
    path("jobs/<int:pk>/conflicts/",JobConflictsAPIView.as_view(),name="job-conflicts"),
]