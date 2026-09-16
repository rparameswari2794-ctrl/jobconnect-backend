from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.authentication import JWTAuthentication

from django.contrib.auth import get_user_model

from .models import (
    HelpRequest,
    HelpMessage,
)

from .help_serializers import (
    HelpRequestSerializer,
    HelpReplySerializer,
)

from jobseeker.models import (
    JobApplication,
    Notification,
)


User = get_user_model()


# ============================================================
# HELPER - CREATE NOTIFICATION
# ============================================================

def create_notification(
    recipient,
    title,
    message,
    notification_type="PROFILE",
):

    if not recipient:
        return

    if not recipient.is_active:
        return

    Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
    )


# ============================================================
# HELPER - NOTIFY ALL ACTIVE ADMINS
# ============================================================

def notify_all_admins(
    title,
    message,
    notification_type="PROFILE",
):

    admins = User.objects.filter(
        is_staff=True,
        is_active=True,
    )

    for admin in admins:

        create_notification(
            recipient=admin,
            title=title,
            message=message,
            notification_type=notification_type,
        )


# ============================================================
# USER - CREATE / LIST HELP REQUESTS
# ============================================================

class HelpRequestListCreateView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def get(self, request):

        status_filter = (
            request.query_params.get("status")
            or "OPEN"
        ).strip().upper()

        valid_statuses = {
            "OPEN",
            "RESOLVED",
        }

        if status_filter not in valid_statuses:

            return Response(
                {
                    "message": "Invalid status.",
                    "allowed_statuses": [
                        "OPEN",
                        "RESOLVED",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        help_requests = (
            HelpRequest.objects
            .filter(
                user=request.user,
                status=status_filter,
            )
            .prefetch_related(
                "messages__sender",
            )
            .order_by("-created_at")
        )

        serializer = HelpRequestSerializer(
            help_requests,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "help_requests": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    def post(self, request):

        subject = (
            request.data.get("subject")
            or ""
        ).strip()

        message = (
            request.data.get("message")
            or request.data.get("description")
            or ""
        ).strip()

        if not subject:

            return Response(
                {
                    "message":
                        "Please enter a subject."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not message:

            return Response(
                {
                    "message":
                        "Please describe your issue."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # ONLY NORMAL USERS CREATE SUPPORT REQUESTS
        # ----------------------------------------------------

        if request.user.is_staff:

            return Response(
                {
                    "message":
                        "Administrators cannot create "
                        "user Help & Support requests."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # CREATE REQUEST
        # ----------------------------------------------------

        with transaction.atomic():

            help_request = HelpRequest.objects.create(
                user=request.user,
                subject=subject,
                status=HelpRequest.STATUS_OPEN,
                is_read=False,
            )

            HelpMessage.objects.create(
                help_request=help_request,
                sender=request.user,
                message=message,
                is_read=False,
            )

        # ----------------------------------------------------
        # USER ROLE
        # ----------------------------------------------------

        if hasattr(request.user, "employer_profile"):

            user_role = "Employer"

        elif hasattr(request.user, "jobseeker_profile"):

            user_role = "JobSeeker"

        else:

            user_role = "User"

        # ----------------------------------------------------
        # NOTIFY ALL ADMINS
        # ----------------------------------------------------

        admin_message = (
            f"A new Help & Support request has been submitted.\n\n"
            f"User: {request.user.username}\n"
            f"Role: {user_role}\n"
            f"Subject: {subject}\n\n"
            f"Message:\n"
            f"{message}"
        )

        notify_all_admins(
            title="New Help & Support Request",
            message=admin_message,
            notification_type="PROFILE",
        )

        # ----------------------------------------------------
        # SERIALIZE
        # ----------------------------------------------------

        serializer = HelpRequestSerializer(
            help_request,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "message":
                    "Help request submitted successfully.",
                "help_request":
                    serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# USER - HELP REQUEST DETAIL
# ============================================================

class HelpRequestDetailView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request,
        help_request_id,
    ):

        try:

            help_request = (
                HelpRequest.objects
                .prefetch_related(
                    "messages__sender",
                )
                .get(
                    id=help_request_id,
                    user=request.user,
                )
            )

        except HelpRequest.DoesNotExist:

            return Response(
                {
                    "message":
                        "Help request not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = HelpRequestSerializer(
            help_request,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "help_request":
                    serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# USER - MARK HELP REQUEST MESSAGES AS READ
# ============================================================

class HelpRequestMarkReadView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    @transaction.atomic
    def patch(
        self,
        request,
        help_request_id,
    ):

        try:

            help_request = (
                HelpRequest.objects
                .select_for_update()
                .get(
                    id=help_request_id,
                    user=request.user,
                )
            )

        except HelpRequest.DoesNotExist:

            return Response(
                {
                    "message":
                        "Help request not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ----------------------------------------------------
        # MARK ONLY MESSAGES SENT BY ADMIN AS READ
        # ----------------------------------------------------

        HelpMessage.objects.filter(
            help_request=help_request,
        ).exclude(
            sender=request.user,
        ).update(
            is_read=True
        )

        help_request.is_read = True

        help_request.save(
            update_fields=[
                "is_read",
                "updated_at",
            ]
        )

        return Response(
            {
                "message":
                    "Help messages marked as read.",
                "help_request_id":
                    help_request.id,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# ADMIN - LIST HELP REQUESTS
# ============================================================

class AdminHelpRequestListView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        if not request.user.is_staff:

            return Response(
                {
                    "message":
                        "Only admin users can access "
                        "Help & Support requests."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        status_filter = (
            request.query_params.get("status")
            or "OPEN"
        ).strip().upper()

        valid_statuses = {
            "OPEN",
            "RESOLVED",
        }

        if status_filter not in valid_statuses:

            return Response(
                {
                    "message": "Invalid status.",
                    "allowed_statuses": [
                        "OPEN",
                        "RESOLVED",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        requests = (
            HelpRequest.objects
            .filter(
                status=status_filter,
            )
            .select_related(
                "user",
            )
            .prefetch_related(
                "messages__sender",
            )
            .order_by("-created_at")
        )

        serializer = HelpRequestSerializer(
            requests,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "help_requests":
                    serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# ADMIN - MARK HELP REQUEST AS READ
# ============================================================

class AdminHelpRequestMarkReadView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    @transaction.atomic
    def patch(
        self,
        request,
        help_request_id,
    ):

        if not request.user.is_staff:

            return Response(
                {
                    "message":
                        "Only admin users can mark "
                        "help requests as read."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:

            help_request = (
                HelpRequest.objects
                .select_for_update()
                .get(
                    id=help_request_id
                )
            )

        except HelpRequest.DoesNotExist:

            return Response(
                {
                    "message":
                        "Help request not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ----------------------------------------------------
        # MARK USER MESSAGES AS READ
        # ----------------------------------------------------

        HelpMessage.objects.filter(
            help_request=help_request,
        ).exclude(
            sender=request.user,
        ).update(
            is_read=True
        )

        help_request.is_read = True

        help_request.save(
            update_fields=[
                "is_read",
                "updated_at",
            ]
        )

        return Response(
            {
                "message":
                    "Help request marked as read.",
                "help_request_id":
                    help_request.id,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# ADMIN - REPLY TO HELP REQUEST
# ============================================================

class AdminHelpRequestReplyView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    @transaction.atomic
    def post(
        self,
        request,
        help_request_id,
    ):

        if not request.user.is_staff:

            return Response(
                {
                    "message":
                        "Only admin users can reply "
                        "to help requests."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:

            help_request = (
                HelpRequest.objects
                .select_for_update()
                .select_related(
                    "user",
                )
                .get(
                    id=help_request_id
                )
            )

        except HelpRequest.DoesNotExist:

            return Response(
                {
                    "message":
                        "Help request not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ----------------------------------------------------
        # DO NOT ALLOW REPLY TO DELETED/NONEXISTENT REQUEST
        # ----------------------------------------------------

        serializer = HelpReplySerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        message = serializer.validated_data[
            "message"
        ].strip()

        if not message:

            return Response(
                {
                    "message":
                        "Reply message cannot be empty."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # CREATE ADMIN MESSAGE
        # ----------------------------------------------------

        help_message = HelpMessage.objects.create(
            help_request=help_request,
            sender=request.user,
            message=message,
            is_read=False,
        )

        # ----------------------------------------------------
        # REQUEST IS READ BY ADMIN
        # ----------------------------------------------------

        help_request.is_read = True

        help_request.save(
            update_fields=[
                "is_read",
                "updated_at",
            ]
        )

        # ----------------------------------------------------
        # NOTIFY USER
        # ----------------------------------------------------

        create_notification(
            recipient=help_request.user,
            title="Help & Support Reply",
            message=(
                f"An administrator replied to your "
                f"Help & Support request:\n\n"
                f"{help_request.subject}\n\n"
                f"Reply:\n"
                f"{message}"
            ),
            notification_type="PROFILE",
        )

        message_serializer = HelpRequestSerializer(
            help_request,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "message":
                    "Reply sent successfully.",
                "help_request":
                    message_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# ADMIN - RESOLVE HELP REQUEST
# ============================================================

class AdminHelpRequestResolveView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    @transaction.atomic
    def patch(
        self,
        request,
        help_request_id,
    ):

        if not request.user.is_staff:

            return Response(
                {
                    "message":
                        "Only admin users can resolve "
                        "help requests."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:

            help_request = (
                HelpRequest.objects
                .select_for_update()
                .select_related(
                    "user",
                )
                .get(
                    id=help_request_id
                )
            )

        except HelpRequest.DoesNotExist:

            return Response(
                {
                    "message":
                        "Help request not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ----------------------------------------------------
        # ALREADY RESOLVED
        # ----------------------------------------------------

        if help_request.status == HelpRequest.STATUS_RESOLVED:

            return Response(
                {
                    "message":
                        "This help request is already resolved."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # AUTOMATIC RESOLUTION MESSAGE
        # ----------------------------------------------------

        resolution_message = (
            "Your Help & Support request has been "
            "resolved by the JobConnect admin."
        )

        HelpMessage.objects.create(
            help_request=help_request,
            sender=request.user,
            message=resolution_message,
            is_read=False,
        )

        # ----------------------------------------------------
        # MARK USER'S PREVIOUS MESSAGES AS READ BY ADMIN
        # ----------------------------------------------------

        HelpMessage.objects.filter(
            help_request=help_request,
        ).exclude(
            sender=request.user,
        ).update(
            is_read=True
        )

        # ----------------------------------------------------
        # MOVE REQUEST TO HISTORY
        # ----------------------------------------------------

        help_request.status = (
            HelpRequest.STATUS_RESOLVED
        )

        help_request.resolved_at = timezone.now()

        help_request.is_read = True

        help_request.save(
            update_fields=[
                "status",
                "resolved_at",
                "is_read",
                "updated_at",
            ]
        )

        # ----------------------------------------------------
        # NOTIFY USER
        # ----------------------------------------------------

        create_notification(
            recipient=help_request.user,
            title="Help & Support Resolved",
            message=resolution_message,
            notification_type="PROFILE",
        )

        serializer = HelpRequestSerializer(
            help_request,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "message":
                    "Help request resolved successfully.",
                "help_request":
                    serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# ADMIN - DELETE HELP REQUEST
# ============================================================

class AdminHelpRequestDeleteView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    @transaction.atomic
    def delete(
        self,
        request,
        help_request_id,
    ):

        if not request.user.is_staff:

            return Response(
                {
                    "message":
                        "Only admin users can delete "
                        "help requests."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:

            help_request = HelpRequest.objects.get(
                id=help_request_id
            )

        except HelpRequest.DoesNotExist:

            return Response(
                {
                    "message":
                        "Help request not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        request_id = help_request.id

        # ----------------------------------------------------
        # CASCADE DELETES ALL HELP MESSAGES
        # ----------------------------------------------------

        help_request.delete()

        return Response(
            {
                "message":
                    "Help request deleted successfully.",
                "help_request_id":
                    request_id,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# ADMIN - REJECT SPECIFIC HIRED APPLICATION
#
# IMPORTANT:
# The new HelpRequest model intentionally has NO application FK.
#
# Therefore application_id is supplied separately.
# help_request_id is used only to connect this action to the
# user's Help & Support conversation.
# ============================================================

class AdminRejectHiredApplicationView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    @transaction.atomic
    def patch(
        self,
        request,
        help_request_id,
    ):

        # ====================================================
        # ADMIN ONLY
        # ====================================================

        if not request.user.is_staff:

            return Response(
                {
                    "message":
                        "Only admin users can perform "
                        "this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ====================================================
        # APPLICATION ID REQUIRED
        # ====================================================

        application_id = request.data.get(
            "application_id"
        )

        if not application_id:

            return Response(
                {
                    "message":
                        "application_id is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ====================================================
        # LOCK HELP REQUEST
        # ====================================================

        try:

            help_request = (
                HelpRequest.objects
                .select_for_update()
                .select_related(
                    "user",
                )
                .get(
                    id=help_request_id
                )
            )

        except HelpRequest.DoesNotExist:

            return Response(
                {
                    "message":
                        "Help request not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ====================================================
        # LOCK APPLICATION
        # ====================================================

        try:

            application = (
                JobApplication.objects
                .select_for_update()
                .select_related(
                    "job",
                    "job__employer",
                    "jobseeker",
                    "jobseeker__user",
                )
                .get(
                    id=application_id
                )
            )

        except JobApplication.DoesNotExist:

            return Response(
                {
                    "message":
                        "Application not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ====================================================
        # SECURITY:
        # HELP REQUEST OWNER MUST BE CANDIDATE
        # ====================================================

        if (
            application.jobseeker.user_id
            != help_request.user_id
        ):

            return Response(
                {
                    "message":
                        "The selected application does not "
                        "belong to the Help & Support request user."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ====================================================
        # ONLY HIRED APPLICATION CAN BE CHANGED
        # ====================================================

        current_status = (
            application.status or ""
        ).strip().upper()

        if current_status != "HIRED":

            return Response(
                {
                    "message":
                        "Only a currently HIRED application "
                        "can be changed by this action.",
                    "current_status":
                        current_status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ====================================================
        # CANDIDATE
        # ====================================================

        jobseeker = application.jobseeker

        candidate_user = jobseeker.user

        original_employer = application.job.employer

        original_company_name = (
            original_employer.company_name
        )

        original_job_title = (
            application.job.title
        )

        # ====================================================
        # CHANGE ONLY THIS APPLICATION
        # ====================================================

        application.status = "REJECTED"

        application.save(
            update_fields=[
                "status",
            ]
        )

        # ====================================================
        # CANDIDATE NOTIFICATION
        # ====================================================

        create_notification(
            recipient=candidate_user,
            title="Hiring Decision Updated",
            message=(
                f"Your hiring application for "
                f"{original_job_title} at "
                f"{original_company_name} has been changed "
                f"from HIRED to REJECTED after admin review."
            ),
            notification_type="JOB",
        )

        # ====================================================
        # FIND ALL OTHER APPLICATIONS
        #
        # IMPORTANT:
        # THEIR STATUS IS NOT CHANGED.
        # ====================================================

        other_applications = (
            JobApplication.objects
            .select_related(
                "job",
                "job__employer",
            )
            .filter(
                jobseeker=jobseeker,
            )
            .exclude(
                id=application.id,
            )
        )

        notified_employers = set()

        for other_application in other_applications:

            employer = (
                other_application.job.employer
            )

            if not employer:
                continue

            employer_user = employer.user

            if not employer_user:
                continue

            # ------------------------------------------------
            # DON'T NOTIFY ORIGINAL EMPLOYER HERE
            # ------------------------------------------------

            if employer_user.id == original_employer.user_id:

                continue

            # ------------------------------------------------
            # DON'T DUPLICATE NOTIFICATION
            # ------------------------------------------------

            if employer_user.id in notified_employers:

                continue

            notified_employers.add(
                employer_user.id
            )

            create_notification(
                recipient=employer_user,
                title="Hiring Update",
                message=(
                    f"A candidate you have an application "
                    f"for was previously marked as hired by "
                    f"{original_company_name}, but that hiring "
                    f"did not go through.\n\n"
                    f"The candidate's application with your "
                    f"company remains unchanged.\n\n"
                    f"You may continue reviewing the candidate "
                    f"according to your normal hiring process."
                ),
                notification_type="JOB",
            )

        # ====================================================
        # ORIGINAL EMPLOYER NOTIFICATION
        # ====================================================

        create_notification(
            recipient=original_employer.user,
            title="Hiring Application Changed",
            message=(
                f"The application for "
                f"{original_job_title} has been changed "
                f"from HIRED to REJECTED by an administrator "
                f"after verification with the candidate."
            ),
            notification_type="JOB",
        )

        # ====================================================
        # ADD CORRECTION MESSAGE TO HELP CONVERSATION
        # ====================================================

        correction_message = (
            f"The hiring application for "
            f"{original_job_title} at "
            f"{original_company_name} was verified with you "
            f"and changed from HIRED to REJECTED.\n\n"
            f"Your other applications were not changed."
        )

        HelpMessage.objects.create(
            help_request=help_request,
            sender=request.user,
            message=correction_message,
            is_read=False,
        )

        # ====================================================
        # RESOLVE HELP REQUEST
        # ====================================================

        help_request.status = (
            HelpRequest.STATUS_RESOLVED
        )

        help_request.resolved_at = timezone.now()

        help_request.is_read = True

        help_request.save(
            update_fields=[
                "status",
                "resolved_at",
                "is_read",
                "updated_at",
            ]
        )

        # ====================================================
        # FINAL RESPONSE
        # ====================================================

        return Response(
            {
                "message":
                    "The selected hired application has "
                    "been changed to REJECTED successfully.",

                "help_request_id":
                    help_request.id,

                "application_id":
                    application.id,

                "status":
                    application.status,

                "other_applications_changed":
                    False,

                "other_employers_notified":
                    len(notified_employers),
            },
            status=status.HTTP_200_OK,
        )