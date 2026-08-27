from django.contrib.auth.models import User
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .permissions import IsAdminUserRole

from datetime import timedelta
from secrets import randbelow

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken

from adminpanel.models import PasswordResetOTP
from jobseeker.models import JobSeekerProfile
from employer.models import EmployerProfile
from adminpanel.serializers import AdminJobSeekerSerializer

from jobconnect.authentication import authenticate_by_email
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# =========================================================
# COMMON LOGIN
# Email/Password + Google Login
# =========================================================

class CommonLoginView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        # =====================================================
        # GOOGLE LOGIN
        # =====================================================

        google_token = request.data.get(
            "google_token"
        )

        if google_token:

            return self.google_login(
                google_token
            )

        # =====================================================
        # GET LOGIN DATA
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

        email = request.data.get(
            "email",
            ""
        )

        password = request.data.get(
            "password",
            ""
        )

        email = email.strip().lower()

        # =====================================================
        # VALIDATION
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

        if not email or not password:

            return Response(
                {
                    "detail":
                        "Email and password are required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # FIND USER BY EMAIL
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

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

        # =====================================================
        # AUTHENTICATE PASSWORD
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

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

        # =====================================================
        # DETERMINE ROLE
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

        role = None

        name = (
            user.get_full_name()
            or user.username
            or user.email
        )

        approval_status = None

        profile_completed = False

        company_name = None

        # =====================================================
        # ADMIN
        # =====================================================

        if user.is_superuser or user.is_staff:

            role = "admin"

            name = (
                user.get_full_name()
                or user.username
                or "Admin"
            )

            approval_status = "approved"

            profile_completed = True

        # =====================================================
        # EMPLOYER
        # =====================================================

        elif hasattr(
            user,
            "employer_profile"
        ):

            profile = user.employer_profile

            role = "employer"

            name = (
                profile.contact_name
                or profile.company_name
                or user.username
            )

            company_name = (
                profile.company_name
                or ""
            )

            approval_status = (
                profile.approval_status
            )

            profile_completed = (
                profile.profile_completed
            )

        # =====================================================
        # JOB SEEKER
        # =====================================================

        elif hasattr(
            user,
            "jobseeker_profile"
        ):

            profile = user.jobseeker_profile

            role = "jobseeker"

            name = (
                profile.full_name
                or user.username
            )

            approval_status = (
                profile.approval_status
            )

            profile_completed = (
                profile.profile_completed
            )

        # =====================================================
        # UNKNOWN USER
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

        else:

            return Response(
                {
                    "detail":
                        "User role could not be determined."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =====================================================
        # JWT
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

        refresh = RefreshToken.for_user(
            user
        )

        access_token = str(
            refresh.access_token
        )

        refresh_token = str(
            refresh
        )

        # =====================================================
        # USER RESPONSE
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

        user_data = {

            "id":
                user.id,

            "name":
                name,

            "username":
                user.username,

            "email":
                user.email,

            "role":
                role,

            "approval_status":
                approval_status,

            "profile_completed":
                profile_completed,
        }

        # =====================================================
        # EMPLOYER COMPANY NAME
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

        if role == "employer":

            user_data["company_name"] = (
                company_name
            )

        # =====================================================
        # RESPONSE
        # EXISTING FUNCTIONALITY - UNCHANGED
        # =====================================================

        return Response(
            {
                "message":
                    "Login successful.",

                "access":
                    access_token,

                "refresh":
                    refresh_token,

                "user":
                    user_data,
            },
            status=status.HTTP_200_OK
        )

    # =========================================================
    # GOOGLE LOGIN
    # NEW FUNCTIONALITY ONLY
    # =========================================================

    def google_login(
        self,
        google_token
    ):

        # =====================================================
        # GOOGLE CLIENT ID
        # =====================================================

        google_client_id = getattr(
            settings,
            "GOOGLE_CLIENT_ID",
            None
        )

        if not google_client_id:

            return Response(
                {
                    "detail":
                        "Google OAuth is not configured on the server."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # =====================================================
        # VERIFY GOOGLE ID TOKEN
        # =====================================================

        try:

            google_user = (
                id_token.verify_oauth2_token(
                    google_token,
                    google_requests.Request(),
                    google_client_id
                )
            )

        except ValueError:

            return Response(
                {
                    "detail":
                        "Invalid or expired Google token."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        except Exception as exc:

            print(
                "GOOGLE TOKEN ERROR:",
                exc
            )

            return Response(
                {
                    "detail":
                        "Unable to verify Google account."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # =====================================================
        # GOOGLE EMAIL
        # =====================================================

        google_email = google_user.get(
            "email"
        )

        email_verified = google_user.get(
            "email_verified",
            False
        )

        if not google_email:

            return Response(
                {
                    "detail":
                        "Google email address was not received."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # CHECK VERIFIED EMAIL
        # =====================================================

        if not email_verified:

            return Response(
                {
                    "detail":
                        "Your Google email address is not verified."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        google_email = (
            google_email
            .strip()
            .lower()
        )

        # =====================================================
        # FIND EXISTING JOB CONNECT USER
        # =====================================================

        try:

            user = User.objects.get(
                email__iexact=google_email
            )

        except User.DoesNotExist:

            return Response(
                {
                    "detail":
                        "No Job Connect account exists with this Google email. Please create an account first."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # DETERMINE ROLE
        # SAME EXISTING LOGIC
        # =====================================================

        role = None

        name = (
            user.get_full_name()
            or user.username
            or user.email
        )

        approval_status = None

        profile_completed = False

        company_name = None

        # =====================================================
        # ADMIN
        # =====================================================

        if user.is_superuser or user.is_staff:

            role = "admin"

            name = (
                user.get_full_name()
                or user.username
                or "Admin"
            )

            approval_status = "approved"

            profile_completed = True

        # =====================================================
        # EMPLOYER
        # =====================================================

        elif hasattr(
            user,
            "employer_profile"
        ):

            profile = user.employer_profile

            role = "employer"

            name = (
                profile.contact_name
                or profile.company_name
                or user.username
            )

            company_name = (
                profile.company_name
                or ""
            )

            approval_status = (
                profile.approval_status
            )

            profile_completed = (
                profile.profile_completed
            )

        # =====================================================
        # JOB SEEKER
        # =====================================================

        elif hasattr(
            user,
            "jobseeker_profile"
        ):

            profile = user.jobseeker_profile

            role = "jobseeker"

            name = (
                profile.full_name
                or user.username
            )

            approval_status = (
                profile.approval_status
            )

            profile_completed = (
                profile.profile_completed
            )

        # =====================================================
        # UNKNOWN USER
        # =====================================================

        else:

            return Response(
                {
                    "detail":
                        "User role could not be determined."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =====================================================
        # CREATE JWT
        # =====================================================

        refresh = RefreshToken.for_user(
            user
        )

        access_token = str(
            refresh.access_token
        )

        refresh_token = str(
            refresh
        )

        # =====================================================
        # USER DATA
        # =====================================================

        user_data = {

            "id":
                user.id,

            "name":
                name,

            "username":
                user.username,

            "email":
                user.email,

            "role":
                role,

            "approval_status":
                approval_status,

            "profile_completed":
                profile_completed,
        }

        # =====================================================
        # EMPLOYER COMPANY
        # =====================================================

        if role == "employer":

            user_data["company_name"] = (
                company_name
            )

        # =====================================================
        # GOOGLE LOGIN RESPONSE
        # SAME JWT FORMAT AS NORMAL LOGIN
        # =====================================================

        return Response(
            {
                "message":
                    "Google login successful.",

                "access":
                    access_token,

                "refresh":
                    refresh_token,

                "user":
                    user_data,
            },
            status=status.HTTP_200_OK
        )

# =========================================================
# FORGOT PASSWORD - SEND OTP
# =========================================================
@method_decorator(csrf_exempt, name="dispatch")
class ForgotPasswordView(APIView):

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email", "")

        email = email.strip().lower()

        # =====================================================
        # VALIDATION
        # =====================================================

        if not email:

            return Response(
                {
                    "detail":
                        "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # FIND USER
        # =====================================================

        try:

            user = User.objects.get(
                email__iexact=email
            )

        except User.DoesNotExist:

            return Response(
                {
                    "detail":
                        "No account found with this email address."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # DETERMINE ROLE
        # =====================================================

        role = None

        # JOB SEEKER

        try:

            user.jobseeker_profile

            role = "jobseeker"

        except JobSeekerProfile.DoesNotExist:

            pass

        # EMPLOYER

        if role is None:

            try:

                user.employer_profile

                role = "employer"

            except EmployerProfile.DoesNotExist:

                pass

        # =====================================================
        # NO PROFILE
        # =====================================================

        if role is None:

            return Response(
                {
                    "detail":
                        "No job seeker or employer account "
                        "is associated with this email."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # DELETE OLD OTP
        # =====================================================

        PasswordResetOTP.objects.filter(
            user=user
        ).delete()

        # =====================================================
        # GENERATE OTP
        # =====================================================

        otp = str(
            100000 + randbelow(900000)
        )

        # =====================================================
        # CREATE OTP
        # =====================================================

        PasswordResetOTP.objects.create(

            user=user,

            otp=otp,

            expires_at=timezone.now()
            + timedelta(minutes=10),

            is_verified=False,
        )

        # =====================================================
        # EMAIL
        # =====================================================

        send_mail(

            "JobConnect Password Reset OTP",

            f"""
Hello,

Your JobConnect password reset OTP is:

{otp}

This OTP is valid for 10 minutes.

If you did not request a password reset,
please ignore this email.

Thank you,
JobConnect
""",

            settings.DEFAULT_FROM_EMAIL,

            [email],

            fail_silently=False,
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "message":
                    "OTP has been sent to your registered email.",

                "email":
                    email,

                "role":
                    role,
            },
            status=status.HTTP_200_OK
        )
    
# =========================================================
# VERIFY OTP
# =========================================================
@method_decorator(csrf_exempt, name="dispatch")
class VerifyOTPView(APIView):

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email", "")
        otp = request.data.get("otp", "")

        email = email.strip().lower()
        otp = str(otp).strip()

        # =====================================================
        # VALIDATION
        # =====================================================

        if not email:

            return Response(
                {
                    "detail":
                        "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not otp:

            return Response(
                {
                    "detail":
                        "OTP is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # FIND USER
        # =====================================================

        try:

            user = User.objects.get(
                email__iexact=email
            )

        except User.DoesNotExist:

            return Response(
                {
                    "detail":
                        "No account found with this email address."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # FIND OTP
        # =====================================================

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

        # =====================================================
        # CHECK EXPIRY
        # =====================================================

        if reset_otp.is_expired():

            reset_otp.delete()

            return Response(
                {
                    "detail":
                        "OTP has expired. Please request a new OTP."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # VERIFY
        # =====================================================

        reset_otp.is_verified = True

        reset_otp.save(
            update_fields=[
                "is_verified"
            ]
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "message":
                    "OTP verified successfully.",

                "email":
                    email,

                "verified":
                    True,
            },
            status=status.HTTP_200_OK
        )
    

# =========================================================
# RESET PASSWORD
# =========================================================
@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordView(APIView):

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        print("======================================")
        print("RESET PASSWORD REQUEST DATA:")
        print(request.data)
        print("======================================")


        email = request.data.get("email", "")
        otp = request.data.get("otp", "")
        new_password = request.data.get(
            "new_password",
            ""
        )
        confirm_password = request.data.get(
            "confirm_password",
            ""
        )

        email = email.strip().lower()
        otp = str(otp).strip()

        # =====================================================
        # VALIDATION
        # =====================================================

        if not email:

            return Response(
                {
                    "detail":
                        "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not otp:

            return Response(
                {
                    "detail":
                        "OTP is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not new_password:

            return Response(
                {
                    "detail":
                        "New password is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not confirm_password:

            return Response(
                {
                    "detail":
                        "Confirm password is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # PASSWORD MATCH
        # =====================================================

        if new_password != confirm_password:

            return Response(
                {
                    "detail":
                        "Passwords do not match."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # FIND USER
        # =====================================================

        try:

            user = User.objects.get(
                email__iexact=email
            )

        except User.DoesNotExist:

            return Response(
                {
                    "detail":
                        "No account found with this email address."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # FIND VERIFIED OTP
        # =====================================================

        try:

            reset_otp = (
                PasswordResetOTP.objects
                .filter(
                    user=user,
                    otp=otp,
                    is_verified=True
                )
                .latest("created_at")
            )

        except PasswordResetOTP.DoesNotExist:

            return Response(
                {
                    "detail":
                        "Please verify the OTP first."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # CHECK EXPIRY
        # =====================================================

        if reset_otp.is_expired():

            reset_otp.delete()

            return Response(
                {
                    "detail":
                        "OTP verification has expired. "
                        "Please request a new OTP."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # VALIDATE PASSWORD
        # =====================================================

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

        # =====================================================
        # SET PASSWORD
        # =====================================================

        user.set_password(
            new_password
        )

        user.save(
            update_fields=[
                "password"
            ]
        )

        # =====================================================
        # DELETE OTP
        # =====================================================

        reset_otp.delete()

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "message":
                    "Password reset successfully. "
                    "You can now login."
            },
            status=status.HTTP_200_OK
        )

class AdminDashboardView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def get(self, request):

        # =====================================================
        # JOB SEEKERS
        # =====================================================

        # Only APPROVED job seekers
        total_jobseekers = (
            JobSeekerProfile.objects
            .filter(
                approval_status="approved"
            )
            .count()
        )

        # Pending job seekers
        pending_jobseekers = (
            JobSeekerProfile.objects
            .filter(
                approval_status="pending",
                profile_completed=True
            )
            .count()
        )

        # Approved job seekers
        approved_jobseekers = (
            JobSeekerProfile.objects
            .filter(
                approval_status="approved"
            )
            .count()
        )

        # Rejected job seekers
        rejected_jobseekers = (
            JobSeekerProfile.objects
            .filter(
                approval_status="rejected"
            )
            .count()
        )

        # =====================================================
        # EMPLOYERS
        # =====================================================

        # Only APPROVED employers
        total_employers = (
            EmployerProfile.objects
            .filter(
                approval_status="approved"
            )
            .count()
        )

        # Pending employers
        pending_employers = (
            EmployerProfile.objects
            .filter(
                approval_status="pending"
            )
            .count()
        )

        # Approved employers
        approved_employers = (
            EmployerProfile.objects
            .filter(
                approval_status="approved"
            )
            .count()
        )

        # Rejected employers
        rejected_employers = (
            EmployerProfile.objects
            .filter(
                approval_status="rejected"
            )
            .count()
        )

        # =====================================================
        # TOTAL PENDING VERIFICATIONS
        # =====================================================

        pending_verifications = (
            pending_jobseekers +
            pending_employers
        )

        # =====================================================
        # TOTAL NON-ADMIN USERS
        # =====================================================

        total_users = (
            User.objects
            .filter(
                is_staff=False,
                is_superuser=False
            )
            .count()
        )

        # =====================================================
        # APPROVED ACCOUNTS
        # =====================================================

        approved_accounts = (
            approved_jobseekers +
            approved_employers
        )

        # =====================================================
        # REJECTED ACCOUNTS
        # =====================================================

        rejected_accounts = (
            rejected_jobseekers +
            rejected_employers
        )

        # =====================================================
        # LIVE JOB POSTS
        # =====================================================

        # Change this later when Job model is connected
        live_job_posts = 0

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                # -------------------------------------------------
                # VERIFICATION
                # -------------------------------------------------

                "pending_verifications":
                    pending_verifications,

                "pending_jobseekers":
                    pending_jobseekers,

                "pending_employers":
                    pending_employers,

                # -------------------------------------------------
                # USERS
                # -------------------------------------------------

                "total_users":
                    total_users,

                # -------------------------------------------------
                # APPROVED JOB SEEKERS / EMPLOYERS
                # -------------------------------------------------

                "total_jobseekers":
                    total_jobseekers,

                "total_employers":
                    total_employers,

                "approved_jobseekers":
                    approved_jobseekers,

                "approved_employers":
                    approved_employers,

                # -------------------------------------------------
                # REJECTED
                # -------------------------------------------------

                "rejected_jobseekers":
                    rejected_jobseekers,

                "rejected_employers":
                    rejected_employers,

                "approved_accounts":
                    approved_accounts,

                "rejected_accounts":
                    rejected_accounts,

                # -------------------------------------------------
                # JOBS
                # -------------------------------------------------

                "live_job_posts":
                    live_job_posts,
            },
            status=status.HTTP_200_OK
        )
# =========================================================
# ADMIN - VERIFICATION QUEUE
# =========================================================

class AdminVerificationQueueView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def get(self, request):

        submissions = []

        # =====================================================
        # JOB SEEKERS
        # =====================================================

        jobseekers = (
            JobSeekerProfile.objects.filter(
                profile_completed=True,
                approval_status="pending")
            .select_related("user")
            .order_by("-created_at")
        )

        for profile in jobseekers:

            submissions.append(
                {
                    "id": profile.id,

                    "type": "job seeker",

                    "name": profile.full_name,

                    "email": profile.user.email,

                    "location": profile.location or "",

                    "submitted": profile.created_at,

                    "approval_status":
                        profile.approval_status,

                    "profile_completed":
                        profile.profile_completed,
                }
            )

        # =====================================================
        # EMPLOYERS
        # =====================================================

        employers = (
            EmployerProfile.objects
            .filter(
                profile_completed=True,
                approval_status="pending"
            )
            .select_related("user")
            .order_by("-created_at")
        )

        for profile in employers:

            submissions.append(
                {
                    "id": profile.id,

                    "type": "employer",

                    "name": profile.company_name,

                    "email": profile.user.email,

                    "location": getattr(
                        profile,
                        "location",
                        ""
                    ),

                    "submitted": profile.created_at,

                    "approval_status":
                        profile.approval_status,
                }
            )

        # =====================================================
        # SORT
        # =====================================================

        submissions.sort(
            key=lambda item: item["submitted"],
            reverse=True
        )

        return Response(
            submissions,
            status=status.HTTP_200_OK
        )

# =========================================================
# ADMIN - JOB SEEKER LIST
# =========================================================

class AdminJobSeekerListView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def get(self, request):

        jobseekers = (
            JobSeekerProfile.objects
            .filter(
                approval_status="pending",
                profile_completed=True
            )
            .select_related("user")
            .prefetch_related(
                "educations",
                "experiences",
                "projects"
            )
            .order_by("-created_at")
        )

        serializer = AdminJobSeekerSerializer(
            jobseekers,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


# =========================================================
# ADMIN - JOB SEEKER PROFILE
# =========================================================

class AdminJobSeekerProfileView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def get(self, request, pk):

        try:

            profile = (
                JobSeekerProfile.objects
                .select_related("user")
                .prefetch_related(
                    "educations",
                    "experiences",
                    "projects",
                )
                .get(pk=pk)
            )

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Job seeker not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = AdminJobSeekerSerializer(
            profile
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


# =========================================================
# ADMIN - APPROVE JOB SEEKER
# =========================================================

class AdminJobSeekerApproveView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def patch(self, request, pk):

        try:

            profile = (
                JobSeekerProfile.objects
                .get(pk=pk)
            )

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Job seeker not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # PROFILE COMPLETION CHECK
        # =====================================================

        if not profile.profile_completed:

            return Response(
                {
                    "message":
                        "Job seeker has not completed the profile."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # APPROVE
        # =====================================================

        profile.approval_status = "approved"
        profile.rejection_reason = ""

        profile.save(
            update_fields=[
                "approval_status",
                "rejection_reason",
            ]
        )

        return Response(
            {
                "message":
                    "Job seeker approved successfully.",

                "id":
                    profile.id,

                "approval_status":
                    profile.approval_status,
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# ADMIN - REJECT JOB SEEKER
# =========================================================

class AdminJobSeekerRejectView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def patch(self, request, pk):

        try:

            profile = (
                JobSeekerProfile.objects
                .get(pk=pk)
            )

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Job seeker not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # REJECTION REASON
        # =====================================================

        reason = request.data.get(
            "rejection_reason",
            ""
        )

        if not isinstance(reason, str):
            reason = str(reason)

        reason = reason.strip()

        if not reason:

            return Response(
                {
                    "message":
                        "Rejection reason is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # REJECT
        # =====================================================

        profile.approval_status = "rejected"
        profile.rejection_reason = reason

        profile.save(
            update_fields=[
                "approval_status",
                "rejection_reason",
            ]
        )

        return Response(
            {
                "message":
                    "Job seeker rejected successfully.",

                "id":
                    profile.id,

                "approval_status":
                    profile.approval_status,

                "rejection_reason":
                    profile.rejection_reason,
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# LOGIN
# =========================================================
@method_decorator(csrf_exempt, name="dispatch")
class LoginView(APIView):

    permission_classes = [
        AllowAny
    ]

    def post(self, request):

        email = request.data.get(
            "email",
            ""
        ).strip()

        password = request.data.get(
            "password",
            ""
        )

        # =====================================================
        # VALIDATION
        # =====================================================

        if not email or not password:

            return Response(
                {
                    "detail":
                        "Email and password are required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # CHECK USER
        # =====================================================

        try:

            User.objects.get(
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

        # =====================================================
        # AUTHENTICATE
        # =====================================================

        authenticated_user = (
            authenticate_by_email(
                email,
                password
            )
        )

        if authenticated_user is None:

            return Response(
                {
                    "detail":
                        "Invalid email or password."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticated_user

        # =====================================================
        # DETERMINE ROLE
        # =====================================================

        if user.is_superuser:

            role = "admin"
            approval_status = "approved"

        elif hasattr(
            user,
            "jobseeker_profile"
        ):

            role = "jobseeker"

            approval_status = (
                user.jobseeker_profile
                .approval_status
            )

        elif hasattr(
            user,
            "employer_profile"
        ):

            role = "employer"

            approval_status = (
                user.employer_profile
                .approval_status
            )

        else:

            return Response(
                {
                    "detail":
                        "User role could not be identified."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =====================================================
        # JWT
        # =====================================================

        refresh = RefreshToken.for_user(
            user
        )

        access_token = str(
            refresh.access_token
        )

        refresh_token = str(
            refresh
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "message":
                    "Login successful.",

                "access":
                    access_token,

                "refresh":
                    refresh_token,

                "user": {

                    "id":
                        user.id,

                    "username":
                        user.username,

                    "email":
                        user.email,

                    "role":
                        role,

                    "approval_status":
                        approval_status,
                }
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# CURRENT USER
# =========================================================

class MeView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        user = request.user

        # =====================================================
        # ADMIN
        # =====================================================

        if user.is_superuser:

            role = "admin"

            name = (
                user.get_full_name()
                or user.username
            )

            approval_status = "approved"

            profile_completed = True

        # =====================================================
        # JOB SEEKER
        # =====================================================

        elif hasattr(user, "jobseeker_profile"):

            profile = user.jobseeker_profile

            role = "jobseeker"

            name = (
                profile.full_name
                or user.username
            )

            approval_status = (
                profile.approval_status
            )

            profile_completed = (
                profile.profile_completed
            )

        # =====================================================
        # EMPLOYER
        # =====================================================

        elif hasattr(user, "employer_profile"):

            profile = user.employer_profile

            role = "employer"

            name = (
                profile.company_name
                or user.username
            )

            approval_status = (
                profile.approval_status
            )

            profile_completed = getattr(
                profile,
                "profile_completed",
                True
            )

        # =====================================================
        # UNKNOWN ROLE
        # =====================================================

        else:

            return Response(
                {
                    "detail":
                        "User role could not be identified."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "id": user.id,

                "name": name,

                "email": user.email,

                "role": role,

                "approval_status":
                    approval_status,

                "profile_completed":
                    profile_completed,
            },
            status=status.HTTP_200_OK
        )
    
class AdminReportsFlagsView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def get(self, request):

        reports = []

        # =====================================================
        # REJECTED JOB SEEKERS
        # =====================================================

        rejected_jobseekers = (
            JobSeekerProfile.objects
            .filter(
                approval_status="rejected"
            )
            .select_related("user")
            .order_by("-updated_at")
        )

        for profile in rejected_jobseekers:

            reports.append(
                {
                    "id": f"jobseeker-{profile.id}",

                    "profile_id": profile.id,

                    "type": "Job Seeker",

                    "name": (
                        profile.full_name
                        or profile.user.email
                    ),

                    "email": profile.user.email,

                    "reason": (
                        profile.rejection_reason
                        or "No rejection reason provided."
                    ),

                    "submitted": (
                        profile.created_at
                    ),

                    "updated_at": (
                        profile.updated_at
                    ),

                    "approval_status": (
                        profile.approval_status
                    ),
                }
            )

        # =====================================================
        # REJECTED EMPLOYERS
        # =====================================================

        rejected_employers = (
            EmployerProfile.objects
            .filter(
                approval_status="rejected"
            )
            .select_related("user")
            .order_by("-updated_at")
        )

        for profile in rejected_employers:

            reports.append(
                {
                    "id": f"employer-{profile.id}",

                    "profile_id": profile.id,

                    "type": "Employer",

                    "name": (
                        profile.company_name
                        or profile.user.email
                    ),

                    "email": profile.user.email,

                    "reason": (
                        profile.rejection_reason
                        or "No rejection reason provided."
                    ),

                    "submitted": (
                        profile.created_at
                    ),

                    "updated_at": (
                        profile.updated_at
                    ),

                    "approval_status": (
                        profile.approval_status
                    ),
                }
            )

        # =====================================================
        # SORT
        # =====================================================

        reports.sort(
            key=lambda item: item["updated_at"],
            reverse=True
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            reports,
            status=status.HTTP_200_OK
        )



class AdminUsersView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def get(self, request):

        users = []

        # =====================================================
        # APPROVED JOB SEEKERS
        # =====================================================

        approved_jobseekers = (
            JobSeekerProfile.objects
            .filter(
                approval_status="approved"
            )
            .select_related("user")
            .order_by("-updated_at")
        )

        for profile in approved_jobseekers:

            name = (
                profile.full_name
                or profile.user.get_full_name()
                or profile.user.email
            )

            users.append(
                {
                    "id": profile.id,

                    "user_id": profile.user.id,

                    "name": name,

                    "email": profile.user.email,

                    "role": "job seeker",

                    "status": "Verified",

                    "joined": profile.created_at,

                    "profile_completed":
                        profile.profile_completed,

                    "approval_status":
                        profile.approval_status,
                }
            )

        # =====================================================
        # APPROVED EMPLOYERS
        # =====================================================

        approved_employers = (
            EmployerProfile.objects
            .filter(
                approval_status="approved"
            )
            .select_related("user")
            .order_by("-updated_at")
        )

        for profile in approved_employers:

            name = (
                profile.company_name
                or profile.user.get_full_name()
                or profile.user.email
            )

            users.append(
                {
                    "id": profile.id,

                    "user_id": profile.user.id,

                    "name": name,

                    "email": profile.user.email,

                    "role": "employer",

                    "status": "Verified",

                    "joined": profile.created_at,

                    "profile_completed":
                        getattr(
                            profile,
                            "profile_completed",
                            True
                        ),

                    "approval_status":
                        profile.approval_status,
                }
            )

        # =====================================================
        # SORT
        # =====================================================

        users.sort(
            key=lambda item: item["joined"]
            if item["joined"]
            else "",
            reverse=True
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            users,
            status=status.HTTP_200_OK
        )
    
# =========================================================
# ADMIN - EMPLOYER PROFILE
# =========================================================

# =========================================================
# ADMIN - EMPLOYER PROFILE
# =========================================================

class AdminEmployerProfileView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def get(self, request, pk):

        try:

            profile = (
                EmployerProfile.objects
                .select_related("user")
                .get(pk=pk)
            )

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Employer not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # COMPANY LOGO
        # =====================================================

        company_logo = None

        if getattr(profile, "company_logo", None):

            try:
                company_logo = profile.company_logo.url
            except ValueError:
                company_logo = None

        # =====================================================
        # UPLOADED DOCUMENTS
        # =====================================================

        documents = []

        for field in profile._meta.get_fields():

            # Only actual model fields
            if not hasattr(field, "name"):
                continue

            field_name = field.name

            # Don't include logo as a document
            if field_name == "company_logo":
                continue

            # Check whether field is a FileField / ImageField
            try:
                internal_type = field.get_internal_type()
            except Exception:
                continue

            if internal_type not in [
                "FileField",
                "ImageField"
            ]:
                continue

            try:

                file_value = getattr(
                    profile,
                    field_name,
                    None
                )

                if file_value:

                    try:
                        file_url = file_value.url
                    except ValueError:
                        file_url = None

                    if file_url:

                        documents.append(
                            {
                                "name": field_name,
                                "label": field_name.replace(
                                    "_",
                                    " "
                                ).title(),
                                "url": file_url,
                            }
                        )

            except Exception:

                continue

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "id":
                    profile.id,

                "user_id":
                    profile.user.id,

                # -------------------------------------------------
                # COMPANY
                # -------------------------------------------------

                "company_name":
                    profile.company_name or "",

                "contact_name":
                    getattr(
                        profile,
                        "contact_name",
                        ""
                    ) or "",

                "email":
                    profile.user.email or "",

                "company_email":
                    getattr(
                        profile,
                        "company_email",
                        profile.user.email
                    ) or "",

                "phone":
                    getattr(
                        profile,
                        "phone",
                        ""
                    ) or "",

                "website":
                    getattr(
                        profile,
                        "website",
                        ""
                    ) or "",

                "location":
                    getattr(
                        profile,
                        "location",
                        ""
                    ) or "",

                "company_description":
                    getattr(
                        profile,
                        "company_description",
                        ""
                    ) or "",

                # -------------------------------------------------
                # LOGO
                # -------------------------------------------------

                "company_logo":
                    company_logo,

                # -------------------------------------------------
                # DOCUMENTS
                # -------------------------------------------------

                "documents":
                    documents,

                # -------------------------------------------------
                # VERIFICATION
                # -------------------------------------------------

                "profile_completed":
                    getattr(
                        profile,
                        "profile_completed",
                        False
                    ),

                "approval_status":
                    profile.approval_status,

                "rejection_reason":
                    getattr(
                        profile,
                        "rejection_reason",
                        ""
                    ) or "",

                # -------------------------------------------------
                # DATES
                # -------------------------------------------------

                "created_at":
                    profile.created_at,

                "updated_at":
                    profile.updated_at,
            },

            status=status.HTTP_200_OK
        )

# =========================================================
# ADMIN - APPROVE EMPLOYER
# =========================================================

class AdminEmployerApproveView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def patch(self, request, pk):

        try:

            profile = (
                EmployerProfile.objects
                .get(pk=pk)
            )

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =================================================
        # PROFILE COMPLETION CHECK
        # =================================================

        if not getattr(
            profile,
            "profile_completed",
            False
        ):

            return Response(
                {
                    "message":
                        "Employer has not completed the profile."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =================================================
        # APPROVE
        # =================================================

        profile.approval_status = "approved"

        if hasattr(
            profile,
            "rejection_reason"
        ):
            profile.rejection_reason = ""

        update_fields = [
            "approval_status"
        ]

        if hasattr(
            profile,
            "rejection_reason"
        ):
            update_fields.append(
                "rejection_reason"
            )

        profile.save(
            update_fields=update_fields
        )

        return Response(
            {
                "message":
                    "Employer approved successfully.",

                "id":
                    profile.id,

                "approval_status":
                    profile.approval_status,
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# ADMIN - REJECT EMPLOYER
# =========================================================

class AdminEmployerRejectView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdminUserRole
    ]

    def patch(self, request, pk):

        try:

            profile = (
                EmployerProfile.objects
                .get(pk=pk)
            )

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "message":
                        "Employer not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =================================================
        # REJECTION REASON
        # =================================================

        reason = request.data.get(
            "rejection_reason",
            ""
        )

        if not isinstance(reason, str):

            reason = str(reason)

        reason = reason.strip()

        if not reason:

            return Response(
                {
                    "message":
                        "Rejection reason is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =================================================
        # REJECT
        # =================================================

        profile.approval_status = "rejected"

        if hasattr(
            profile,
            "rejection_reason"
        ):
            profile.rejection_reason = reason

            profile.save(
                update_fields=[
                    "approval_status",
                    "rejection_reason"
                ]
            )

        else:

            profile.save(
                update_fields=[
                    "approval_status"
                ]
            )

        return Response(
            {
                "message":
                    "Employer rejected successfully.",

                "id":
                    profile.id,

                "approval_status":
                    profile.approval_status,

                "rejection_reason":
                    reason,
            },
            status=status.HTTP_200_OK
        )