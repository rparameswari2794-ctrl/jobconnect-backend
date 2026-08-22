from rest_framework.permissions import BasePermission


class IsAdminUserRole(BasePermission):

    message = "Only admin users can access this API."

    def has_permission(self, request, view):

        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )