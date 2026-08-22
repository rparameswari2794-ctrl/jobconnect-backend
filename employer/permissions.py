from rest_framework.permissions import BasePermission


class IsApprovedEmployer(BasePermission):

    message = (
        "Your employer account must be approved "
        "by admin before posting jobs."
    )

    def has_permission(self, request, view):

        if not request.user.is_authenticated:
            return False

        try:

            profile = request.user.employer_profile

        except Exception:

            return False

        return (
            profile.profile_completed
            and profile.approval_status == "approved"
        )