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

    AdminNotificationUsersView,
    AdminSendNotificationView,
)
from .help_views import (

    # =====================================================
    # HELP & SUPPORT
    # =====================================================
    HelpRequestListCreateView,
    HelpRequestDetailView,
    HelpRequestMarkReadView,

    AdminHelpRequestListView,
    AdminHelpRequestMarkReadView,
    AdminHelpRequestReplyView,
    AdminHelpRequestResolveView,
    AdminHelpRequestDeleteView,

    AdminRejectHiredApplicationView,
)


urlpatterns = [

    # =====================================================
    # LOGIN
    # =====================================================

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

    # =====================================================
    # ADMIN - NOTIFICATIONS
    # =====================================================

    path(
        "notification-users/",
        AdminNotificationUsersView.as_view(),
        name="admin-notification-users"
    ),

    path(
        "notifications/",
        AdminSendNotificationView.as_view(),
        name="admin-send-notification"
    ),

    # =====================================================
    # USER - HELP & SUPPORT
    # =====================================================

    # GET  -> user's help requests
    # POST -> create a new help request
    path(
        "help/",
        HelpRequestListCreateView.as_view(),
        name="help-list-create"
    ),

    # GET -> one help request + messages
    path(
        "help/<int:help_request_id>/",
        HelpRequestDetailView.as_view(),
        name="help-detail"
    ),

    # POST -> mark user's help request as read
    path(
        "help/<int:help_request_id>/read/",
        HelpRequestMarkReadView.as_view(),
        name="help-mark-read"
    ),

    # =====================================================
    # ADMIN - HELP & SUPPORT INBOX
    # =====================================================

    # GET
    # ?status=OPEN
    # ?status=RESOLVED
    path(
        "admin/help/",
        AdminHelpRequestListView.as_view(),
        name="admin-help-list"
    ),

    # POST -> mark one help request as read
    path(
        "admin/help/<int:help_request_id>/read/",
        AdminHelpRequestMarkReadView.as_view(),
        name="admin-help-mark-read"
    ),

    # POST -> reply to the user
    path(
        "admin/help/<int:help_request_id>/reply/",
        AdminHelpRequestReplyView.as_view(),
        name="admin-help-reply"
    ),

    # POST -> resolve request
    # Creates automatic resolution message
    # Keeps request in database as RESOLVED
    path(
        "admin/help/<int:help_request_id>/resolve/",
        AdminHelpRequestResolveView.as_view(),
        name="admin-help-resolve"
    ),

    # DELETE -> permanently delete help request
    path(
        "admin/help/<int:help_request_id>/delete/",
        AdminHelpRequestDeleteView.as_view(),
        name="admin-help-delete"
    ),

    # =====================================================
    # ADMIN - HIRED APPLICATION CORRECTION
    # =====================================================

    # POST
    # {
    #     "application_id": 123
    # }
    #
    # Changes only the selected HIRED application
    # from HIRED -> REJECTED.
    path(
        "admin/help/<int:help_request_id>/reject-hired/",
        AdminRejectHiredApplicationView.as_view(),
        name="admin-reject-hired-application"
    ),
]