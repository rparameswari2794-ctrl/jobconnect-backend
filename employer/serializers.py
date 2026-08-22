from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from rest_framework import serializers

from .models import EmployerProfile, Job
from jobseeker.models import JobApplication


# =========================================================
# EMPLOYER SIGNUP
# =========================================================

class EmployerSignupSerializer(serializers.Serializer):

    company_name = serializers.CharField(
        max_length=200
    )

    contact_name = serializers.CharField(
        max_length=150
    )

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    def validate_email(self, value):

        value = value.lower().strip()

        if User.objects.filter(
            username=value
        ).exists():

            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return value

    def validate_password(self, value):

        validate_password(value)

        return value

    def create(self, validated_data):

        company_name = validated_data["company_name"]
        contact_name = validated_data["contact_name"]
        email = validated_data["email"]
        password = validated_data["password"]

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password
        )

        profile = EmployerProfile.objects.create(
            user=user,
            company_name=company_name,
            contact_name=contact_name,
            company_email=email,
            approval_status="pending"
        )

        return profile


# =========================================================
# EMPLOYER PROFILE
# =========================================================

class EmployerProfileSerializer(serializers.ModelSerializer):

    class Meta:

        model = EmployerProfile

        fields = [
            "id",
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
            "profile_completed",
            "approval_status",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "profile_completed",
            "approval_status",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):

        representative_position = attrs.get(
            "representative_position",
            getattr(
                self.instance,
                "representative_position",
                ""
            )
        )

        authorization_letter = attrs.get(
            "authorization_letter"
        )

        existing_authorization = getattr(
            self.instance,
            "authorization_letter",
            None
        )

        requires_authorization = (
            representative_position not in [
                "",
                "director",
                "ceo",
                "proprietor",
            ]
        )

        if (
            requires_authorization
            and not authorization_letter
            and not existing_authorization
        ):

            raise serializers.ValidationError({
                "authorization_letter":
                    "Authorization Letter is required when "
                    "the representative is not a Director, CEO, "
                    "or Proprietor."
            })

        return attrs

    def update(self, instance, validated_data):

        was_approved = (
            instance.approval_status == "approved"
        )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if was_approved:

            instance.approval_status = "pending"
            instance.profile_completed = True
            instance.rejection_reason = ""

        else:

            instance.approval_status = "pending"
            instance.profile_completed = True
            instance.rejection_reason = ""

        instance.save()

        return instance


# =========================================================
# JOB SERIALIZER
# =========================================================

# =========================================================
# JOB SERIALIZER
# =========================================================

class JobSerializer(serializers.ModelSerializer):

    applicants_count = serializers.SerializerMethodField()

    class Meta:
        model = Job

        fields = [
            "id",
            "employer",

            "title",
            "description",
            "skills",
            "location",

            "job_type",
            "work_mode",

            "experience",
            "minimum_experience",
            "maximum_experience",

            "education_details",
            "roles_responsibilities",
            "key_features",

            "salary_min",
            "salary_max",

            "status",
            "is_active",

            "applicants_count",

            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "employer",
            "status",
            "is_active",
            "applicants_count",
            "created_at",
            "updated_at",
        ]

    def get_applicants_count(self, obj):
        return JobApplication.objects.filter(
            job=obj
        ).count()

    def validate(self, attrs):

        minimum_experience = attrs.get(
            "minimum_experience"
        )

        maximum_experience = attrs.get(
            "maximum_experience"
        )

        if (
            minimum_experience is not None
            and maximum_experience is not None
        ):

            if minimum_experience > maximum_experience:

                raise serializers.ValidationError({
                    "maximum_experience":
                        "Maximum experience must be greater than "
                        "or equal to minimum experience."
                })

        return attrs