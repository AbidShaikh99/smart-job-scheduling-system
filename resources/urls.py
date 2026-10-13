
from django.urls import path

from .views import (
    ResourceListCreateAPIView,
    ResourceDetailAPIView,
    WorkingHourListCreateAPIView,
    WorkingHourDetailAPIView,
    ResourceBreakListCreateAPIView,
    ResourceBreakDetailAPIView,
    ResourceHolidayListCreateAPIView,
    ResourceHolidayDetailAPIView,
    ResourceBookingListCreateAPIView,
    ResourceBookingCancelAPIView,
    ResourceScheduleAPIView
)


urlpatterns = [
    path("resources/", ResourceListCreateAPIView.as_view(), name="resource-list-create"),
    path("resources/<int:pk>/", ResourceDetailAPIView.as_view(), name="resource-detail"),
    path("resources/working-hours/<int:pk>/",WorkingHourDetailAPIView.as_view(),name="working-hour-detail"),
    path("resources/working-hours/",WorkingHourListCreateAPIView.as_view(),name="working-hour-list-create"),
    # Breaks
    path("resources/breaks/",ResourceBreakListCreateAPIView.as_view(),name="resource-break-list-create"),
    path("resources/breaks/<int:pk>/",ResourceBreakDetailAPIView.as_view(),name="resource-break-detail"),

    # Holidays
    path("resources/holidays/",ResourceHolidayListCreateAPIView.as_view(),name="resource-holiday-list-create"),
    path("resources/holidays/<int:pk>/",ResourceHolidayDetailAPIView.as_view(),name="resource-holiday-detail"),
    
    path("resources/bookings/",ResourceBookingListCreateAPIView.as_view(),name="resource-booking-list-create"),
    path("resources/bookings/<int:pk>/cancel/",ResourceBookingCancelAPIView.as_view(),name="resource-booking-cancel"),
    path("resources/<int:pk>/schedule/",ResourceScheduleAPIView.as_view(),name="resource-schedule"),
]