from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from accounts.permissions import IsAdminRole
from utils.responses import error_response, success_response

from django.core.exceptions import ValidationError as DjangoValidationError

from accounts.permissions import IsSchedulerRole
from .models import ResourceBooking
from .serializers import ResourceBookingSerializer
from .services import create_resource_booking
from .models import (Resource, ResourceWorkingHour, ResourceBreak, ResourceHoliday)
from .serializers import (ResourceSerializer, ResourceWorkingHourSerializer,
    ResourceBreakSerializer,
    ResourceHolidaySerializer,
    ResourceScheduleSerializer,)


class ResourceListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        resources = Resource.objects.all().order_by("id")

        if request.user.role != "ADMIN" and not request.user.is_superuser:
            resources = resources.filter(
                status=Resource.Status.AVAILABLE
            )

        serializer = ResourceSerializer(resources, many=True)

        return success_response(
            message="Resources retrieved successfully.",
            data=serializer.data,
        )

    def post(self, request):
        if not (
            request.user.role == "ADMIN"
            or request.user.is_superuser
        ):
            return error_response(
                message="Only administrators can create resources.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = ResourceSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        resource = serializer.save()

        return success_response(
            message="Resource created successfully.",
            data=ResourceSerializer(resource).data,
            status_code=status.HTTP_201_CREATED,
        )


class ResourceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Resource.objects.get(pk=pk)
        except Resource.DoesNotExist:
            return None

    def get(self, request, pk):
        resource = self.get_object(pk)

        if resource is None:
            return error_response(
                message="Resource not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        is_admin = (
            request.user.role == "ADMIN"
            or request.user.is_superuser
        )

        if not is_admin and resource.status != Resource.Status.AVAILABLE:
            return error_response(
                message="Resource not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return success_response(
            message="Resource retrieved successfully.",
            data=ResourceSerializer(resource).data,
        )

    def patch(self, request, pk):
        if not (
            request.user.role == "ADMIN"
            or request.user.is_superuser
        ):
            return error_response(
                message="Only administrators can update resources.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        resource = self.get_object(pk)

        if resource is None:
            return error_response(
                message="Resource not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = ResourceSerializer(
            resource,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        resource = serializer.save()

        return success_response(
            message="Resource updated successfully.",
            data=ResourceSerializer(resource).data,
        )

    def delete(self, request, pk):
        if not (
            request.user.role == "ADMIN"
            or request.user.is_superuser
        ):
            return error_response(
                message="Only administrators can deactivate resources.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        resource = self.get_object(pk)

        if resource is None:
            return error_response(
                message="Resource not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        resource.status = Resource.Status.INACTIVE
        resource.save(update_fields=["status", "updated_at"])

        return success_response(
            message="Resource deactivated successfully.",
            data={"id": resource.id, "status": resource.status},
        )
    


class AdminListCreateAPIView(APIView):
    permission_classes = [IsAdminRole]

    queryset = None
    serializer_class = None
    object_label = "Record"

    def get(self, request):
        objects = self.queryset.all()
        serializer = self.serializer_class(objects, many=True)

        return success_response(
            message=f"{self.object_label} list retrieved successfully.",
            data=serializer.data,
        )

    def post(self, request):
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        obj = serializer.save()

        return success_response(
            message=f"{self.object_label} created successfully.",
            data=self.serializer_class(obj).data,
            status_code=status.HTTP_201_CREATED,
        )


class AdminDetailAPIView(APIView):
    permission_classes = [IsAdminRole]

    queryset = None
    serializer_class = None
    object_label = "Record"

    def get_object(self, pk):
        try:
            return self.queryset.get(pk=pk)
        except self.queryset.model.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self.get_object(pk)

        if obj is None:
            return error_response(
                message=f"{self.object_label} not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return success_response(
            message=f"{self.object_label} retrieved successfully.",
            data=self.serializer_class(obj).data,
        )

    def patch(self, request, pk):
        obj = self.get_object(pk)

        if obj is None:
            return error_response(
                message=f"{self.object_label} not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.serializer_class(
            obj,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        obj = serializer.save()

        return success_response(
            message=f"{self.object_label} updated successfully.",
            data=self.serializer_class(obj).data,
        )

    def delete(self, request, pk):
        obj = self.get_object(pk)

        if obj is None:
            return error_response(
                message=f"{self.object_label} not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        obj.delete()

        return success_response(
            message=f"{self.object_label} deleted successfully.",
            data=None,
        )


class WorkingHourListCreateAPIView(AdminListCreateAPIView):
    queryset = ResourceWorkingHour.objects.select_related("resource")
    serializer_class = ResourceWorkingHourSerializer
    object_label = "Working hour"


class WorkingHourDetailAPIView(AdminDetailAPIView):
    queryset = ResourceWorkingHour.objects.select_related("resource")
    serializer_class = ResourceWorkingHourSerializer
    object_label = "Working hour"


class ResourceBreakListCreateAPIView(AdminListCreateAPIView):
    queryset = ResourceBreak.objects.select_related(
        "working_hour",
        "working_hour__resource",
    )
    serializer_class = ResourceBreakSerializer
    object_label = "Break"


class ResourceBreakDetailAPIView(AdminDetailAPIView):
    queryset = ResourceBreak.objects.select_related(
        "working_hour",
        "working_hour__resource",
    )
    serializer_class = ResourceBreakSerializer
    object_label = "Break"


class ResourceHolidayListCreateAPIView(AdminListCreateAPIView):
    queryset = ResourceHoliday.objects.select_related("resource")
    serializer_class = ResourceHolidaySerializer
    object_label = "Holiday"


class ResourceHolidayDetailAPIView(AdminDetailAPIView):
    queryset = ResourceHoliday.objects.select_related("resource")
    serializer_class = ResourceHolidaySerializer
    object_label = "Holiday"


class ResourceBookingListCreateAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    def get(self, request):
        bookings = ResourceBooking.objects.select_related(
            "job",
            "resource",
        ).order_by("start_datetime")

        serializer = ResourceBookingSerializer(bookings, many=True)

        return success_response(
            message="Bookings retrieved successfully.",
            data=serializer.data,
        )

    def post(self, request):
        serializer = ResourceBookingSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            booking = create_resource_booking(
                job=serializer.validated_data["job"],
                resource=serializer.validated_data["resource"],
                start_datetime=serializer.validated_data["start_datetime"],
                end_datetime=serializer.validated_data["end_datetime"],
            )
        except DjangoValidationError as exc:
            return error_response(
                message="Booking could not be created.",
                data={"detail": exc.messages},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="Resource booked successfully.",
            data=ResourceBookingSerializer(booking).data,
            status_code=status.HTTP_201_CREATED,
        )


class ResourceBookingCancelAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    def post(self, request, pk):
        try:
            booking = ResourceBooking.objects.get(pk=pk)
        except ResourceBooking.DoesNotExist:
            return error_response(
                message="Booking not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if booking.status == ResourceBooking.Status.CANCELLED:
            return error_response(
                message="Booking is already cancelled.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = ResourceBooking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])

        return success_response(
            message="Booking cancelled successfully.",
            data=ResourceBookingSerializer(booking).data,
        )
    

class ResourceScheduleAPIView(APIView):
    permission_classes = [IsSchedulerRole]

    def get(self, request, pk):
        resource = get_object_or_404(Resource, pk=pk)

        bookings = (
            ResourceBooking.objects
            .filter(resource=resource)
            .select_related("job")
            .order_by("start_datetime", "id")
        )

        serializer = ResourceScheduleSerializer(
            bookings,
            many=True,
        )

        return success_response(
            message="Resource schedule retrieved successfully.",
            data={
                "resource_id": resource.id,
                "resource_name": resource.name,
                "resource_status": resource.status,
                "total_bookings": bookings.count(),
                "schedule": serializer.data,
            },
            status_code=status.HTTP_200_OK,
        )
