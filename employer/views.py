from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError

from secrets import randbelow
from datetime import timedelta

from rest_framework_simplejwt.tokens import RefreshToken

from jobseeker.models import Notification, JobApplication
from adminpanel.models import PasswordResetOTP

from .models import EmployerProfile, Job

from .serializers import (
    EmployerSignupSerializer,
    EmployerProfileSerializer,
    JobSerializer,
    EmployerApplicantDetailSerializer,
)

from django.db import transaction


User = get_user_model()


# =========================================================
# NOTIFY ADMIN WHEN EMPLOYER PROFILE IS UPDATED
# =========================================================

def notify_admin_of_employer_profile_update(
    profile,
    changed_fields
):

    if not changed_fields:
        return

    field_labels = {
        "company_name": "Company Name",
        "contact_name": "Contact Name",
        "representative_position": "Representative Position",
        "phone": "Phone",
        "company_email": "Company Email",
        "company_description": "Company Description",
        "website": "Website",
        "location": "Location",
        "company_logo": "Company Logo",
        "company_gst_certificate": "GST Certificate",
        "company_registration_certificate": "Registration Certificate",
        "authorization_letter": "Authorization Letter",
    }

    changed_labels = []

    for field in changed_fields.keys():

        changed_labels.append(
            field_labels.get(field, field)
        )

    fields_text = ", ".join(changed_labels)

    message = (
        f"Employer '{profile.company_name}' has updated "
        f"their company profile.\n\n"
        f"Updated fields:\n"
        f"{fields_text}\n\n"
        f"Approval status: {profile.approval_status}"
    )

    # =====================================================
    # YOUR SYSTEM HAS ONE ADMIN
    # =====================================================

    admin = User.objects.filter(
        is_staff=True,
        is_active=True
    ).first()

    if not admin:

        print(
            "EMPLOYER PROFILE NOTIFICATION: "
            "No active admin found."
        )

        return

    # =====================================================
    # CREATE ADMIN NOTIFICATION
    # =====================================================

    Notification.objects.create(
        recipient=admin,
        title="Employer Profile Updated",
        message=message,
        notification_type="PROFILE",
    )

    print(
        "ADMIN NOTIFICATION CREATED FOR EMPLOYER PROFILE:",
        profile.id
    )


# =========================================================
# NOTIFY JOBSEEKERS + ADMIN WHEN EMPLOYER POSTS A JOB
# =========================================================

def notify_new_job_posted(job):
    """
    When an employer creates a new job:

    1. Normal job:
       Notify all active jobseekers.

    2. Disability-only job:
       Notify only active jobseekers whose profile
       has disability=True.

    3. Notify the one active admin.

    4. Do NOT notify the employer who created the job.
    """

    employer = job.employer

    company_name = employer.company_name

    # =====================================================
    # COMMON MESSAGE FOR JOBSEEKERS
    # =====================================================

    jobseeker_message = (
        f"New job posted by {company_name}.\n\n"
        f"Job Title: {job.title}\n"
        f"Location: {job.location}\n"
        f"Job Type: {job.get_job_type_display()}\n"
        f"Work Mode: {job.get_work_mode_display()}"
    )

    # =====================================================
    # DISABILITY-ONLY JOB MESSAGE
    # =====================================================

    if job.is_disability_job:

        jobseeker_message += (
            "\n\n"
            "Eligibility: This job is exclusively "
            "for jobseekers with a disability."
        )

    notifications = []

    # =====================================================
    # JOBSEEKER NOTIFICATION TARGET
    # =====================================================

    if job.is_disability_job:

        # -------------------------------------------------
        # DISABILITY-ONLY JOB
        # -------------------------------------------------
        # Notify only jobseekers whose profile has
        # disability=True.
        # -------------------------------------------------

        jobseeker_users = User.objects.filter(
            is_active=True,
            jobseeker_profile__isnull=False,
            jobseeker_profile__disability=True
        )

    else:

        # -------------------------------------------------
        # NORMAL JOB
        # -------------------------------------------------
        # Notify all active jobseekers.
        # -------------------------------------------------

        jobseeker_users = User.objects.filter(
            is_active=True,
            jobseeker_profile__isnull=False
        )

    # =====================================================
    # CREATE JOBSEEKER NOTIFICATIONS
    # =====================================================

    for user in jobseeker_users:

        notifications.append(
            Notification(
                recipient=user,
                title="New Job Posted",
                message=jobseeker_message,
                notification_type="JOB",
            )
        )

    # =====================================================
    # ONE ADMIN
    # =====================================================

    admin = User.objects.filter(
        is_staff=True,
        is_active=True
    ).first()

    if admin:

        admin_message = (
            f"Employer '{company_name}' posted a new job.\n\n"
            f"Job Title: {job.title}\n"
            f"Location: {job.location}\n"
            f"Job Type: {job.get_job_type_display()}\n"
            f"Work Mode: {job.get_work_mode_display()}"
        )

        if job.is_disability_job:

            admin_message += (
                "\n\n"
                "Eligibility: Disability-only job."
            )

        notifications.append(
            Notification(
                recipient=admin,
                title="New Job Posted",
                message=admin_message,
                notification_type="JOB",
            )
        )

    # =====================================================
    # CREATE ALL NOTIFICATIONS
    # =====================================================

    if notifications:

        Notification.objects.bulk_create(
            notifications
        )

        print(
            "NEW JOB NOTIFICATIONS CREATED:",
            len(notifications),
            "JOB ID:",
            job.id,
            "DISABILITY ONLY:",
            job.is_disability_job
        )

    else:

        print(
            "NO NEW JOB NOTIFICATIONS CREATED.",
            "JOB ID:",
            job.id
        )


# =========================================================
# EMPLOYER SIGNUP
# =========================================================

class EmployerSignupView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        print("\n========================================")
        print("EMPLOYER SIGNUP REQUEST")
        print("========================================")
        print("DATA:", request.data)
        print("========================================")

        serializer = EmployerSignupSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            print("\n========================================")
            print("EMPLOYER SIGNUP VALIDATION ERRORS")
            print("========================================")
            print(serializer.errors)
            print("========================================\n")

            return Response(
                {
                    "message":
                        "Employer signup validation failed.",

                    "errors":
                        serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            profile = serializer.save()

            return Response(
                {
                    "message":
                        "Employer account created successfully.",

                    "approval_status":
                        profile.approval_status,

                    "profile_completed":
                        profile.profile_completed,

                    "employer": {

                        "id":
                            profile.id,

                        "company_name":
                            profile.company_name,

                        "contact_name":
                            profile.contact_name,

                        "email":
                            profile.user.email,
                    }
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:

            print(
                "EMPLOYER SIGNUP ERROR:",
                str(e)
            )

            return Response(
                {
                    "message":
                        "Unable to create employer account.",

                    "error":
                        str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =========================================================
# EMPLOYER FORGOT PASSWORD
# =========================================================

class EmployerForgotPasswordView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get(
            "email",
            ""
        ).strip().lower()

        if not email:

            return Response(
                {
                    "detail":
                        "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            user = User.objects.get(
                email__iexact=email
            )

            employer = user.employer_profile

        except User.DoesNotExist:

            return Response(
                {
                    "detail":
                        "No employer account found with this email address."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =================================================
        # DELETE PREVIOUS OTPs
        # =================================================

        PasswordResetOTP.objects.filter(
            user=user
        ).delete()

        # =================================================
        # GENERATE 6 DIGIT OTP
        # =================================================

        otp = str(
            100000 + randbelow(900000)
        )

        # =================================================
        # SAVE OTP
        # =================================================

        PasswordResetOTP.objects.create(
            user=user,
            otp=otp,
            expires_at=timezone.now() + timedelta(
                minutes=10
            )
        )

        # =================================================
        # SEND OTP
        # =================================================

        send_mail(
            "JobConnect Employer Password Reset OTP",

            f"""
Hello {employer.contact_name},

Your JobConnect password reset OTP is:

{otp}

This OTP is valid for 10 minutes.

If you did not request a password reset, please ignore this email.

Thank you,
JobConnect
""",

            settings.DEFAULT_FROM_EMAIL,

            [email],

            fail_silently=False,
        )

        return Response(
            {
                "message":
                    "OTP has been sent to your registered email."
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER VERIFY OTP
# =========================================================

class EmployerVerifyOTPView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get(
            "email",
            ""
        ).strip().lower()

        otp = str(
            request.data.get(
                "otp",
                ""
            )
        ).strip()

        if not email or not otp:

            return Response(
                {
                    "detail":
                        "Email and OTP are required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            user = User.objects.get(
                email__iexact=email
            )

            user.employer_profile

        except User.DoesNotExist:

            return Response(
                {
                    "detail":
                        "No employer account found with this email address."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        try:

            reset_otp = (
                PasswordResetOTP.objects
                .filter(
                    user=user,
                    otp=otp,
                    is_verified=False
                )
                .latest("created_at")
            )

        except PasswordResetOTP.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Invalid OTP."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =================================================
        # CHECK EXPIRY
        # =================================================

        if reset_otp.is_expired():

            reset_otp.delete()

            return Response(
                {
                    "detail":
                        "OTP has expired. Please request a new OTP."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =================================================
        # MARK OTP VERIFIED
        # =================================================

        reset_otp.is_verified = True

        reset_otp.save(
            update_fields=[
                "is_verified"
            ]
        )

        return Response(
            {
                "message":
                    "OTP verified successfully.",

                "verified":
                    True,

                "email":
                    email
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER RESET PASSWORD
# =========================================================

class EmployerResetPasswordView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get(
            "email",
            ""
        ).strip().lower()

        new_password = request.data.get(
            "new_password",
            ""
        )

        if not email or not new_password:

            return Response(
                {
                    "detail":
                        "Email and new password are required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            user = User.objects.get(
                email__iexact=email
            )

            user.employer_profile

        except User.DoesNotExist:

            return Response(
                {
                    "detail":
                        "No employer account found with this email address."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =================================================
        # GET VERIFIED OTP
        # =================================================

        try:

            reset_otp = (
                PasswordResetOTP.objects
                .filter(
                    user=user,
                    is_verified=True
                )
                .latest("created_at")
            )

        except PasswordResetOTP.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Please verify your OTP first."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =================================================
        # CHECK OTP EXPIRY
        # =================================================

        if reset_otp.is_expired():

            reset_otp.delete()

            return Response(
                {
                    "detail":
                        "OTP verification has expired. Please request a new OTP."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =================================================
        # VALIDATE PASSWORD
        # =================================================

        try:

            validate_password(
                new_password,
                user
            )

        except ValidationError as e:

            return Response(
                {
                    "detail":
                        e.messages
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =================================================
        # CHANGE PASSWORD
        # =================================================

        user.set_password(
            new_password
        )

        user.save()

        # =================================================
        # OTP CAN NO LONGER BE REUSED
        # =================================================

        reset_otp.delete()

        return Response(
            {
                "message":
                    "Password reset successfully. You can now login."
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER LOGIN
# =========================================================

class EmployerLoginView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get(
            "email"
        )

        password = request.data.get(
            "password"
        )

        if not email or not password:

            return Response(
                {
                    "detail":
                        "Email and password are required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        email = email.strip().lower()

        # =================================================
        # FIND USER
        # =================================================

        try:

            user_obj = User.objects.get(
                email__iexact=email
            )

        except User.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Invalid email or password."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # =================================================
        # AUTHENTICATE
        # =================================================

        user = authenticate(
            username=user_obj.username,
            password=password
        )

        if user is None:

            return Response(
                {
                    "detail":
                        "Invalid email or password."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # =================================================
        # EMPLOYER PROFILE
        # =================================================

        try:

            profile = user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =================================================
        # JWT
        # =================================================

        refresh = RefreshToken.for_user(
            user
        )

        return Response(
            {
                "refresh":
                    str(refresh),

                "access":
                    str(refresh.access_token),

                "user": {

                    "id":
                        user.id,

                    "name":
                        profile.contact_name,

                    "company_name":
                        profile.company_name,

                    "email":
                        user.email,

                    "role":
                        "employer",

                    "approval_status":
                        profile.approval_status,

                    "profile_completed":
                        profile.profile_completed,
                }
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER PROFILE
# =========================================================

class EmployerProfileView(APIView):

    authentication_classes = [JWTAuthentication]

    permission_classes = [IsAuthenticated]

    # =====================================================
    # GET PROFILE
    # =====================================================

    def get(self, request):

        try:

            profile = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EmployerProfileSerializer(
            profile
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # =====================================================
    # PATCH PROFILE
    # =====================================================

    def patch(self, request):

        try:

            profile = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =================================================
        # CURRENT STATUS
        # =================================================

        previous_status = (
            profile.approval_status or ""
        ).lower().strip()

        # =================================================
        # PENDING + COMPLETED = LOCKED
        # =================================================

        if (
            previous_status == "pending"
            and profile.profile_completed
        ):

            return Response(
                {
                    "message":
                        "Your company profile is currently "
                        "waiting for admin approval. "
                        "You cannot edit it at this time.",

                    "approval_status":
                        profile.approval_status,

                    "profile_completed":
                        profile.profile_completed,

                    "locked":
                        True,
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =================================================
        # STORE OLD VALUES
        # =================================================

        tracked_fields = [

            "company_name",
            "contact_name",
            "representative_position",
            "phone",
            "company_email",
            "company_description",
            "website",
            "location",
            "company_logo",
            "company_gst_certificate",
            "company_registration_certificate",
            "authorization_letter",
        ]

        old_values = {}

        for field in tracked_fields:

            old_values[field] = getattr(
                profile,
                field,
                None
            )

        # =================================================
        # VALIDATE UPDATE
        # =================================================

        serializer = EmployerProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message":
                        "Company profile validation failed.",

                    "errors":
                        serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =================================================
        # SAVE REQUESTED CHANGES
        # =================================================

        profile = serializer.save()

        # =================================================
        # DETECT CHANGED FIELDS
        # =================================================

        changed_fields = {}

        for field in tracked_fields:

            old_value = old_values.get(
                field
            )

            new_value = getattr(
                profile,
                field,
                None
            )

            # =================================================
            # FILE FIELD COMPARISON
            # =================================================

            if field in [
                "company_logo",
                "company_gst_certificate",
                "company_registration_certificate",
                "authorization_letter",
            ]:

                old_name = (
                    getattr(
                        old_value,
                        "name",
                        None
                    )
                    if old_value
                    else None
                )

                new_name = (
                    getattr(
                        new_value,
                        "name",
                        None
                    )
                    if new_value
                    else None
                )

                if old_name != new_name:

                    changed_fields[field] = {
                        "old":
                            old_name,

                        "new":
                            new_name,
                    }

            else:

                old_text = (
                    str(old_value).strip()
                    if old_value is not None
                    else ""
                )

                new_text = (
                    str(new_value).strip()
                    if new_value is not None
                    else ""
                )

                if old_text != new_text:

                    changed_fields[field] = {
                        "old":
                            old_value,

                        "new":
                            new_value,
                    }

        # =================================================
        # CHECK PROFILE COMPLETION
        # =================================================

        required_fields = [

            profile.company_name,

            profile.contact_name,

            profile.phone,

            profile.company_email,

            profile.company_description,

            profile.location,

            profile.representative_position,
        ]

        profile.profile_completed = all(
            bool(
                value
                and
                str(value).strip()
            )
            for value in required_fields
        )

        # =================================================
        # APPROVED → EDITED → PENDING
        # =================================================

        if previous_status == "approved":

            profile.approval_status = "pending"

            profile.rejection_reason = ""

        # =================================================
        # REJECTED → EDITED → PENDING
        # =================================================

        elif previous_status == "rejected":

            profile.approval_status = "pending"

            profile.rejection_reason = ""

        # =================================================
        # NEW PROFILE
        # =================================================

        elif previous_status == "pending":

            profile.approval_status = "pending"

        # =================================================
        # SAVE FINAL STATE
        # =================================================

        profile.save()

        # =================================================
        # NOTIFY ADMIN
        # =================================================

        if changed_fields:

            notify_admin_of_employer_profile_update(
                profile,
                changed_fields
            )

        # =================================================
        # RESPONSE
        # =================================================

        response_data = EmployerProfileSerializer(
            profile
        ).data

        return Response(
            response_data,
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER JOB LIST + CREATE
# =========================================================

class EmployerJobListCreateView(APIView):

    authentication_classes = [JWTAuthentication]

    permission_classes = [IsAuthenticated]

    # =====================================================
    # GET JOBS
    # =====================================================

    def get(self, request):

        try:

            employer = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        jobs = Job.objects.filter(
            employer=employer
        ).order_by(
            "-created_at"
        )

        serializer = JobSerializer(
            jobs,
            many=True
        )

        # =====================================================
        # ACTIVE APPLICANT COUNT FOR EACH JOB
        #
        # Rejected applications stay in the database and remain
        # visible in the applicant-management page, but they are
        # excluded from the count displayed in My Jobs.
        # =====================================================

        jobs_data = serializer.data

        for job_data in jobs_data:
            job_id = job_data.get("id")

            if job_id is None:
                job_data["applicants_count"] = 0
                continue

            job_data["applicants_count"] = (
                JobApplication.objects
                .filter(job_id=job_id)
                .exclude(status__iexact="REJECTED")
                .count()
            )

        return Response(
            jobs_data,
            status=status.HTTP_200_OK
        )

    # =====================================================
    # CREATE JOB
    # =====================================================

    def post(self, request):

        print("\n========================================")
        print("EMPLOYER CREATE JOB")
        print("========================================")

        print(
            "USER:",
            request.user
        )

        print(
            "AUTHENTICATED:",
            request.user.is_authenticated
        )

        print(
            "DATA:",
            request.data
        )

        print("========================================\n")

        # =================================================
        # GET EMPLOYER PROFILE
        # =================================================

        try:

            employer = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =================================================
        # ADMIN APPROVAL CHECK
        # =================================================

        approval_status = (
            employer.approval_status or ""
        ).lower().strip()

        print(
            "EMPLOYER APPROVAL STATUS:",
            approval_status
        )

        if approval_status != "approved":

            return Response(
                {
                    "message":
                        "Your employer account is not approved yet.",

                    "approval_status":
                        employer.approval_status,

                    "profile_completed":
                        employer.profile_completed,
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =================================================
        # PROFILE COMPLETION CHECK
        # =================================================

        print(
            "EMPLOYER PROFILE COMPLETED:",
            employer.profile_completed
        )

        if employer.profile_completed is not True:

            return Response(
                {
                    "message":
                        "Please complete your employer profile "
                        "before posting a job.",

                    "approval_status":
                        employer.approval_status,

                    "profile_completed":
                        employer.profile_completed,
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =================================================
        # VALIDATE JOB
        # =================================================

        serializer = JobSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            print(
                "JOB VALIDATION ERRORS:",
                serializer.errors
            )

            return Response(
                {
                    "message":
                        "Job validation failed.",

                    "errors":
                        serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =================================================
        # CREATE JOB
        # =================================================

        job = serializer.save(
            employer=employer
        )

        print(
            "JOB CREATED:",
            job.id
        )

        print(
            "DISABILITY ONLY JOB:",
            job.is_disability_job
        )

        # =================================================
        # SEND NEW JOB NOTIFICATIONS
        # =================================================

        try:

            notify_new_job_posted(
                job
            )

            print(
                "NEW JOB NOTIFICATIONS CREATED FOR JOB:",
                job.id
            )

        except Exception as e:

            print(
                "NEW JOB NOTIFICATION ERROR:",
                str(e)
            )

        # =================================================
        # RESPONSE
        # =================================================

        return Response(
            {
                "message":
                    "Job posted successfully.",

                "job":
                    JobSerializer(job).data,
            },
            status=status.HTTP_201_CREATED
        )


# =========================================================
# EMPLOYER DASHBOARD
# =========================================================

class EmployerDashboardView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        # =================================================
        # GET EMPLOYER PROFILE
        # =================================================

        try:

            employer = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =================================================
        # GET EMPLOYER JOBS
        # =================================================

        jobs = (
            Job.objects
            .filter(
                employer=employer
            )
            .order_by(
                "-created_at"
            )
        )

        # =================================================
        # JOB STATISTICS
        # =================================================

        total_jobs = jobs.count()

        live_jobs = jobs.filter(
            is_active=True
        ).count()

        closed_jobs = jobs.filter(
            is_active=False
        ).count()

        # =================================================
        # GET EMPLOYER APPLICATIONS
        #
        # IMPORTANT:
        # Only applications for this employer's jobs
        # are returned.
        # =================================================

        applications = (
            JobApplication.objects
            .filter(
                job__employer=employer
            )
            .select_related(
                "job"
            )
            .prefetch_related(
                "jobseeker"
            )
            .order_by(
                "-applied_at"
            )
        )

        # =================================================
        # APPLICATION COUNT
        #
        # Rejected applications are retained for history, but are
        # NOT included in the dashboard's applicant count.
        # =====================================================

        total_applicants = (
            applications
            .exclude(status__iexact="REJECTED")
            .count()
        )

        rejected_applicants = (
            applications
            .filter(status__iexact="REJECTED")
            .count()
        )

        # =================================================
        # PROFILE DATA
        # =================================================

        profile_data = EmployerProfileSerializer(
            employer
        ).data

        # =================================================
        # JOB DATA
        # =================================================

        jobs_data = JobSerializer(
            jobs,
            many=True
        ).data

        # =====================================================
        # PER-JOB ACTIVE APPLICANT COUNTS
        # =====================================================

        for job_data in jobs_data:
            job_id = job_data.get("id")

            if job_id is None:
                job_data["applicants_count"] = 0
                continue

            job_data["applicants_count"] = (
                JobApplication.objects
                .filter(job_id=job_id)
                .exclude(status__iexact="REJECTED")
                .count()
            )

        # =================================================
        # APPLICATION DATA
        # =================================================

        applications_data = (
            EmployerApplicantDetailSerializer(
                applications,
                many=True
            ).data
        )

        # =================================================
        # RESPONSE
        # =================================================

        return Response(
            {

                # =========================================
                # PROFILE
                # =========================================

                "profile":
                    profile_data,

                "employer_name":
                    employer.contact_name,

                "company_name":
                    employer.company_name,

                "email":
                    employer.company_email,

                # =========================================
                # STATISTICS
                # =========================================

                "stats": {

                    "total_jobs":
                        total_jobs,

                    "draft_jobs":
                        0,

                    "live_jobs":
                        live_jobs,

                    "active_jobs":
                        live_jobs,

                    "closed_jobs":
                        closed_jobs,

                    "total_applicants":
                        total_applicants,

                    "total_applications":
                        total_applicants,

                    "rejected_applicants":
                        rejected_applicants,
                },

                # =========================================
                # TOP-LEVEL STATISTICS
                #
                # These are included for frontend
                # compatibility.
                # =========================================

                "total_jobs":
                    total_jobs,

                "active_jobs":
                    live_jobs,

                "total_applications":
                    total_applicants,

                "rejected_applicants":
                    rejected_applicants,

                # =========================================
                # JOBS
                # =========================================

                "jobs":
                    jobs_data,

                "recent_jobs":
                    jobs_data[:5],

                # =========================================
                # APPLICATIONS
                #
                # THIS IS THE IMPORTANT FIX
                # =========================================

                "applications":
                    applications_data,

                "recent_applications":
                    applications_data[:5],
            },

            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER JOB APPLICANTS
# =========================================================

class EmployerApplicantsView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request,
        job_id
    ):

        # =====================================================
        # GET EMPLOYER PROFILE
        # =====================================================

        try:

            employer = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # GET JOB
        # =====================================================

        try:

            job = (
                Job.objects
                .select_related(
                    "employer"
                )
                .get(
                    id=job_id,
                    employer=employer
                )
            )

        except Job.DoesNotExist:

            return Response(
                {
                    "message":
                        "Job not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # GET APPLICATIONS
        # =====================================================

        applications = (
            JobApplication.objects
            .select_related(
                "job",
                "jobseeker",
                "jobseeker__user"
            )
            .filter(
                job=job
            )
            .order_by(
                "-applied_at"
            )
        )

        # =====================================================
        # BUILD APPLICANTS
        # =====================================================

        applicants = []

        for application in applications:

            applicant = application.jobseeker

            applicants.append({

                # =================================================
                # APPLICATION ID
                # =================================================

                "id":
                    application.id,

                "application_id":
                    application.id,

                # =================================================
                # JOB
                # =================================================

                "job_id":
                    job.id,

                "job_title":
                    job.title,

                # =================================================
                # APPLICATION
                # =================================================

                "status":
                    application.status,

                "applied_at":
                    application.applied_at,

                # =================================================
                # JOBSEEKER
                # =================================================

                "jobseeker": {

                    "id":
                        applicant.id,

                    "user_id":
                        applicant.user.id,

                    "full_name":
                        applicant.full_name or "",

                    "email":
                        applicant.user.email or "",

                    "phone":
                        applicant.phone or "",

                    "linkedin":
                        getattr(
                            applicant,
                            "linkedin",
                            ""
                        ) or "",

                    "headline":
                        applicant.headline or "",

                    "skills":
                        applicant.skills or "",

                    "location":
                        applicant.location or "",

                    # =================================================
                    # DISABILITY
                    # =================================================

                    "disability_type":
                        getattr(
                            applicant,
                            "disability_type",
                            ""
                        ) or "",

                    # =================================================
                    # PROFILE STATUS
                    # =================================================

                    "approval_status":
                        applicant.approval_status,

                    "profile_completed":
                        applicant.profile_completed,
                }
            })

        # =====================================================
        # RESPONSE
        # =====================================================

        # =====================================================
        # APPLICANT COUNTS
        #
        # Keep every application in `applicants`, including rejected
        # applicants, so the employer can still review their history.
        # `total_applicants` counts only non-rejected applications.
        # =====================================================

        active_applicants_count = (
            applications
            .exclude(status__iexact="REJECTED")
            .count()
        )

        rejected_applicants_count = (
            applications
            .filter(status__iexact="REJECTED")
            .count()
        )

        return Response(
            {
                "job": {

                    "id":
                        job.id,

                    "title":
                        job.title,

                    "company_name":
                        employer.company_name,
                },

                "total_applicants":
                    active_applicants_count,

                "active_applicants":
                    active_applicants_count,

                "rejected_applicants":
                    rejected_applicants_count,

                "all_applicants":
                    len(applicants),

                "applicants":
                    applicants,
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER VIEW CANDIDATE PROFILE
# =========================================================

class EmployerApplicantProfileView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request,
        application_id
    ):

        # =====================================================
        # GET EMPLOYER
        # =====================================================

        try:

            employer = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # GET APPLICATION
        # =====================================================

        try:

            application = (
                JobApplication.objects
                .select_related(
                    "job",
                    "job__employer",
                    "jobseeker",
                    "jobseeker__user",
                )
                .get(
                    id=application_id,
                    job__employer=employer
                )
            )

        except JobApplication.DoesNotExist:

            return Response(
                {
                    "message":
                        "Application not found or you do not "
                        "have permission to view this candidate."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # GET JOBSEEKER
        # =====================================================

        applicant = application.jobseeker

        # =====================================================
        # FILE URL HELPER
        # =====================================================

        def get_file_url(file_field):

            if not file_field:
                return None

            try:

                return request.build_absolute_uri(
                    file_field.url
                )

            except Exception:

                return None

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {

                "id":
                    applicant.id,

                "user_id":
                    applicant.user.id,

                "full_name":
                    applicant.full_name or "",

                "email":
                    applicant.user.email or "",

                "phone":
                    applicant.phone or "",

                "headline":
                    applicant.headline or "",

                "skills":
                    applicant.skills or "",

                "location":
                    applicant.location or "",

                "linkedin":
                    getattr(
                        applicant,
                        "linkedin",
                        ""
                    ) or "",

                "disability_type":
                    getattr(
                        applicant,
                        "disability_type",
                        ""
                    ) or "",

                "profile_completed":
                    applicant.profile_completed,

                "approval_status":
                    applicant.approval_status,

                # =================================================
                # DOCUMENTS
                # =================================================

                "documents": {

                    "profile_photo":
                        get_file_url(
                            applicant.profile_photo
                        ),

                    "resume":
                        get_file_url(
                            applicant.resume
                        ),

                    "aadhaar":
                        get_file_url(
                            applicant.aadhaar
                        ),
                },

                # =================================================
                # APPLICATION
                # =================================================

                "application": {

                    "id":
                        application.id,

                    "application_id":
                        application.id,

                    "status":
                        application.status,

                    "applied_at":
                        application.applied_at,

                    "job": {

                        "id":
                            application.job.id,

                        "title":
                            application.job.title,

                        "company_name":
                            employer.company_name,
                    }
                }
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER VIEW APPLICANT FULL PROFILE
# =========================================================

class EmployerApplicantDetailView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request,
        application_id
    ):

        # =====================================================
        # GET EMPLOYER PROFILE
        # =====================================================

        try:

            employer = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Employer profile not found."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # =====================================================
        # GET APPLICATION
        # ONLY THE EMPLOYER'S OWN JOB APPLICATION
        # =====================================================

        try:

            application = (
                JobApplication.objects
                .select_related(
                    "job",
                    "job__employer",
                    "jobseeker",
                    "jobseeker__user",
                )
                .prefetch_related(
                    "jobseeker__educations",
                    "jobseeker__experiences",
                    "jobseeker__projects",
                )
                .get(
                    id=application_id,
                    job__employer=employer,
                )
            )

        except JobApplication.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Application not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # =====================================================
        # SERIALIZE COMPLETE JOBSEEKER
        # =====================================================

        serializer = EmployerApplicantDetailSerializer(
            application,
            context={
                "request": request
            }
        )

        jobseeker_data = serializer.data.get(
            "jobseeker",
            {}
        )

        # =====================================================
        # COMPLETE APPLICATION DATA
        # =====================================================

        job = application.job

        application_data = {
            "id": application.id,

            "application_id":
                application.id,

            "status":
                application.status,

            "applied_at":
                application.applied_at,

            "job": {

                "id":
                    job.id,

                "title":
                    job.title,

                "company_name": (
                    job.employer.company_name
                    if job.employer
                    else ""
                ),

                "description": getattr(
                    job,
                    "description",
                    ""
                ),

                "location": getattr(
                    job,
                    "location",
                    ""
                ),

                "job_type": getattr(
                    job,
                    "job_type",
                    ""
                ),

                "job_type_display": (
                    job.get_job_type_display()
                    if hasattr(
                        job,
                        "get_job_type_display"
                    )
                    else ""
                ),

                "work_mode": getattr(
                    job,
                    "work_mode",
                    ""
                ),

                "work_mode_display": (
                    job.get_work_mode_display()
                    if hasattr(
                        job,
                        "get_work_mode_display"
                    )
                    else ""
                ),

                # =================================================
                # DISABILITY-ONLY JOB
                # =================================================

                "is_disability_job":
                    getattr(
                        job,
                        "is_disability_job",
                        False
                    ),

                "experience": getattr(
                    job,
                    "experience",
                    ""
                ),

                "experience_display": (
                    job.get_experience_display()
                    if hasattr(
                        job,
                        "get_experience_display"
                    )
                    else ""
                ),

                "minimum_experience": getattr(
                    job,
                    "minimum_experience",
                    None
                ),

                "maximum_experience": getattr(
                    job,
                    "maximum_experience",
                    None
                ),

                "education_details": getattr(
                    job,
                    "education_details",
                    ""
                ),

                "roles_responsibilities": getattr(
                    job,
                    "roles_responsibilities",
                    ""
                ),

                "key_features": getattr(
                    job,
                    "key_features",
                    ""
                ),

                "salary_min": getattr(
                    job,
                    "salary_min",
                    None
                ),

                "salary_max": getattr(
                    job,
                    "salary_max",
                    None
                ),

                "skills": getattr(
                    job,
                    "skills",
                    ""
                ),
            },
        }

        # =====================================================
        # FINAL RESPONSE
        # =====================================================

        return Response(
            {
                "application":
                    application_data,

                "jobseeker":
                    jobseeker_data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# EMPLOYER UPDATE APPLICANT STATUS
# =========================================================

class EmployerApplicationStatusView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    @transaction.atomic
    def patch(self, request, application_id):

        # =====================================================
        # GET EMPLOYER PROFILE
        # =====================================================

        try:
            employer = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # GET SELECTED APPLICATION
        # =====================================================

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
                    id=application_id,
                    job__employer=employer,
                )
            )

        except JobApplication.DoesNotExist:

            return Response(
                {
                    "message":
                        "Application not found or you do not "
                        "have permission to update this application."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # CURRENT STATUS
        # =====================================================

        current_status = (
            application.status or "APPLIED"
        ).strip().upper()

        # =====================================================
        # NEW STATUS
        # =====================================================

        new_status = (
            request.data.get("status") or ""
        ).strip().upper()

        allowed_statuses = [
            "APPLIED",
            "UNDER REVIEW",
            "SHORTLISTED",
            "INTERVIEW SCHEDULED",
            "REJECTED",
            "HIRED",
        ]

        if new_status not in allowed_statuses:

            return Response(
                {
                    "message": "Invalid application status.",
                    "allowed_statuses": allowed_statuses,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # BASIC DATA
        # =====================================================

        jobseeker = application.jobseeker
        candidate_user = jobseeker.user

        selected_job = application.job
        selected_employer = selected_job.employer

        company_name = (
            selected_employer.company_name
            or "the company"
        )

        job_title = (
            selected_job.title
            or "the selected position"
        )

        # =====================================================
        # REJECTED IS FINAL
        # =====================================================

        if current_status == "REJECTED":

            return Response(
                {
                    "message":
                        "Application is already REJECTED. "
                        "Its status cannot be changed.",

                    "application_id":
                        application.id,

                    "status":
                        current_status,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # IMPORTANT:
        #
        # DIRECTLY FIND SAME CANDIDATE + SAME COMPANY
        #
        # We DO NOT use job ID here.
        #
        # Example:
        #
        # Candidate = Parameswari
        #
        # Company A:
        #   Job 1 -> Hired
        #   Job 2 -> Under Review
        #   Job 3 -> Shortlisted
        #
        # Company B:
        #   Job 4 -> Applied
        #
        # When Company A hires Job 1:
        #
        # Job 1 -> HIRED
        # Job 2 -> REJECTED
        # Job 3 -> REJECTED
        # Job 4 -> UNCHANGED
        #
        # =====================================================

        same_company_apps = (
            JobApplication.objects
            .select_for_update()
            .select_related(
                "job",
                "job__employer",
                "jobseeker",
                "jobseeker__user",
            )
            .filter(
                jobseeker_id=application.jobseeker_id,
                job__employer_id=application.job.employer_id,
            )
            .exclude(
                id=application.id
            )
        )

        # =====================================================
        # ALREADY HIRED -> SYNCHRONIZE OLD DATA
        # =====================================================

        if (
            current_status == "HIRED"
            and new_status == "HIRED"
        ):

            same_company_rejected = 0
            rejected_application_ids = []

            for other_application in same_company_apps:

                other_status = (
                    other_application.status or ""
                ).strip().upper()

                # Already rejected -> leave unchanged
                if other_status == "REJECTED":
                    continue

                # Another hired application -> leave unchanged
                if other_status == "HIRED":
                    continue

                # =================================================
                # SAME CANDIDATE + SAME COMPANY
                # =================================================

                other_application.status = "REJECTED"

                other_application.save(
                    update_fields=["status"]
                )

                same_company_rejected += 1

                rejected_application_ids.append(
                    other_application.id
                )

            print(
                "\n========================================"
            )
            print(
                "HIRED APPLICATION SYNCHRONIZATION"
            )
            print(
                "========================================"
            )
            print(
                "Candidate:",
                jobseeker.full_name
            )
            print(
                "Candidate User ID:",
                candidate_user.id
            )
            print(
                "Hired Application ID:",
                application.id
            )
            print(
                "Employer Profile ID:",
                selected_employer.id
            )
            print(
                "Company:",
                company_name
            )
            print(
                "Same Company Rejected:",
                same_company_rejected
            )
            print(
                "Rejected Application IDs:",
                rejected_application_ids
            )
            print(
                "========================================\n"
            )

            return Response(
                {
                    "message":
                        "Application is already HIRED. "
                        "Same candidate's other applications "
                        "with the same company were synchronized.",

                    "application_id":
                        application.id,

                    "status":
                        "HIRED",

                    "already_hired":
                        True,

                    "same_company_rejected":
                        same_company_rejected,

                    "rejected_application_ids":
                        rejected_application_ids,

                    "notifications_sent":
                        False,
                },
                status=status.HTTP_200_OK
            )

        # =====================================================
        # NORMAL STATUS UPDATE
        #
        # APPLIED
        # UNDER REVIEW
        # SHORTLISTED
        # INTERVIEW SCHEDULED
        # REJECTED
        # =====================================================

        if new_status != "HIRED":

            application.status = new_status

            application.save(
                update_fields=["status"]
            )

            return Response(
                {
                    "message":
                        "Application status updated successfully.",

                    "application_id":
                        application.id,

                    "previous_status":
                        current_status,

                    "status":
                        application.status,
                },
                status=status.HTTP_200_OK
            )

        # =====================================================
        # HIRED WORKFLOW
        # =====================================================

        # =====================================================
        # CHECK WHETHER CANDIDATE IS ALREADY HIRED
        # SOMEWHERE ELSE
        # =====================================================

        already_hired = (
            JobApplication.objects
            .select_for_update()
            .select_related(
                "job",
                "job__employer",
            )
            .filter(
                jobseeker_id=application.jobseeker_id,
                status="HIRED",
            )
            .exclude(
                id=application.id
            )
            .first()
        )

        if already_hired:

            existing_company = "another company"

            if (
                already_hired.job
                and already_hired.job.employer
            ):

                existing_company = (
                    already_hired.job.employer.company_name
                    or "another company"
                )

            return Response(
                {
                    "message":
                        "This candidate has already been "
                        f"hired by {existing_company}.",

                    "application_id":
                        application.id,

                    "status":
                        current_status,
                },
                status=status.HTTP_409_CONFLICT
            )

        # =====================================================
        # SELECTED APPLICATION -> HIRED
        # =====================================================

        application.status = "HIRED"

        application.save(
            update_fields=["status"]
        )

        # =====================================================
        # REJECT SAME CANDIDATE'S OTHER APPLICATIONS
        # FOR THE SAME COMPANY
        #
        # IMPORTANT:
        #
        # same_company_apps was selected using:
        #
        # jobseeker_id = candidate
        # job__employer_id = current company
        #
        # Therefore OTHER COMPANIES ARE NEVER TOUCHED.
        # =====================================================

        same_company_rejected = 0
        rejected_application_ids = []

        for other_application in same_company_apps:

            other_status = (
                other_application.status or ""
            ).strip().upper()

            # Never change another hired application
            if other_status == "HIRED":
                continue

            # Already rejected
            if other_status == "REJECTED":
                continue

            # =================================================
            # REJECT
            # =================================================

            other_application.status = "REJECTED"

            other_application.save(
                update_fields=["status"]
            )

            same_company_rejected += 1

            rejected_application_ids.append(
                other_application.id
            )

            print(
                "SAME COMPANY APPLICATION REJECTED:",
                other_application.id
            )

        # =====================================================
        # FIND OTHER COMPANIES WHERE THIS CANDIDATE APPLIED
        # =====================================================

        other_company_employers = {}

        other_company_apps = (
            JobApplication.objects
            .select_related(
                "job",
                "job__employer",
            )
            .filter(
                jobseeker_id=application.jobseeker_id
            )
            .exclude(
                job__employer_id=selected_employer.id
            )
        )

        for other_application in other_company_apps:

            if not other_application.job:
                continue

            other_employer = (
                other_application.job.employer
            )

            if not other_employer:
                continue

            employer_user = getattr(
                other_employer,
                "user",
                None
            )

            if employer_user:

                other_company_employers[
                    employer_user.id
                ] = other_employer

        # =====================================================
        # JOBSEEKER HIRED NOTIFICATION
        # =====================================================

        Notification.objects.create(

            recipient=candidate_user,

            title="🎉 Congratulations! You Are Hired",

            message=(
                "🎉 Congratulations!\n\n"

                f"You have been hired by "
                f"{company_name} for the position "
                f"'{job_title}'.\n\n"

                "Your other applications with "
                "the same company have been "
                "automatically rejected.\n\n"

                "If you do not accept this hiring "
                "decision, please use Help & Support "
                "and contact a JobConnect admin."
            ),

            notification_type="JOB",
        )

        # =====================================================
        # JOBSEEKER PROFILE UPDATE NOTIFICATION
        # =====================================================

        Notification.objects.create(

            recipient=candidate_user,

            title="Update Your JobConnect Profile",

            message=(
                f"Your hiring by {company_name} "
                f"for '{job_title}' has been recorded.\n\n"

                "Please update your JobConnect profile "
                "with your latest employment information "
                "so your profile remains current.\n\n"

                "Recommended updates:\n"
                "• Current employment\n"
                "• Job title / position\n"
                "• Skills\n"
                "• Experience\n"
                "• Professional summary\n\n"

                "Please open your Profile page and "
                "keep your information up to date."
            ),

            notification_type="PROFILE",
        )

        # =====================================================
        # NOTIFY OTHER COMPANIES
        #
        # Their applications remain unchanged.
        # =====================================================

        other_employer_notifications = []

        for other_employer in other_company_employers.values():

            other_employer_notifications.append(

                Notification(

                    recipient=other_employer.user,

                    title="Candidate Hiring Update",

                    message=(
                        "A candidate who applied to "
                        "your company has been hired "
                        "by another company.\n\n"

                        f"Candidate: "
                        f"{jobseeker.full_name}\n"

                        f"Hired Company: "
                        f"{company_name}\n"

                        f"Hired Position: "
                        f"{job_title}\n\n"

                        "The candidate's application "
                        "with your company has NOT "
                        "been changed.\n\n"

                        "You may continue reviewing "
                        "the application according to "
                        "your normal hiring process."
                    ),

                    notification_type="JOB",
                )
            )

        if other_employer_notifications:

            Notification.objects.bulk_create(
                other_employer_notifications
            )

        # =====================================================
        # ADMIN NOTIFICATIONS
        # =====================================================

        admin_users = (
            User.objects
            .filter(
                is_staff=True,
                is_active=True,
            )
        )

        admin_notifications = []

        for admin_user in admin_users:

            admin_notifications.append(

                Notification(

                    recipient=admin_user,

                    title="Candidate Hired",

                    message=(
                        "A jobseeker has been hired.\n\n"

                        f"Candidate: "
                        f"{jobseeker.full_name}\n"

                        f"Candidate Email: "
                        f"{candidate_user.email}\n\n"

                        f"Company: "
                        f"{company_name}\n"

                        f"Position: "
                        f"{job_title}\n"

                        f"Application ID: "
                        f"{application.id}\n\n"

                        "Other applications with "
                        "the same company: "
                        f"{same_company_rejected} "
                        "automatically rejected."
                    ),

                    notification_type="JOB",
                )
            )

        if admin_notifications:

            Notification.objects.bulk_create(
                admin_notifications
            )

        # =====================================================
        # FINAL RESPONSE
        # =====================================================

        return Response(
            {
                "message":
                    "Application marked as HIRED successfully.",

                "application_id":
                    application.id,

                "previous_status":
                    current_status,

                "status":
                    "HIRED",

                "hired_company":
                    company_name,

                "hired_job":
                    job_title,

                "same_company_rejected":
                    same_company_rejected,

                "rejected_application_ids":
                    rejected_application_ids,

                "other_company_applications_changed":
                    False,

                "other_company_employers_notified":
                    len(
                        other_company_employers
                    ),

                "jobseeker_profile_update_notification":
                    True,

                "admin_notified":
                    bool(
                        admin_notifications
                    ),
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER CLOSE JOB
# =========================================================

class EmployerCloseJobView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def patch(
        self,
        request,
        job_id
    ):

        print("\n========================================")
        print("EMPLOYER CLOSE JOB")
        print("========================================")

        print(
            "USER:",
            request.user
        )

        print(
            "JOB ID:",
            job_id
        )

        print("========================================\n")

        # =====================================================
        # GET EMPLOYER PROFILE
        # =====================================================

        try:

            employer = request.user.employer_profile

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # GET JOB
        # =====================================================

        try:

            job = Job.objects.get(
                id=job_id,
                employer=employer
            )

        except Job.DoesNotExist:

            return Response(
                {
                    "message":
                        "Job not found or you do not have "
                        "permission to close this job."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # ALREADY CLOSED
        # =====================================================

        if not job.is_active:

            return Response(
                {
                    "message":
                        "This job is already closed.",

                    "job_id":
                        job.id,

                    "is_active":
                        False,

                    "status":
                        "closed",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # CLOSE JOB
        # =====================================================

        job.is_active = False

        job.save(
            update_fields=[
                "is_active"
            ]
        )

        print(
            "JOB CLOSED:",
            job.id
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "message":
                    "Job closed successfully.",

                "job_id":
                    job.id,

                "job_title":
                    job.title,

                "is_active":
                    job.is_active,

                "status":
                    "closed",
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER NOTIFICATION LIST
# =========================================================

class EmployerNotificationListView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        notifications = (
            Notification.objects
            .filter(
                recipient=request.user
            )
            .order_by(
                "-created_at"
            )
        )

        unread_count = notifications.filter(
            is_read=False
        ).count()

        data = []

        for notification in notifications:

            data.append({

                "id":
                    notification.id,

                "title":
                    notification.title,

                "message":
                    notification.message,

                "notification_type":
                    notification.notification_type,

                "notification_type_display":
                    notification.get_notification_type_display(),

                "is_read":
                    notification.is_read,

                "created_at":
                    notification.created_at,
            })

        return Response(
            {
                "notifications":
                    data,

                "unread_count":
                    unread_count,
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER MARK ONE NOTIFICATION AS READ
# =========================================================

class EmployerNotificationReadView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def post(
        self,
        request,
        notification_id
    ):

        try:

            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )

        except Notification.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Notification not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        notification.is_read = True

        notification.save(
            update_fields=[
                "is_read"
            ]
        )

        return Response(
            {
                "message":
                    "Notification marked as read.",

                "id":
                    notification.id,

                "is_read":
                    notification.is_read,
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER MARK ALL NOTIFICATIONS AS READ
# =========================================================

class EmployerMarkAllNotificationsReadView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def post(self, request):

        print("\n========================================")
        print("EMPLOYER MARK ALL NOTIFICATIONS READ")
        print("========================================")

        print(
            "USER:",
            request.user
        )

        print(
            "USER ID:",
            request.user.id
        )

        print(
            "AUTHENTICATED:",
            request.user.is_authenticated
        )

        # =====================================================
        # UPDATE ONLY THIS EMPLOYER'S NOTIFICATIONS
        # =====================================================

        updated_count = (
            Notification.objects
            .filter(
                recipient=request.user,
                is_read=False
            )
            .update(
                is_read=True
            )
        )

        print(
            "UPDATED NOTIFICATIONS:",
            updated_count
        )

        print(
            "========================================\n"
        )

        return Response(
            {
                "message":
                    "All notifications marked as read.",

                "updated_count":
                    updated_count,
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EMPLOYER DELETE NOTIFICATION
# =========================================================

class EmployerNotificationDeleteView(APIView):

    authentication_classes = [
        JWTAuthentication
    ]

    permission_classes = [
        IsAuthenticated
    ]

    def delete(
        self,
        request,
        notification_id
    ):

        try:

            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )

        except Notification.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Notification not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        notification.delete()

        return Response(
            {
                "message":
                    "Notification deleted successfully."
            },
            status=status.HTTP_200_OK
        )