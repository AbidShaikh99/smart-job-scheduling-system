
from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    message = "Only administrators can access this resource."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.role == "ADMIN"
                or user.is_superuser
            )
        )


class IsCustomerRole(BasePermission):
    message = "Only customers can access this resource."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role == "CUSTOMER"
        )


class IsSchedulerRole(BasePermission):
    message = "Only schedulers can access this resource."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.role == "SCHEDULER"
                or user.role == "ADMIN"
                or user.is_superuser
            )
        )


class IsAdminOrCustomer(BasePermission):
    message = "Only administrators and customers can access this resource."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.role in ["ADMIN", "CUSTOMER"]
                or user.is_superuser
            )
        )