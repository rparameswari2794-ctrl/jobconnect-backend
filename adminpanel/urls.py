from django.urls import path

from .views import (
    AdminDashboardView,
    AdminVerificationQueueView,
    CommonLoginView,

    AdminJobSeekerListView,
    AdminJobSeekerProfileView,
    AdminJobSeekerApproveView,
    AdminJobSeekerRejectView,

    AdminEmployerProfileView,
    AdminEmployerApproveView,
    AdminEmployerRejectView,

    AdminReportsFlagsView,
    AdminUsersView,
)


urlpatterns = [
    path(
        "login/",
        CommonLoginView.as_view(),
        name="common-login"
    ),


    # =====================================================
    # ADMIN DASHBOARD
    # =====================================================

    path(
        "dashboard/",
        AdminDashboardView.as_view(),
        name="admin-dashboard"
    ),

    # =====================================================
    # VERIFICATION QUEUE
    # =====================================================

    path(
        "verifications/",
        AdminVerificationQueueView.as_view(),
        name="admin-verification-queue"
    ),

    # =====================================================
    # JOB SEEKERS
    # =====================================================

    path(
        "jobseekers/",
        AdminJobSeekerListView.as_view(),
        name="admin-jobseekers"
    ),

    path(
        "jobseekers/<int:pk>/",
        AdminJobSeekerProfileView.as_view(),
        name="admin-jobseeker-profile"
    ),

    path(
        "jobseekers/<int:pk>/approve/",
        AdminJobSeekerApproveView.as_view(),
        name="admin-jobseeker-approve"
    ),

    path(
        "jobseekers/<int:pk>/reject/",
        AdminJobSeekerRejectView.as_view(),
        name="admin-jobseeker-reject"
    ),

    # =====================================================
    # REPORTS
    # =====================================================

    path(
        "reports/",
        AdminReportsFlagsView.as_view(),
        name="admin-reports"
    ),

    # =====================================================
    # USERS
    # =====================================================

    path(
        "users/",
        AdminUsersView.as_view(),
        name="admin-users"
    ),

    # =====================================================
    # EMPLOYERS
    # =====================================================

    path(
        "employers/<int:pk>/",
        AdminEmployerProfileView.as_view(),
        name="admin-employer-profile"
    ),

    path(
        "employers/<int:pk>/approve/",
        AdminEmployerApproveView.as_view(),
        name="admin-employer-approve"
    ),

    path(
        "employers/<int:pk>/reject/",
        AdminEmployerRejectView.as_view(),
        name="admin-employer-reject"
    ),
]