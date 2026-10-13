from django.urls import path
from auditlog.views import JobHistoryAPIView

urlpatterns = [
    path("jobs/<int:pk>/history/",JobHistoryAPIView.as_view(),name="job-history"),
]
