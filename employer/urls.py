from django.urls import path

from .views import (
    EmployerSignupView,
    EmployerProfileView,
    EmployerJobListCreateView,
    EmployerDashboardView,
    EmployerApplicantsView,
    EmployerApplicantProfileView,
    EmployerApplicantDetailView,
    EmployerApplicationStatusView,
    EmployerCloseJobView,
    EmployerForgotPasswordView,
    EmployerLoginView,
    EmployerResetPasswordView,
    EmployerVerifyOTPView,
)


urlpatterns = [

    # =====================================================
    # EMPLOYER SIGNUP
    # =====================================================

    path(
        "signup/",
        EmployerSignupView.as_view(),
        name="employer-signup"
    ),
    # =====================================================
    # EMPLOYER LOGIN
    # =====================================================

    path(
        "login/",
        EmployerLoginView.as_view(),
        name="employer-login"
    ),

    path(
        "forgot-password/",
        EmployerForgotPasswordView.as_view(),
        name="employer-forgot-password"
    ),

    # =====================================================
    # EMPLOYER VERIFY OTP
    #
    # POST:
    # /api/auth/employer/verify-otp/
    # =====================================================

    path(
        "verify-otp/",
        EmployerVerifyOTPView.as_view(),
        name="employer-verify-otp"
    ),

    # =====================================================
    # EMPLOYER RESET PASSWORD
    #
    # POST:
    # /api/auth/employer/reset-password/
    # =====================================================

    path(
        "reset-password/",
        EmployerResetPasswordView.as_view(),
        name="employer-reset-password"
    ),

    # =====================================================
    # EMPLOYER PROFILE
    # =====================================================

    path(
        "profile/",
        EmployerProfileView.as_view(),
        name="employer-profile"
    ),

    # =====================================================
    # EMPLOYER JOBS
    # =====================================================

    path(
        "jobs/",
        EmployerJobListCreateView.as_view(),
        name="employer-jobs"
    ),

    # =====================================================
    # EMPLOYER DASHBOARD
    # =====================================================

    path(
        "dashboard/",
        EmployerDashboardView.as_view(),
        name="employer-dashboard"
    ),

    # =====================================================
    # JOB APPLICANTS
    # =====================================================

    path(
        "jobs/<int:job_id>/applicants/",
        EmployerApplicantsView.as_view(),
        name="employer-job-applicants"
    ),

    # =====================================================
    # VIEW APPLICANT PROFILE
    #
    # React calls:
    # /api/auth/employer/applications/1/
    # =====================================================

    path(
        "applications/<int:application_id>/",
        EmployerApplicantDetailView.as_view(),
        name="employer-applicant-detail"
    ),

    # =====================================================
    # UPDATE APPLICATION STATUS
    #
    # PATCH:
    # /api/auth/employer/applications/1/status/
    # =====================================================

    path(
        "applications/<int:application_id>/status/",
        EmployerApplicationStatusView.as_view(),
        name="employer-application-status"
    ),
    path(
        "jobs/<int:job_id>/close/",
        EmployerCloseJobView.as_view(),
        name="employer-close-job"
    ),
]