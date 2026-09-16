from django.urls import path

from .views import (
    # =====================================================
    # AUTHENTICATION
    # =====================================================
    JobSeekerSignupView,
    JobSeekerLoginView,
    CurrentUserView,
    LogoutView,

    

    # =====================================================
    # PROFILE
    # =====================================================
    JobSeekerProfileView,
    SubmitProfileView,
    ProfileStatusView,

    # =====================================================
    # EDUCATION
    # =====================================================
    EducationListCreateView,
    EducationDetailView,

    # =====================================================
    # EXPERIENCE
    # =====================================================
    ExperienceListCreateView,
    ExperienceDetailView,

    # =====================================================
    # PROJECT
    # =====================================================
    ProjectListCreateView,
    ProjectDetailView,

    # =====================================================
    # JOBS
    # =====================================================
    JobListView,
    ApplyJobView,
    MyApplicationsView,

    # =====================================================
    # NOTIFICATIONS
    # =====================================================
    NotificationListView,
    NotificationReadView,
    MarkAllNotificationsReadView,
    NotificationDeleteView,

    # =====================================================
    # CHAT
    # =====================================================

    ConversationListCreateView,
    ConversationMessagesView,
    ConversationReadView,
    ConversationDeleteView,

    # =====================================================
    # PASSWORD
    # =====================================================
    ForgotPasswordView,
    VerifyOTPView,
    ResetPasswordView,
)


urlpatterns = [

    # =====================================================
    # AUTH
    # =====================================================

    path(
        "signup/",
        JobSeekerSignupView.as_view(),
        name="jobseeker-signup",
    ),

    path(
        "login/",
        JobSeekerLoginView.as_view(),
        name="jobseeker-login",
    ),

    path(
        "me/",
        CurrentUserView.as_view(),
        name="current-user",
    ),

    path(
        "logout/",
        LogoutView.as_view(),
        name="jobseeker-logout",
    ),
    

    # =====================================================
    # PROFILE
    # =====================================================

    path(
        "profile/",
        JobSeekerProfileView.as_view(),
        name="jobseeker-profile",
    ),

    path(
        "profile/status/",
        ProfileStatusView.as_view(),
        name="profile-status",
    ),

    path(
        "profile/submit/",
        SubmitProfileView.as_view(),
        name="jobseeker-profile-submit",
    ),


    # =====================================================
    # EDUCATION
    # =====================================================

    path(
        "education/",
        EducationListCreateView.as_view(),
        name="education",
    ),

    path(
        "education/<int:pk>/",
        EducationDetailView.as_view(),
        name="education-detail",
    ),


    # =====================================================
    # EXPERIENCE
    # =====================================================

    path(
        "experience/",
        ExperienceListCreateView.as_view(),
        name="experience",
    ),

    path(
        "experience/<int:pk>/",
        ExperienceDetailView.as_view(),
        name="experience-detail",
    ),


    # =====================================================
    # FIND JOBS
    # =====================================================

    path(
        "jobs/",
        JobListView.as_view(),
        name="job-list",
    ),

    path(
        "jobs/<int:job_id>/apply/",
        ApplyJobView.as_view(),
        name="apply-job",
    ),


    # =====================================================
    # PROJECTS
    # =====================================================

    path(
        "projects/",
        ProjectListCreateView.as_view(),
        name="project-list-create",
    ),

    path(
        "projects/<int:pk>/",
        ProjectDetailView.as_view(),
        name="project-detail",
    ),


    # =====================================================
    # MY APPLICATIONS
    # =====================================================

    path(
        "applications/",
        MyApplicationsView.as_view(),
        name="my-applications",
    ),


    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    # IMPORTANT:
    # Keep read-all before the integer notification URL.

    path(
        "notifications/read-all/",
        MarkAllNotificationsReadView.as_view(),
        name="notification-read-all",
    ),

    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notification-list",
    ),

    path(
        "notifications/<int:notification_id>/read/",
        NotificationReadView.as_view(),
        name="notification-read",
    ),

    path(
        "notifications/<int:notification_id>/",
        NotificationDeleteView.as_view(),
        name="notification-delete",
    ),

    # =====================================================
    # CHAT
    # =====================================================

    path(
        "chat/conversations/",
        ConversationListCreateView.as_view(),
        name="chat-conversations",
    ),

    path(
        "chat/conversations/<int:conversation_id>/messages/",
        ConversationMessagesView.as_view(),
        name="chat-messages",
    ),

    path(
        "chat/conversations/<int:conversation_id>/read/",
        ConversationReadView.as_view(),
        name="chat-read",
    ),

    path(
        "chat/conversations/<int:conversation_id>/",
        ConversationDeleteView.as_view(),
        name="chat-delete",
    ),


    # =====================================================
    # FORGOT PASSWORD
    # =====================================================

    path(
        "forgot-password/",
        ForgotPasswordView.as_view(),
        name="forgot-password",
    ),

    path(
        "verify-otp/",
        VerifyOTPView.as_view(),
        name="verify-otp",
    ),

    path(
        "reset-password/",
        ResetPasswordView.as_view(),
        name="reset-password",
    ),
]