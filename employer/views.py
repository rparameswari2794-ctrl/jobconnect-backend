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

from adminpanel.models import PasswordResetOTP

from .models import EmployerProfile, Job

from .serializers import (
    EmployerSignupSerializer,
    EmployerProfileSerializer,
    JobSerializer,
)
from jobseeker.models import JobApplication
User = get_user_model()

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
                    "message": "Employer signup validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            profile = serializer.save()

            return Response(
                {
                    "message": "Employer account created successfully.",

                    "approval_status":
                        profile.approval_status,

                    "profile_completed":
                        profile.profile_completed,

                    "employer": {
                        "id": profile.id,

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
        
class EmployerForgotPasswordView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email__iexact=email)
            employer = user.employer_profile

        except User.DoesNotExist:
            return Response(
                {"detail": "No employer account found with this email address."},
                status=status.HTTP_404_NOT_FOUND
            )

        except EmployerProfile.DoesNotExist:
            return Response(
                {"detail": "Employer profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Delete previous OTPs
        PasswordResetOTP.objects.filter(user=user).delete()

        # Generate 6-digit OTP
        otp = str(100000 + randbelow(900000))

        # Save OTP
        PasswordResetOTP.objects.create(
            user=user,
            otp=otp,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        # Send OTP
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
            {"message": "OTP has been sent to your registered email."},
            status=status.HTTP_200_OK
        )

class EmployerVerifyOTPView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email", "").strip().lower()
        otp = str(request.data.get("otp", "")).strip()

        if not email or not otp:
            return Response(
                {"detail": "Email and OTP are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email__iexact=email)
            user.employer_profile

        except User.DoesNotExist:
            return Response(
                {"detail": "No employer account found with this email address."},
                status=status.HTTP_404_NOT_FOUND
            )

        except EmployerProfile.DoesNotExist:
            return Response(
                {"detail": "Employer profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            reset_otp = PasswordResetOTP.objects.filter(
                user=user,
                otp=otp,
                is_verified=False
            ).latest("created_at")

        except PasswordResetOTP.DoesNotExist:
            return Response(
                {"detail": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check expiry
        if reset_otp.is_expired():
            reset_otp.delete()

            return Response(
                {"detail": "OTP has expired. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark OTP as verified
        reset_otp.is_verified = True
        reset_otp.save(update_fields=["is_verified"])

        return Response(
            {
                "message": "OTP verified successfully.",
                "verified": True,
                "email": email
            },
            status=status.HTTP_200_OK
        )
    
class EmployerResetPasswordView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email", "").strip().lower()
        new_password = request.data.get("new_password", "")

        if not email or not new_password:
            return Response(
                {"detail": "Email and new password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email__iexact=email)
            user.employer_profile

        except User.DoesNotExist:
            return Response(
                {"detail": "No employer account found with this email address."},
                status=status.HTTP_404_NOT_FOUND
            )

        except EmployerProfile.DoesNotExist:
            return Response(
                {"detail": "Employer profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get verified OTP
        try:
            reset_otp = PasswordResetOTP.objects.filter(
                user=user,
                is_verified=True
            ).latest("created_at")

        except PasswordResetOTP.DoesNotExist:
            return Response(
                {"detail": "Please verify your OTP first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check OTP expiry
        if reset_otp.is_expired():
            reset_otp.delete()

            return Response(
                {"detail": "OTP verification has expired. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate password
        try:
            validate_password(new_password, user)

        except ValidationError as e:
            return Response(
                {"detail": e.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Change password
        user.set_password(new_password)
        user.save()

        # OTP can no longer be reused
        reset_otp.delete()

        return Response(
            {"message": "Password reset successfully. You can now login."},
            status=status.HTTP_200_OK
        )
    
# =========================================================
# EMPLOYER LOGIN
# =========================================================

class EmployerLoginView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:

            return Response(
                {
                    "detail":
                        "Email and password are required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        email = email.strip().lower()

        # -------------------------------------------------
        # FIND USER
        # -------------------------------------------------

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

        # -------------------------------------------------
        # AUTHENTICATE
        # -------------------------------------------------

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

        # -------------------------------------------------
        # EMPLOYER PROFILE
        # -------------------------------------------------

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

        # -------------------------------------------------
        # JWT
        # -------------------------------------------------

        refresh = RefreshToken.for_user(user)

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
#
# Workflow:
#
# NEW
#   ↓
# Submit profile
#   ↓
# Pending
#   ↓
# Admin approves
#   ↓
# Approved
#   ↓
# Employer edits profile
#   ↓
# Pending again
#   ↓
# Profile locked
#   ↓
# Admin verifies again
#   ↓
# Approved
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
        #
        # This protects the backend even if somebody
        # bypasses the React frontend.
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
        # UPDATE PROFILE
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
        #
        # Keep it pending after submission.
        # =================================================

        elif previous_status == "pending":

            profile.approval_status = "pending"

        # =================================================
        # SAVE FINAL STATE
        # =================================================

        profile.save()

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

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # =====================================================
    # CREATE JOB
    # =====================================================

    def post(self, request):

        print("\n========================================")
        print("EMPLOYER CREATE JOB")
        print("========================================")

        print("USER:", request.user)
        print("AUTHENTICATED:", request.user.is_authenticated)
        print("DATA:", request.data)

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

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

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
        #
        # Current Job model uses is_active:
        #
        # True  = Live
        # False = Closed
        #
        # There is currently no separate draft field.
        # =================================================

        total_jobs = jobs.count()

        live_jobs = jobs.filter(
            is_active=True
        ).count()

        closed_jobs = jobs.filter(
            is_active=False
        ).count()

        # =================================================
        # TOTAL APPLICANTS
        #
        # Count all applications belonging to this employer's
        # jobs.
        # =================================================

        total_applicants = (
            JobApplication.objects
            .filter(
                job__employer=employer
            )
            .count()
        )

        # =================================================
        # PROFILE
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

        # =================================================
        # RESPONSE
        # =================================================

        return Response(
            {
                "profile":
                    profile_data,

                "stats": {

                    "total_jobs":
                        total_jobs,

                    "draft_jobs":
                        0,

                    "live_jobs":
                        live_jobs,

                    "closed_jobs":
                        closed_jobs,

                    "total_applicants":
                        total_applicants,
                },

                "jobs":
                    jobs_data,
            },
            status=status.HTTP_200_OK
        )
    
# =========================================================
# EMPLOYER JOB APPLICANTS
# =========================================================

class EmployerApplicantsView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):

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

            applicants.append(
                {
                    "id": application.id,

                    "application_id":
                        application.id,

                    "job_id":
                        job.id,

                    "job_title":
                        job.title,

                    # IMPORTANT:
                    # Database values are:
                    # applied
                    # shortlisted
                    # hired
                    # rejected

                    "status":
                        application.status,

                    "applied_at":
                        application.applied_at,

                    "jobseeker": {

                        "id":
                            applicant.id,

                        "full_name":
                            applicant.full_name,

                        "email":
                            applicant.user.email,

                        "phone":
                            applicant.phone,

                        "linkedin":
                            getattr(
                                applicant,
                                "linkedin",
                                ""
                            ),

                        "headline":
                            applicant.headline,

                       

                        "skills":
                            applicant.skills,

                        

                        "location":
                            applicant.location,

                        "approval_status":
                            applicant.approval_status,

                        "profile_completed":
                            applicant.profile_completed,
                    }
                }
            )

        # =====================================================
        # RESPONSE
        # =====================================================

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

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, application_id):

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
        # GET APPLICATION
        # =====================================================

        try:

            application = JobApplication.objects.select_related(
                "job",
                "job__employer",
                "jobseeker",
                "jobseeker__user",
            ).get(
                id=application_id,
                job__employer=employer
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
        # GET JOB SEEKER PROFILE
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
        # CANDIDATE PROFILE
        # =====================================================

        candidate = {

            "id":
                applicant.id,

            "full_name":
                applicant.full_name,

            "email":
                applicant.user.email,

            "phone":
                applicant.phone,

            "headline":
                applicant.headline,

            

            "skills":
                applicant.skills,

            "location":
                applicant.location,

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
        }

        return Response(
            candidate,
            status=status.HTTP_200_OK
        )
    
# =========================================================
# EMPLOYER VIEW APPLICANT PROFILE
# =========================================================

class EmployerApplicantDetailView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, application_id):

        # =====================================================
        # GET EMPLOYER
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
        # GET APPLICATION
        # =====================================================

        try:

            application = (
                JobApplication.objects
                .select_related(
                    "job",
                    "job__employer",
                    "jobseeker",
                    "jobseeker__user"
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
        # JOB SEEKER
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
        # CANDIDATE BASIC PROFILE
        # =====================================================

        candidate = {

            "id":
                applicant.id,

            "full_name":
                applicant.full_name,

            "email":
                applicant.user.email,

            "phone":
                applicant.phone,

            "linkedin":
                getattr(
                    applicant,
                    "linkedin",
                    ""
                ),

            "headline":
                applicant.headline,

            

            "skills":
                applicant.skills,


            "location":
                applicant.location,

            "profile_completed":
                applicant.profile_completed,

            "approval_status":
                applicant.approval_status,

            # =================================================
            # DOCUMENTS
            # =================================================

            "resume":
                get_file_url(
                    applicant.resume
                ),

            "aadhaar":
                get_file_url(
                    applicant.aadhaar
                ),

            "profile_photo":
                get_file_url(
                    applicant.profile_photo
                ),
        }

        # =====================================================
        # EDUCATION
        # =====================================================

        education_data = []

        education_queryset = (
            applicant.educations
            .all()
            .order_by("-start_year", "-id")
        )

        for education in education_queryset:

            education_data.append(
                {
                    "id":
                        education.id,

                    "degree":
                        education.degree or "",

                    "university":
                        education.university or "",

                    "college":
                        education.college or "",


                    "passing_month_year":
                        education.passing_month_year or "",

                    "percentage_cgpa":
                        education.percentage_cgpa or "",

                    "activities":
                        education.activities or "",
                }
            )

        # =====================================================
        # EXPERIENCE
        # =====================================================

        experience_data = []

        experience_queryset = (
            applicant.experiences
            .all()
            .order_by("-id")
        )

        for experience in experience_queryset:

            experience_data.append(
                {
                    "id":
                        experience.id,

                    "job_title":
                        experience.job_title or "",

                    "company":
                        experience.company or "",

                    "employment_type":
                        experience.employment_type or "",

                    "start_date":
                        experience.start_date or "",

                    "end_date":
                        experience.end_date or "",

                    "is_current":
                        experience.is_current,

                    "description":
                        experience.description or "",
                }
            )

        # =====================================================
        # PROJECTS
        # =====================================================

        projects_data = []

        projects_queryset = (
            applicant.projects
            .all()
            .order_by("-id")
        )

        for project in projects_queryset:

            projects_data.append(
                {
                    "id":
                        project.id,

                    "name":
                        project.name or "",

                    "project_type":
                        project.project_type or "",

                    "technologies":
                        project.technologies or "",

                    "project_url":
                        project.project_url or "",

                    "description":
                        project.description or "",
                }
            )

        # =====================================================
        # APPLICATION
        # =====================================================

        application_data = {

            "id":
                application.id,

            "status":
                application.status,

            "applied_at":
                application.applied_at,

            "job_id":
                application.job.id,

            "job_title":
                application.job.title,

            "company_name":
                employer.company_name,
        }

        # =====================================================
        # DEBUG
        # =====================================================

        print("\n========================================")
        print("EMPLOYER APPLICANT PROFILE")
        print("========================================")

        print(
            "APPLICATION ID:",
            application.id
        )

        print(
            "JOB SEEKER:",
            applicant.full_name
        )

        print(
            "EDUCATION COUNT:",
            len(education_data)
        )

        print(
            "EDUCATION DATA:",
            education_data
        )

        print(
            "EXPERIENCE COUNT:",
            len(experience_data)
        )

        print(
            "PROJECT COUNT:",
            len(projects_data)
        )

        print("========================================\n")

        # =====================================================
        # FINAL RESPONSE
        # =====================================================

        return Response(
            {

                "application":
                    application_data,

                "jobseeker":
                    candidate,

                "education":
                    education_data,

                "experience_details":
                    experience_data,

                "projects":
                    projects_data,
            },

            status=status.HTTP_200_OK
        )
    

# =========================================================
# EMPLOYER UPDATE APPLICANT STATUS
# =========================================================

class EmployerApplicationStatusView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, application_id):

        print("\n========================================")
        print("EMPLOYER UPDATE APPLICATION STATUS")
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
            "APPLICATION ID:",
            application_id
        )

        print(
            "DATA:",
            request.data
        )

        print("========================================")

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
                    "jobseeker"
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

        # =====================================================
        # ALLOWED STATUS
        # =====================================================

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
                    "message":
                        "Invalid application status.",

                    "allowed_statuses":
                        allowed_statuses,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # FINAL STATUS LOCK
        # =====================================================

        if current_status in [
            "REJECTED",
            "HIRED"
        ]:

            return Response(
                {
                    "message":
                        f"Application is already {current_status}. "
                        "Its status cannot be changed.",

                    "application_id":
                        application.id,

                    "status":
                        current_status,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # UPDATE
        # =====================================================

        application.status = new_status

        application.save(
            update_fields=["status"]
        )

        print(
            "STATUS UPDATED:",
            current_status,
            "->",
            new_status
        )

        # =====================================================
        # RESPONSE
        # =====================================================

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
    
# =========================================================
# EMPLOYER CLOSE JOB
# =========================================================
#
# Employer can close an active job.
#
# CLOSED JOB:
# - disappears from Job Seeker Find Jobs
# - remains visible in Employer My Jobs
# - cannot be reopened
# - cannot be edited through this endpoint
# - existing applications are NOT deleted
#
# =========================================================

class EmployerCloseJobView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, job_id):

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