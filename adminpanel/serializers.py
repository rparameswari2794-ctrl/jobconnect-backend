from rest_framework import serializers

from jobseeker.models import (
    JobSeekerProfile,
    Education,
    Experience,
    Project,
)


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


class AdminJobSeekerSerializer(serializers.ModelSerializer):

    email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    educations = AdminEducationSerializer(
        many=True,
        read_only=True
    )

    experiences = AdminExperienceSerializer(
        many=True,
        read_only=True
    )

    projects = AdminProjectSerializer(
        many=True,
        read_only=True
    )

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

    disability_certificate = serializers.FileField(
        read_only=True,
        allow_null=True
    )

    class Meta:

        model = JobSeekerProfile

        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "location",
            "linkedin",
            "headline",
            "skills",

            # Disability
            "disability",
            "disability_category",
            "disability_type",
            "disability_percentage",
            "disability_certificate",

            # Education / Experience / Projects
            "educations",
            "experiences",
            "projects",

            # Documents
            "aadhaar",
            "resume",
            "profile_photo",

            # Approval
            "approval_status",
            "rejection_reason",
            "profile_completed",

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
            "disability_certificate",
            "created_at",
            "updated_at",
        ]


