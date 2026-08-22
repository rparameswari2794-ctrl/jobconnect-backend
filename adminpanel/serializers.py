from rest_framework import serializers

from jobseeker.models import (
    JobSeekerProfile,
    Education,
    Experience,
    Project,
)


# =========================================================
# ADMIN - EDUCATION
# =========================================================

class AdminEducationSerializer(serializers.ModelSerializer):

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
# ADMIN - EXPERIENCE
# =========================================================

class AdminExperienceSerializer(serializers.ModelSerializer):

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


# =========================================================
# ADMIN - PROJECT
# =========================================================

class AdminProjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = Project

        fields = [
            "id",
            "name",
            "project_type",
            "technologies",
            "project_url",
            "description",
        ]


# =========================================================
# ADMIN - JOB SEEKER
# =========================================================

class AdminJobSeekerSerializer(serializers.ModelSerializer):

    # -----------------------------------------------------
    # USER EMAIL
    # -----------------------------------------------------

    email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    # -----------------------------------------------------
    # EDUCATION
    # -----------------------------------------------------

    educations = AdminEducationSerializer(
        many=True,
        read_only=True
    )

    # -----------------------------------------------------
    # EXPERIENCE
    # -----------------------------------------------------

    experiences = AdminExperienceSerializer(
        many=True,
        read_only=True
    )

    # -----------------------------------------------------
    # PROJECTS
    # -----------------------------------------------------

    projects = AdminProjectSerializer(
        many=True,
        read_only=True
    )

    # -----------------------------------------------------
    # DOCUMENT URLs
    # -----------------------------------------------------

    aadhaar = serializers.FileField(
        read_only=True,
        allow_null=True
    )

    resume = serializers.FileField(
        read_only=True,
        allow_null=True
    )

    profile_photo = serializers.ImageField(
        read_only=True,
        allow_null=True
    )

    class Meta:

        model = JobSeekerProfile

        fields = [

            # =================================================
            # ID
            # =================================================

            "id",

            # =================================================
            # PERSONAL INFORMATION
            # =================================================

            "full_name",
            "email",
            "phone",
            "location",
            "linkedin",
            "headline",

            # =================================================
            # PROFESSIONAL INFORMATION
            # =================================================

            "skills",

            # =================================================
            # DETAILED INFORMATION
            # =================================================

            "educations",
            "experiences",
            "projects",

            # =================================================
            # DOCUMENTS
            # =================================================

            "aadhaar",
            "resume",
            "profile_photo",

            # =================================================
            # VERIFICATION
            # =================================================

            "approval_status",
            "rejection_reason",
            "profile_completed",

            # =================================================
            # DATES
            # =================================================

            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "email",
            "educations",
            "experiences",
            "projects",
            "aadhaar",
            "resume",
            "profile_photo",
            "created_at",
            "updated_at",
        ]

