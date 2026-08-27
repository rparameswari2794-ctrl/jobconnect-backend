from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from secrets import randbelow
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.mail import send_mail
from datetime import timedelta
from django.utils import timezone


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import generics, permissions


from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from adminpanel.models import PasswordResetOTP

from .serializers import (
    JobSeekerSignupSerializer,
    JobSeekerProfileSerializer,
    JobApplicationSerializer,
    EducationSerializer,
    ExperienceSerializer,
    ProjectSerializer,
)

from .models import (
    JobSeekerProfile,
    JobApplication,
    Education,
    Experience,
    Project,

)

from employer.models import Job, EmployerProfile
from employer.serializers import JobSerializer


# =========================================================
# JOB SEEKER SIGNUP
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class JobSeekerSignupView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        serializer = JobSeekerSignupSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            profile = serializer.save()

            return Response(
                {
                    "message": "Job seeker account created successfully.",
                    "status": "pending",

                    "user": {
                        "id": profile.user.id,
                        "name": profile.full_name,
                        "email": profile.user.email,
                        "role": "jobseeker",
                        "approval_status": profile.approval_status,
                        "profile_completed": profile.profile_completed,
                    },
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:

            print("SIGNUP ERROR:", str(e))

            return Response(
                {
                    "message": "Unable to create account.",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    




# =========================================================
# JOB SEEKER LOGIN
# =========================================================


class JobSeekerLoginView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:

            return Response(
                {
                    "detail": "Email and password are required."
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
                    "detail": "Invalid email or password."
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
                    "detail": "Invalid email or password."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # -------------------------------------------------
        # JOB SEEKER PROFILE
        # -------------------------------------------------

        try:

            profile = user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "detail": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # -------------------------------------------------
        # JWT
        # -------------------------------------------------

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),

                "user": {
                    "id": user.id,
                    "name": profile.full_name,
                    "email": user.email,
                    "role": "jobseeker",
                    "approval_status": profile.approval_status,
                    "profile_completed": profile.profile_completed,
                }
            },
            status=status.HTTP_200_OK
        )
    
# =========================================================
# FORGOT PASSWORD - SEND OTP
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class ForgotPasswordView(APIView):

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

        except User.DoesNotExist:
            return Response(
                {"detail": "No account found with this email address."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Delete old OTP
        PasswordResetOTP.objects.filter(user=user).delete()

        # Generate 6-digit OTP
        otp = str(100000 + randbelow(900000))

        # Save OTP
        reset_otp = PasswordResetOTP.objects.create(
            user=user,
            otp=otp,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        # Send OTP
        try:
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

        except Exception as e:

            reset_otp.delete()

            return Response(
                {"detail": "Unable to send OTP email."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {
                "message": "OTP has been sent to your registered email.",
                "email": email
            },
            status=status.HTTP_200_OK
        )
    
    
# =========================================================
# VERIFY PASSWORD RESET OTP
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class VerifyOTPView(APIView):

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

        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST
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
    
# =========================================================
# RESET PASSWORD
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordView(APIView):

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

        except User.DoesNotExist:
            return Response(
                {"detail": "No account found with this email address."},
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
                {"detail": "OTP verification has expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate new password
        try:
            validate_password(
                new_password,
                user
            )

        except ValidationError as e:
            return Response(
                {"detail": e.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Change password
        user.set_password(new_password)
        user.save()

        # Delete used OTP
        reset_otp.delete()

        return Response(
            {
                "message": "Password reset successfully. You can now login."
            },
            status=status.HTTP_200_OK
        )

# =========================================================
# JOB SEEKER PROFILE
# =========================================================

# =========================================================
# JOB SEEKER PROFILE
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class JobSeekerProfileView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # =====================================================
    # GET PROFILE
    # =====================================================

    def get(self, request):

        try:
            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = JobSeekerProfileSerializer(
            profile,
            context={
                "request": request
            }
        )

        data = dict(serializer.data)

        # -------------------------------------------------
        # EDUCATION
        # -------------------------------------------------

        education = Education.objects.filter(
            jobseeker=profile
        ).order_by("-start_year")

        data["education"] = EducationSerializer(
            education,
            many=True,
            context={
                "request": request
            }
        ).data

        # -------------------------------------------------
        # EXPERIENCE
        # -------------------------------------------------

        experience = Experience.objects.filter(
            jobseeker=profile
        ).order_by("-start_date")

        data["experience"] = ExperienceSerializer(
            experience,
            many=True,
            context={
                "request": request
            }
        ).data

        # -------------------------------------------------
        # PROJECTS
        # -------------------------------------------------

        projects = Project.objects.filter(
            jobseeker=profile
        ).order_by("-id")

        data["projects"] = ProjectSerializer(
            projects,
            many=True,
            context={
                "request": request
            }
        ).data

        return Response(
            data,
            status=status.HTTP_200_OK
        )

    # =====================================================
    # UPDATE PROFILE
    # =====================================================

    def patch(self, request):

        try:
            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =================================================
        # PROFILE ALREADY SUBMITTED
        # =================================================

        if (
            profile.profile_completed is True
            and profile.approval_status == "pending"
        ):

            return Response(
                {
                    "message":
                        "Your profile has already been submitted "
                        "and is currently under admin review.",

                    "profile_completed": True,
                    "approval_status": "pending",
                    "readonly": True,
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =================================================
        # PROFILE ALREADY APPROVED
        # =================================================

        # if profile.approval_status == "approved":

        #     return Response(
        #         {
        #             "message":
        #                 "Your profile has already been approved.",

        #             "profile_completed": True,
        #             "approval_status": "approved",
        #             "readonly": True,
        #         },
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        # =================================================
        # REJECTED PROFILE
        # =================================================
        # Rejected users are allowed to edit their profile
        # and submit it again.

        # =================================================
        # UPDATE PROFILE
        # =================================================

        serializer = JobSeekerProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message": "Profile validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer.save()

        # =================================================
        # RETURN UPDATED PROFILE
        # =================================================

        profile_serializer = JobSeekerProfileSerializer(
            profile,
            context={
                "request": request
            }
        )

        data = dict(profile_serializer.data)

        # -------------------------------------------------
        # EDUCATION
        # -------------------------------------------------

        education = Education.objects.filter(
            jobseeker=profile
        ).order_by("-start_year")

        data["education"] = EducationSerializer(
            education,
            many=True,
            context={
                "request": request
            }
        ).data

        # -------------------------------------------------
        # EXPERIENCE
        # -------------------------------------------------

        experience = Experience.objects.filter(
            jobseeker=profile
        ).order_by("-start_date")

        data["experience"] = ExperienceSerializer(
            experience,
            many=True,
            context={
                "request": request
            }
        ).data

        # -------------------------------------------------
        # PROJECTS
        # -------------------------------------------------

        projects = Project.objects.filter(
            jobseeker=profile
        ).order_by("-id")

        data["projects"] = ProjectSerializer(
            projects,
            many=True,
            context={
                "request": request
            }
        ).data

        return Response(
            data,
            status=status.HTTP_200_OK
        )

# =========================================================
# EDUCATION
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class EducationView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def get(self, request):

        try:

            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        education = Education.objects.filter(
            jobseeker=profile
        ).order_by(
            "-start_year"
        )

        serializer = EducationSerializer(
            education,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    def post(self, request):

        try:

            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        print("======================================")
        print("EDUCATION REQUEST DATA:")
        print(request.data)
        print("======================================")

        serializer = EducationSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            print("EDUCATION ERRORS:")
            print(serializer.errors)

            return Response(
                {
                    "message": "Education validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        education = serializer.save(
            jobseeker=profile
        )

        return Response(
            EducationSerializer(education).data,
            status=status.HTTP_201_CREATED
        )


# =========================================================
# EDUCATION DETAIL
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class EducationDetailView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_object(
        self,
        request,
        education_id
    ):

        try:

            profile = request.user.jobseeker_profile

            return Education.objects.get(
                id=education_id,
                jobseeker=profile
            )

        except (
            JobSeekerProfile.DoesNotExist,
            Education.DoesNotExist
        ):

            return None

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def get(
        self,
        request,
        education_id
    ):

        education = self.get_object(
            request,
            education_id
        )

        if not education:

            return Response(
                {
                    "message": "Education not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EducationSerializer(
            education
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # -----------------------------------------------------
    # PATCH
    # -----------------------------------------------------

    def patch(
        self,
        request,
        education_id
    ):

        education = self.get_object(
            request,
            education_id
        )

        if not education:

            return Response(
                {
                    "message": "Education not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EducationSerializer(
            education,
            data=request.data,
            partial=True
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # -----------------------------------------------------
    # DELETE
    # -----------------------------------------------------

    def delete(
        self,
        request,
        education_id
    ):

        education = self.get_object(
            request,
            education_id
        )

        if not education:

            return Response(
                {
                    "message": "Education not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        education.delete()

        return Response(
            {
                "message": "Education deleted successfully."
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# EXPERIENCE
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class ExperienceView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # -----------------------------------------------------
    # GET ALL EXPERIENCE
    # -----------------------------------------------------

    def get(self, request):

        try:

            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        experiences = Experience.objects.filter(
            jobseeker=profile
        ).order_by(
            "-start_date"
        )

        serializer = ExperienceSerializer(
            experiences,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # -----------------------------------------------------
    # ADD EXPERIENCE
    # -----------------------------------------------------

    def post(self, request):

        try:

            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        print("======================================")
        print("EXPERIENCE REQUEST DATA:")
        print(request.data)
        print("======================================")

        serializer = ExperienceSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            print("======================================")
            print("EXPERIENCE VALIDATION ERRORS:")
            print(serializer.errors)
            print("======================================")

            return Response(
                {
                    "message": "Experience validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        experience = serializer.save(
            jobseeker=profile
        )

        return Response(
            ExperienceSerializer(experience).data,
            status=status.HTTP_201_CREATED
        )


# =========================================================
# EXPERIENCE DETAIL
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class ExperienceDetailView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_object(
        self,
        request,
        experience_id
    ):

        try:

            profile = request.user.jobseeker_profile

            return Experience.objects.get(
                id=experience_id,
                jobseeker=profile
            )

        except (
            JobSeekerProfile.DoesNotExist,
            Experience.DoesNotExist
        ):

            return None

    # -----------------------------------------------------
    # GET ONE
    # -----------------------------------------------------

    def get(
        self,
        request,
        experience_id
    ):

        experience = self.get_object(
            request,
            experience_id
        )

        if not experience:

            return Response(
                {
                    "message": "Experience not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ExperienceSerializer(
            experience
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # -----------------------------------------------------
    # PATCH
    # -----------------------------------------------------

    def patch(
        self,
        request,
        experience_id
    ):

        experience = self.get_object(
            request,
            experience_id
        )

        if not experience:

            return Response(
                {
                    "message": "Experience not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ExperienceSerializer(
            experience,
            data=request.data,
            partial=True
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # -----------------------------------------------------
    # DELETE
    # -----------------------------------------------------

    def delete(
        self,
        request,
        experience_id
    ):

        experience = self.get_object(
            request,
            experience_id
        )

        if not experience:

            return Response(
                {
                    "message": "Experience not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        experience.delete()

        return Response(
            {
                "message": "Experience deleted successfully."
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# PROJECT
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class ProjectView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):

        try:
            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        projects = Project.objects.filter(
            jobseeker=profile
        ).order_by("-id")

        serializer = ProjectSerializer(
            projects,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def post(self, request):

        try:
            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        print("======================================")
        print("PROJECT REQUEST DATA:")
        print(request.data)
        print("======================================")

        serializer = ProjectSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            print("PROJECT ERRORS:")
            print(serializer.errors)

            return Response(
                {
                    "message": "Project validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        project = serializer.save(
            jobseeker=profile
        )

        return Response(
            ProjectSerializer(project).data,
            status=status.HTTP_201_CREATED
        )
    
# =========================================================
# PROJECT DETAIL
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class ProjectDetailView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_object(self, request, project_id):

        try:

            profile = request.user.jobseeker_profile

            return Project.objects.get(
                id=project_id,
                jobseeker=profile
            )

        except (
            JobSeekerProfile.DoesNotExist,
            Project.DoesNotExist
        ):

            return None

    def get(self, request, project_id):

        project = self.get_object(
            request,
            project_id
        )

        if not project:

            return Response(
                {
                    "message": "Project not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ProjectSerializer(project)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def patch(self, request, project_id):

        project = self.get_object(
            request,
            project_id
        )

        if not project:

            return Response(
                {
                    "message": "Project not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ProjectSerializer(
            project,
            data=request.data,
            partial=True
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def delete(self, request, project_id):

        project = self.get_object(
            request,
            project_id
        )

        if not project:

            return Response(
                {
                    "message": "Project not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        project.delete()

        return Response(
            {
                "message": "Project deleted successfully."
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# MY APPLICATIONS
# =========================================================

# =========================================================
# MY APPLICATIONS
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class MyApplicationsView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):

        try:

            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        applications = JobApplication.objects.filter(
            jobseeker=profile
        ).select_related(
            "job",
            "job__employer"
        ).order_by(
            "-applied_at"
        )

        serializer = JobApplicationSerializer(
            applications,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

# =========================================================
# APPLICATION DETAIL
# =========================================================

# =========================================================
# APPLICATION DETAIL
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class JobApplicationDetailView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(
        self,
        request,
        application_id
    ):

        try:

            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        try:

            application = JobApplication.objects.select_related(
                "job",
                "job__employer"
            ).get(
                id=application_id,
                jobseeker=profile
            )

        except JobApplication.DoesNotExist:

            return Response(
                {
                    "message": "Application not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = JobApplicationSerializer(
            application
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

# =========================================================
# APPLY JOB
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class ApplyJobView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, job_id):

        # -------------------------------------------------
        # GET JOB SEEKER PROFILE
        # -------------------------------------------------

        try:

            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # -------------------------------------------------
        # APPROVAL CHECK
        # -------------------------------------------------

        if profile.approval_status != "approved":

            if profile.approval_status == "pending":

                return Response(
                    {
                        "message":
                            "Your job seeker account is pending. "
                            "Please wait for admin approval."
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            if profile.approval_status == "rejected":

                return Response(
                    {
                        "message":
                            "Your job seeker account has been rejected.",
                        "reason":
                            profile.rejection_reason
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        # -------------------------------------------------
        # FIND ACTIVE JOB
        # -------------------------------------------------

        try:

            job = Job.objects.select_related(
                "employer"
            ).get(
                id=job_id,
                is_active=True
            )

        except Job.DoesNotExist:

            return Response(
                {
                    "message": "Job not found or inactive."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # -------------------------------------------------
        # CHECK ALREADY APPLIED
        # -------------------------------------------------

        existing_application = JobApplication.objects.filter(
            job=job,
            jobseeker=profile
        ).first()

        if existing_application:

            return Response(
                {
                    "message":
                        "You have already applied for this job.",
                    "already_applied": True,
                    "application_id":
                        existing_application.id,
                    "status":
                        existing_application.status,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------------------------------
        # CREATE APPLICATION
        # -------------------------------------------------

        application = JobApplication.objects.create(
            job=job,
            jobseeker=profile,
            status="APPLIED"
        )

        # -------------------------------------------------
        # SERIALIZE
        # -------------------------------------------------

        serializer = JobApplicationSerializer(
            application
        )

        return Response(
            {
                "message":
                    "Job application submitted successfully.",
                "already_applied": True,
                "application":
                    serializer.data
            },
            status=status.HTTP_201_CREATED
        )

# =========================================================
# SUBMIT PROFILE FOR VERIFICATION
# =========================================================

# =========================================================
# SUBMIT PROFILE FOR VERIFICATION
# =========================================================

# =========================================================
# SUBMIT PROFILE FOR VERIFICATION
# =========================================================

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import JobSeekerProfile


@method_decorator(csrf_exempt, name="dispatch")
class SubmitProfileView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):

        print("=================================================")
        print("SUBMIT PROFILE API")
        print("USER:", request.user)
        print("USER ID:", request.user.id)
        print("AUTHENTICATED:", request.user.is_authenticated)
        print("=================================================")

        # =====================================================
        # GET PROFILE
        # =====================================================

        try:
            profile = JobSeekerProfile.objects.get(
                user=request.user
            )

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # ALREADY APPROVED
        # =====================================================

        if profile.approval_status == "approved":

            return Response(
                {
                    "message": "Your profile is already approved.",
                    "profile_completed": True,
                    "approval_status": "approved",
                    "locked": True,
                },
                status=status.HTTP_200_OK
            )

        # =====================================================
        # ALREADY SUBMITTED
        # =====================================================

        if (
            profile.profile_completed is True
            and
            profile.approval_status == "pending"
        ):

            return Response(
                {
                    "message":
                        "Your profile has already been submitted "
                        "for verification.",

                    "profile_completed": True,

                    "approval_status": "pending",

                    "locked": True,
                },
                status=status.HTTP_200_OK
            )

        # =====================================================
        # REQUIRED DOCUMENT VALIDATION
        # =====================================================

        missing_documents = []

        if not profile.profile_photo:
            missing_documents.append("Profile photo")

        if not profile.resume:
            missing_documents.append("Resume")

        if not profile.aadhaar:
            missing_documents.append("Aadhaar card")

        if missing_documents:

            return Response(
                {
                    "message":
                        "Please upload all required documents "
                        "before submitting your profile.",

                    "missing_documents":
                        missing_documents,

                    "profile_completed":
                        False,

                    "approval_status":
                        profile.approval_status,

                    "locked":
                        False,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # REJECTED PROFILE -> RESUBMIT
        # =====================================================

        if profile.approval_status == "rejected":

            profile.profile_completed = True
            profile.approval_status = "pending"
            profile.rejection_reason = ""

            profile.save(
                update_fields=[
                    "profile_completed",
                    "approval_status",
                    "rejection_reason",
                    "updated_at",
                ]
            )

            return Response(
                {
                    "message":
                        "Your profile has been resubmitted "
                        "for verification.",

                    "profile_completed": True,

                    "approval_status": "pending",

                    "locked": True,
                },
                status=status.HTTP_200_OK
            )

        # =====================================================
        # NORMAL SUBMISSION
        # =====================================================

        profile.profile_completed = True
        profile.approval_status = "pending"

        profile.save(
            update_fields=[
                "profile_completed",
                "approval_status",
                "updated_at",
            ]
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "message":
                    "Profile submitted successfully "
                    "for verification.",

                "profile_completed": True,

                "approval_status": "pending",

                "locked": True,
            },
            status=status.HTTP_200_OK
        )
    

# =========================================================
# FIND JOBS
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class JobListView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):

        # -------------------------------------------------
        # GET JOB SEEKER
        # -------------------------------------------------

        try:

            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # -------------------------------------------------
        # FILTER PARAMETERS
        # -------------------------------------------------

        search = request.GET.get(
            "search",
            ""
        ).strip()

        verified = request.GET.get(
            "verified",
            ""
        ).lower()

        job_type = request.GET.get(
            "job_type",
            ""
        ).strip()

        salary = request.GET.get(
            "salary",
            ""
        ).strip()

        # -------------------------------------------------
        # BASE QUERY
        # -------------------------------------------------

        jobs = Job.objects.filter(
            is_active=True
        ).select_related(
            "employer"
        ).order_by(
            "-created_at"
        )

        # -------------------------------------------------
        # VERIFIED EMPLOYER
        # -------------------------------------------------

        if verified == "true":

            jobs = jobs.filter(
                employer__approval_status="approved"
            )

        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

        if search:

            from django.db.models import Q

            jobs = jobs.filter(
                Q(title__icontains=search)
                |
                Q(
                    employer__company_name__icontains=search
                )
                |
                Q(skills__icontains=search)
            )

        # -------------------------------------------------
        # JOB TYPE
        # -------------------------------------------------

        if job_type:

            jobs = jobs.filter(
                job_type=job_type
            )

        # -------------------------------------------------
        # SALARY
        # -------------------------------------------------

        if salary:

            try:

                salary_value = float(salary)

                jobs = jobs.filter(
                    salary_max__gte=salary_value
                )

            except (
                ValueError,
                TypeError
            ):

                pass

        # -------------------------------------------------
        # BUILD RESPONSE
        # -------------------------------------------------

        job_list = []

        for job in jobs:

            # ---------------------------------------------
            # SKILLS
            # ---------------------------------------------

            skills = []

            if job.skills:

                skills = [
                    skill.strip()
                    for skill in job.skills.split(",")
                    if skill.strip()
                ]

            # ---------------------------------------------
            # EMPLOYER VERIFIED
            # ---------------------------------------------

            employer_verified = (
                job.employer.approval_status
                == "approved"
            )

            # ---------------------------------------------
            # APPLICATION
            # ---------------------------------------------

            application = JobApplication.objects.filter(
                job=job,
                jobseeker=profile
            ).first()

            # ---------------------------------------------
            # APPLICATION STATUS
            # ---------------------------------------------

            applied = application is not None

            application_status = (
                application.status
                if application
                else None
            )

            application_id = (
                application.id
                if application
                else None
            )

            # ---------------------------------------------
            # JOB DATA
            # ---------------------------------------------

            job_list.append(
    {
        "id": job.id,

        "title": job.title,

        "description": job.description,

        "company":
            job.employer.company_name,

        "location":
            job.location,

        # =====================================================
        # JOB TYPE
        # =====================================================

        "job_type":
            job.job_type,

        "job_type_display":
            job.get_job_type_display(),

        # =====================================================
        # WORK MODE
        # =====================================================

        "work_mode":
            job.work_mode,

        "work_mode_display":
            job.get_work_mode_display(),

        # =====================================================
        # EXPERIENCE
        # =====================================================

        "experience":
            job.experience,

        "experience_display":
            job.get_experience_display(),

        "minimum_experience":
            job.minimum_experience,

        "maximum_experience":
            job.maximum_experience,

        # =====================================================
        # SALARY
        # =====================================================

        "salary_min":
            str(job.salary_min)
            if job.salary_min is not None
            else None,

        "salary_max":
            str(job.salary_max)
            if job.salary_max is not None
            else None,

        # =====================================================
        # SKILLS
        # =====================================================

        "skills":
            skills,

        # =====================================================
        # JOB DETAILS
        # =====================================================

        "roles_responsibilities":
            job.roles_responsibilities,

        "key_features":
            job.key_features,

        "education_details":
            job.education_details,

        # =====================================================
        # EMPLOYER
        # =====================================================

        "employer_verified":
            employer_verified,

        "employer_approval_status":
            job.employer.approval_status,

        # =====================================================
        # DATE
        # =====================================================

        "created_at":
            job.created_at,

        # =====================================================
        # APPLICATION
        # =====================================================

        "applied":
            applied,

        "application_id":
            application_id,

        "application_status":
            application_status,

        "application_status_display":
            (
                application.get_status_display()
                if application
                else None
            ),
    }
)

        return Response(
            job_list,
            status=status.HTTP_200_OK
        )

# =========================================================
# JOB DETAILS FOR JOB SEEKER
# =========================================================


# =========================================================
# JOB SEEKER JOB DETAIL
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class JobSeekerJobDetailView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, job_id):

        # -------------------------------------------------
        # GET JOB SEEKER PROFILE
        # -------------------------------------------------

        try:
            profile = request.user.jobseeker_profile

        except JobSeekerProfile.DoesNotExist:

            return Response(
                {
                    "message": "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # -------------------------------------------------
        # GET ACTIVE JOB
        # -------------------------------------------------

        try:

            job = Job.objects.select_related(
                "employer"
            ).get(
                id=job_id,
                is_active=True
            )

        except Job.DoesNotExist:

            return Response(
                {
                    "message": "Job not found or inactive."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # -------------------------------------------------
        # SKILLS
        # -------------------------------------------------

        skills = []

        if job.skills:

            skills = [
                skill.strip()
                for skill in job.skills.split(",")
                if skill.strip()
            ]

        # -------------------------------------------------
        # EMPLOYER VERIFIED
        # -------------------------------------------------

        employer_verified = (
            job.employer.approval_status == "approved"
        )

        # -------------------------------------------------
        # APPLICATION
        # -------------------------------------------------

        application = JobApplication.objects.filter(
            job=job,
            jobseeker=profile
        ).first()

        applied = application is not None

        application_id = (
            application.id
            if application
            else None
        )

        application_status = (
            application.status
            if application
            else None
        )

        application_status_display = (
            application.get_status_display()
            if application
            else None
        )

        # -------------------------------------------------
        # JOB DATA
        # -------------------------------------------------

        job_data = {

    # =====================================================
    # BASIC
    # =====================================================

    "id": job.id,

    "title": job.title,

    "description": job.description,

    # =====================================================
    # COMPANY
    # =====================================================

    "company":
        job.employer.company_name,

    "company_name":
        job.employer.company_name,

    "employer_name":
        job.employer.company_name,

    # =====================================================
    # LOCATION
    # =====================================================

    "location":
        job.location,

    # =====================================================
    # JOB TYPE
    # =====================================================

    "job_type":
        job.job_type,

    "job_type_display":
        job.get_job_type_display(),

    # =====================================================
    # WORK MODE
    # =====================================================

    "work_mode":
        job.work_mode,

    "work_mode_display":
        job.get_work_mode_display(),

    # =====================================================
    # EXPERIENCE
    # =====================================================

    "experience":
        job.experience,

    "experience_display":
        job.get_experience_display(),

    "minimum_experience":
        job.minimum_experience,

    "maximum_experience":
        job.maximum_experience,

    # =====================================================
    # SALARY
    # =====================================================

    "salary_min":
        str(job.salary_min)
        if job.salary_min is not None
        else None,

    "salary_max":
        str(job.salary_max)
        if job.salary_max is not None
        else None,

    # =====================================================
    # SKILLS
    # =====================================================

    "skills":
        skills,

    # =====================================================
    # JOB INFORMATION
    # =====================================================

    "roles_responsibilities":
        job.roles_responsibilities,

    "key_features":
        job.key_features,

    "education_details":
        job.education_details,

    # =====================================================
    # APPLICATION
    # =====================================================

    "applied":
        applied,

    "application_id":
        application_id,

    "application_status":
        application_status,

    "application_status_display":
        application_status_display,

    # =====================================================
    # EMPLOYER
    # =====================================================

    "employer_verified":
        employer_verified,

    "employer_approval_status":
        job.employer.approval_status,

    # =====================================================
    # DATE
    # =====================================================

    "created_at":
        job.created_at,

    # =====================================================
    # ACTIVE
    # =====================================================

    "is_active":
        job.is_active,
}
        return Response(
            job_data,
            status=status.HTTP_200_OK
        )

class JobSeekerProjectListCreateView(generics.ListCreateAPIView):

    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(
            jobseeker=self.request.user.jobseeker_profile
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(
            jobseeker=self.request.user.jobseeker_profile
        )



class JobSeekerProjectDetailView(generics.RetrieveUpdateDestroyAPIView):

    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(
            jobseeker=self.request.user.jobseeker_profile
        )