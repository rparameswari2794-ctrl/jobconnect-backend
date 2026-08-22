from rest_framework.permissions import BasePermission


class IsApprovedJobSeeker(BasePermission):

    message = (
        "Your account must be approved by admin "
        "before you can apply for jobs."
    )

    def has_permission(self, request, view):

        if not request.user.is_authenticated:
            return False

        try:

            profile = request.user.jobseeker_profile

        except Exception:

            return False

        return (
            profile.profile_completed
            and profile.approval_status == "approved"
        )