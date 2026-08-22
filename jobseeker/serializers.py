from django.contrib.auth.models import User

from rest_framework import serializers

from .models import (
    JobSeekerProfile,
    Education,
    Experience,
    Project,
    JobApplication,
)


# =========================================================
# EDUCATION SERIALIZER
# =========================================================

class EducationSerializer(serializers.ModelSerializer):

    class Meta:

        model = Education

        fields = [
            "id",
            "degree",
            "university",
            "college",
            "start_year",
            "end_year",
            "passing_month_year",
            "percentage_cgpa",
            "activities",
        ]


# =========================================================
# EXPERIENCE SERIALIZER
# =========================================================

class ExperienceSerializer(serializers.ModelSerializer):

    start_date = serializers.CharField(
        required=False,
        allow_blank=True
    )

    end_date = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    employment_type = serializers.CharField(
        required=False,
        allow_blank=True
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True
    )

    is_current = serializers.BooleanField(
        required=False,
        default=False
    )

    class Meta:

        model = Experience

        fields = [
            "id",
            "job_title",
            "company",
            "employment_type",
            "start_date",
            "end_date",
            "is_current",
            "description",
        ]

        read_only_fields = [
            "id",
        ]

    def validate(self, attrs):

        is_current = attrs.get(
            "is_current",
            getattr(
                self.instance,
                "is_current",
                False
            ) if self.instance else False
        )

        end_date = attrs.get(
            "end_date",
            getattr(
                self.instance,
                "end_date",
                None
            ) if self.instance else None
        )

        # Current job
        if is_current:

            attrs["end_date"] = None

        # Previous job
        else:

            if not end_date:

                raise serializers.ValidationError({
                    "end_date":
                        "End date is required when this is not your current job."
                })

        return attrs

# =========================================================
# PROJECT SERIALIZER
# =========================================================

class ProjectSerializer(serializers.ModelSerializer):

    title = serializers.CharField(
        source="name"
    )

    project_link = serializers.URLField(
        source="project_url",
        required=False,
        allow_blank=True
    )

    project_type = serializers.CharField(
        required=False,
        allow_blank=True
    )

    class Meta:

        model = Project

        fields = [
            "id",
            "title",
            "project_type",
            "technologies",
            "project_link",
            "description",
        ]

        read_only_fields = [
            "id",
        ]


# =========================================================
# JOB SEEKER SIGNUP
# =========================================================



class JobSeekerSignupSerializer(serializers.ModelSerializer):

    full_name = serializers.CharField(
        write_only=True
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    role = serializers.CharField(
        write_only=True,
        required=False,
        default="jobseeker"
    )

    class Meta:
        model = User

        fields = [
            "full_name",
            "email",
            "password",
            "role",
        ]

    def validate_email(self, value):

        email = value.strip().lower()

        if User.objects.filter(
            email__iexact=email
        ).exists():

            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return email

    def create(self, validated_data):

        full_name = validated_data.pop(
            "full_name"
        )

        password = validated_data.pop(
            "password"
        )

        validated_data.pop(
            "role",
            None
        )

        email = validated_data["email"]

        # Create username from email
        username = email

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        profile = JobSeekerProfile.objects.create(
            user=user,
            full_name=full_name,
            approval_status="pending",
            profile_completed=False
        )

        return profile

# =========================================================
# JOB SEEKER PROFILE
# =========================================================

class JobSeekerProfileSerializer(serializers.ModelSerializer):

    # =====================================================
    # USER EMAIL
    # =====================================================

    email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    # =====================================================
    # RELATED DATA
    # =====================================================

    educations = EducationSerializer(
        many=True,
        read_only=True
    )

    experiences = ExperienceSerializer(
        many=True,
        read_only=True
    )

    projects = ProjectSerializer(
        many=True,
        read_only=True
    )

    # =====================================================
    # LINKEDIN
    # =====================================================

    linkedin = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def validate_linkedin(self, value):

        if not value:
            return ""

        value = value.strip()

        if not value.startswith(("http://", "https://")):
            value = "https://" + value

        from urllib.parse import urlparse

        parsed = urlparse(value)

        hostname = parsed.hostname

        if not hostname:
            raise serializers.ValidationError(
                "Please enter a valid LinkedIn profile URL."
            )

        hostname = hostname.lower()

        if hostname not in [
            "linkedin.com",
            "www.linkedin.com",
        ]:
            raise serializers.ValidationError(
                "Please enter a valid LinkedIn profile URL."
            )

        if not parsed.path.startswith("/in/"):
            raise serializers.ValidationError(
                "Please enter a valid LinkedIn profile URL "
                "such as linkedin.com/in/username."
            )

        username = parsed.path[len("/in/"):].strip("/")

        if not username:
            raise serializers.ValidationError(
                "Please enter a valid LinkedIn profile URL."
            )

        return value

    # =====================================================
    # META
    # =====================================================

    class Meta:

        model = JobSeekerProfile

        fields = [

            # -------------------------------------------------
            # BASIC / PERSONAL
            # -------------------------------------------------

            "id",
            "full_name",
            "email",
            "phone",
            "location",

            # -------------------------------------------------
            # PROFESSIONAL
            # -------------------------------------------------

            "headline",
            "skills",
            "linkedin",

            # -------------------------------------------------
            # EDUCATION
            # Separate Education model
            # -------------------------------------------------

            "educations",

            # -------------------------------------------------
            # EXPERIENCE
            # Separate Experience model
            # -------------------------------------------------

            "experiences",

            # -------------------------------------------------
            # PROJECTS
            # -------------------------------------------------

            "projects",

            # -------------------------------------------------
            # DOCUMENTS
            # -------------------------------------------------

            "resume",
            "aadhaar",
            "profile_photo",

            # -------------------------------------------------
            # VERIFICATION
            # -------------------------------------------------

            "profile_completed",
            "approval_status",
            "rejection_reason",

            # -------------------------------------------------
            # DATES
            # -------------------------------------------------

            "created_at",
            "updated_at",
        ]

        read_only_fields = [

            "id",
            "email",

            "educations",
            "experiences",
            "projects",

            "profile_completed",
            "approval_status",
            "rejection_reason",

            "created_at",
            "updated_at",
        ]

# =========================================================
# JOB APPLICATION
# =========================================================

class JobApplicationSerializer(serializers.ModelSerializer):

    job_title = serializers.CharField(
        source="job.title",
        read_only=True
    )

    company_name = serializers.CharField(
        source="job.employer.company_name",
        read_only=True
    )

    jobseeker_name = serializers.CharField(
        source="jobseeker.full_name",
        read_only=True
    )

    description = serializers.CharField(
        source="job.description",
        read_only=True
    )

    location = serializers.CharField(
        source="job.location",
        read_only=True
    )
    work_mode = serializers.CharField(
        source="job.work_mode",
        read_only=True
    )

    work_mode_display = serializers.CharField(
        source="job.get_work_mode_display",
        read_only=True
    )

    minimum_experience = serializers.IntegerField(
        source="job.minimum_experience",
        read_only=True
    )

    maximum_experience = serializers.IntegerField(
        source="job.maximum_experience",
        read_only=True
    )
    

    job_type = serializers.CharField(
        source="job.job_type",
        read_only=True
    )

    job_type_display = serializers.CharField(
        source="job.get_job_type_display",
        read_only=True
    )

    experience = serializers.CharField(
        source="job.experience",
        read_only=True
    )

    experience_display = serializers.CharField(
        source="job.get_experience_display",
        read_only=True
    )

    salary_min = serializers.DecimalField(
        source="job.salary_min",
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    salary_max = serializers.DecimalField(
        source="job.salary_max",
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    skills = serializers.CharField(
        source="job.skills",
        read_only=True
    )

    class Meta:

        model = JobApplication
        fields = "__all__"

        read_only_fields = [

            "id",
            "job_title",
            "company_name",
            "jobseeker_name",

            "description",
            "location",

            "job_type",
            "job_type_display",

            "work_mode",
            "work_mode_display",

            "experience",
            "experience_display",
            "minimum_experience",
            "maximum_experience",

            "salary_min",
            "salary_max",

            "skills",

            "status",
            "applied_at",
]