from django.contrib.auth.models import User

from rest_framework import serializers

from .models import (
    JobSeekerProfile,
    Education,
    Experience,
    Project,
    JobApplication,
    Notification,
    Conversation,
    Message,
)
from employer.models import Job

# =========================================================
# NOTIFICATION SERIALIZER
# =========================================================

class NotificationSerializer(serializers.ModelSerializer):

    notification_type_display = serializers.CharField(
        source="get_notification_type_display",
        read_only=True
    )

    class Meta:

        model = Notification

        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "notification_type_display",
            "is_read",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "notification_type_display",
            "created_at",
        ]

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
        read_only_fields = ["id"]

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Project name is required."
            )

        return value

    def validate_project_url(self, value):
        if not value:
            return value

        value = value.strip()

        if not value.startswith(("http://", "https://")):
            value = f"https://{value}"

        return value



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
# JOB SEEKER PROFILE SERIALIZER
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

    # =====================================================
    # DISABILITY
    # =====================================================

    disability = serializers.BooleanField(
        required=False
    )

    disability_category = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    disability_type = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    disability_percentage = serializers.IntegerField(
        required=False,
        allow_null=True
    )

    # =====================================================
    # LINKEDIN VALIDATION
    # =====================================================

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

        if hostname not in (
            "linkedin.com",
            "www.linkedin.com",
        ):
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
    # DISABILITY VALIDATION
    # =====================================================

    def validate(self, attrs):

        # -------------------------------------------------
        # If disability was not included in this PATCH,
        # do not touch the existing disability information.
        # -------------------------------------------------

        if "disability" not in attrs:
            return attrs

        disability = attrs.get("disability")

        # =================================================
        # HAS DISABILITY
        # =================================================

        if disability is True:

            category = attrs.get(
                "disability_category",
                ""
            )

            disability_type = attrs.get(
                "disability_type",
                ""
            )

            percentage = attrs.get(
                "disability_percentage",
                None
            )

            # ---------------------------------------------
            # CATEGORY
            # ---------------------------------------------

            category = (
                str(category).strip()
                if category is not None
                else ""
            )

            if not category:

                raise serializers.ValidationError({
                    "disability_category":
                    "Please select a disability category."
                })

            # ---------------------------------------------
            # TYPE
            # ---------------------------------------------

            disability_type = (
                str(disability_type).strip()
                if disability_type is not None
                else ""
            )

            if not disability_type:

                raise serializers.ValidationError({
                    "disability_type":
                    "Please enter the type of disability."
                })

            # ---------------------------------------------
            # PERCENTAGE
            # ---------------------------------------------

            if percentage in (
                None,
                "",
                "null",
            ):

                raise serializers.ValidationError({
                    "disability_percentage":
                    "Please enter the percentage of disability."
                })

            try:

                percentage = int(percentage)

            except (
                ValueError,
                TypeError
            ):

                raise serializers.ValidationError({
                    "disability_percentage":
                    "Disability percentage must be a number."
                })

            if percentage < 1:

                raise serializers.ValidationError({
                    "disability_percentage":
                    "Disability percentage must be at least 1%."
                })

            if percentage > 100:

                raise serializers.ValidationError({
                    "disability_percentage":
                    "Disability percentage cannot exceed 100%."
                })

            # ---------------------------------------------
            # FINAL VALUES
            # ---------------------------------------------

            attrs["disability"] = True

            attrs["disability_category"] = category

            attrs["disability_type"] = disability_type

            attrs["disability_percentage"] = percentage

        # =================================================
        # NO DISABILITY
        # =================================================

        else:

            attrs["disability"] = False

            attrs["disability_category"] = ""

            attrs["disability_type"] = ""

            attrs["disability_percentage"] = None

        return attrs

    # =====================================================
    # UPDATE
    # =====================================================

    def update(self, instance, validated_data):

        for attr, value in validated_data.items():

            setattr(
                instance,
                attr,
                value
            )

        instance.save()

        instance.refresh_from_db()

        return instance

    # =====================================================
    # META
    # =====================================================

    class Meta:

        model = JobSeekerProfile

        fields = [
            "id",

            # BASIC
            "full_name",
            "email",
            "phone",
            "location",

            # PROFESSIONAL
            "headline",
            "skills",
            "linkedin",

            # DISABILITY
            "disability",
            "disability_category",
            "disability_type",
            "disability_percentage",

            # RELATED
            "educations",
            "experiences",
            "projects",

            # DOCUMENTS
            "resume",
            "aadhaar",
            "disability_certificate",
            "profile_photo",

            # APPROVAL
            "profile_completed",
            "approval_status",
            "rejection_reason",

            # DATES
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




# =========================================================
# NESTED JOB SERIALIZER FOR APPLICATION DETAILS
# =========================================================

class ApplicationJobSerializer(serializers.ModelSerializer):

    # -----------------------------------------------------
    # EMPLOYER / COMPANY
    # -----------------------------------------------------

    company_name = serializers.CharField(
        source="employer.company_name",
        read_only=True
    )

    company_location = serializers.CharField(
        source="employer.location",
        read_only=True
    )

    company_description = serializers.CharField(
        source="employer.company_description",
        read_only=True
    )

    company_website = serializers.CharField(
        source="employer.website",
        read_only=True
    )

    company_logo = serializers.SerializerMethodField()

    # -----------------------------------------------------
    # DISPLAY VALUES
    # -----------------------------------------------------

    job_type_display = serializers.CharField(
        source="get_job_type_display",
        read_only=True
    )

    work_mode_display = serializers.CharField(
        source="get_work_mode_display",
        read_only=True
    )

    experience_display = serializers.CharField(
        source="get_experience_display",
        read_only=True
    )

    # -----------------------------------------------------
    # COMPANY LOGO URL
    # -----------------------------------------------------

    def get_company_logo(self, obj):

        try:

            if obj.employer.company_logo:
                request = self.context.get("request")

                if request:
                    return request.build_absolute_uri(
                        obj.employer.company_logo.url
                    )

                return obj.employer.company_logo.url

        except Exception:
            pass

        return ""

    # -----------------------------------------------------
    # META
    # -----------------------------------------------------

    class Meta:

        model = Job

        fields = [
            # =================================================
            # JOB BASIC INFORMATION
            # =================================================

            "id",
            "title",
            "description",
            "skills",

            # =================================================
            # JOB DETAILS
            # =================================================

            "roles_responsibilities",
            "key_features",
            "education_details",

            # =================================================
            # LOCATION / WORK
            # =================================================

            "location",
            "work_mode",
            "work_mode_display",

            "is_disability_job",

            # =================================================
            # JOB TYPE
            # =================================================

            "job_type",
            "job_type_display",

            # =================================================
            # EXPERIENCE
            # =================================================

            "experience",
            "experience_display",

            "minimum_experience",
            "maximum_experience",

            # =================================================
            # SALARY
            # =================================================

            "salary_min",
            "salary_max",

            # =================================================
            # STATUS
            # =================================================

            "status",
            "is_active",

            # =================================================
            # EMPLOYER
            # =================================================

            "employer",
            "company_name",
            "company_location",
            "company_description",
            "company_website",
            "company_logo",

            # =================================================
            # DATES
            # =================================================

            "created_at",
            "updated_at",
        ]

        read_only_fields = fields


class ApplicationJobDetailsSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(
        source="employer.company_name",
        read_only=True
    )

    job_type_display = serializers.CharField(
        source="get_job_type_display",
        read_only=True
    )

    work_mode_display = serializers.CharField(
        source="get_work_mode_display",
        read_only=True
    )

    experience_display = serializers.CharField(
        source="get_experience_display",
        read_only=True
    )

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "company_name",
            "description",
            "skills",
            "roles_responsibilities",
            "key_features",
            "education_details",
            "location",
            "work_mode",
            "work_mode_display",
            "job_type",
            "job_type_display",
            "experience",
            "experience_display",
            "minimum_experience",
            "maximum_experience",
            "salary_min",
            "salary_max",
            "is_disability_job",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        ]


# =========================================================
# JOB APPLICATION SERIALIZER
# =========================================================

class JobApplicationSerializer(serializers.ModelSerializer):

    # =====================================================
    # COMPLETE NESTED JOB
    # =====================================================

    job = ApplicationJobSerializer(
        read_only=True
    )

    # =====================================================
    # JOB TITLE
    # =====================================================

    job_title = serializers.CharField(
        source="job.title",
        read_only=True
    )

    # =====================================================
    # COMPANY
    # =====================================================

    company_name = serializers.CharField(
        source="job.employer.company_name",
        read_only=True
    )

    # =====================================================
    # JOB SEEKER
    # =====================================================

    jobseeker_name = serializers.CharField(
        source="jobseeker.full_name",
        read_only=True
    )

    disability_type = serializers.CharField(
        source="jobseeker.disability_type",
        read_only=True,
        allow_blank=True,
        allow_null=True
    )

    # =====================================================
    # JOB DESCRIPTION
    # =====================================================

    description = serializers.CharField(
        source="job.description",
        read_only=True
    )

    # =====================================================
    # LOCATION
    # =====================================================

    location = serializers.CharField(
        source="job.location",
        read_only=True
    )

    # =====================================================
    # WORK MODE
    # =====================================================

    work_mode = serializers.CharField(
        source="job.work_mode",
        read_only=True
    )

    work_mode_display = serializers.CharField(
        source="job.get_work_mode_display",
        read_only=True
    )

    # =====================================================
    # EXPERIENCE
    # =====================================================

    minimum_experience = serializers.IntegerField(
        source="job.minimum_experience",
        read_only=True,
        allow_null=True
    )

    maximum_experience = serializers.IntegerField(
        source="job.maximum_experience",
        read_only=True,
        allow_null=True
    )

    experience = serializers.CharField(
        source="job.experience",
        read_only=True
    )

    experience_display = serializers.CharField(
        source="job.get_experience_display",
        read_only=True
    )

    # =====================================================
    # JOB TYPE
    # =====================================================

    job_type = serializers.CharField(
        source="job.job_type",
        read_only=True
    )

    job_type_display = serializers.CharField(
        source="job.get_job_type_display",
        read_only=True
    )

    # =====================================================
    # SALARY
    # =====================================================

    salary_min = serializers.DecimalField(
        source="job.salary_min",
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True
    )

    salary_max = serializers.DecimalField(
        source="job.salary_max",
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True
    )

    # =====================================================
    # SKILLS
    # =====================================================

    skills = serializers.CharField(
        source="job.skills",
        read_only=True
    )

    # =====================================================
    # ROLES & RESPONSIBILITIES
    # =====================================================

    roles_responsibilities = serializers.CharField(
        source="job.roles_responsibilities",
        read_only=True
    )

    # =====================================================
    # KEY FEATURES
    # =====================================================

    key_features = serializers.CharField(
        source="job.key_features",
        read_only=True
    )

    # =====================================================
    # EDUCATION
    # =====================================================

    education_details = serializers.CharField(
        source="job.education_details",
        read_only=True
    )

    # =====================================================
    # DISABILITY JOB
    # =====================================================

    is_disability_job = serializers.BooleanField(
        source="job.is_disability_job",
        read_only=True
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:

        model = JobApplication

        fields = [
            # =================================================
            # APPLICATION
            # =================================================

            "id",
            "status",
            "applied_at",

            # =================================================
            # COMPLETE JOB OBJECT
            # =================================================

            "job",

            # =================================================
            # JOB SUMMARY
            # =================================================

            "job_title",
            "company_name",
            "description",
            "location",

            # =================================================
            # WORK MODE
            # =================================================

            "work_mode",
            "work_mode_display",

            # =================================================
            # JOB TYPE
            # =================================================

            "job_type",
            "job_type_display",

            # =================================================
            # EXPERIENCE
            # =================================================

            "experience",
            "experience_display",
            "minimum_experience",
            "maximum_experience",

            # =================================================
            # SALARY
            # =================================================

            "salary_min",
            "salary_max",

            # =================================================
            # SKILLS
            # =================================================

            "skills",

            # =================================================
            # COMPLETE JOB CONTENT
            # =================================================

            "roles_responsibilities",
            "key_features",
            "education_details",
            "is_disability_job",

            # =================================================
            # JOB SEEKER
            # =================================================

            "jobseeker",
            "jobseeker_name",
            "disability_type",
        ]

        read_only_fields = [
            "id",
            "job",
            "job_title",
            "company_name",
            "description",
            "location",
            "work_mode",
            "work_mode_display",
            "job_type",
            "job_type_display",
            "experience",
            "experience_display",
            "minimum_experience",
            "maximum_experience",
            "salary_min",
            "salary_max",
            "skills",
            "roles_responsibilities",
            "key_features",
            "education_details",
            "is_disability_job",
            "jobseeker",
            "jobseeker_name",
            "disability_type",
            "status",
            "applied_at",
        ]


# ============================================================
# CHAT SERIALIZERS
# ============================================================


class ChatParticipantSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()

    role = serializers.CharField()

    name = serializers.CharField()

    email = serializers.EmailField(
        allow_blank=True
    )

    profile_id = serializers.IntegerField(
        allow_null=True
    )

    company_name = serializers.CharField(
        allow_blank=True
    )

    profile_photo = serializers.CharField(
        allow_blank=True,
        allow_null=True,
    )


class ConversationSerializer(serializers.ModelSerializer):
    participant = serializers.SerializerMethodField()

    last_message = serializers.SerializerMethodField()

    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation

        fields = [
            "id",
            "participant",
            "last_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]

    def get_participant(self, obj):
        request = self.context.get("request")

        if not request or not request.user:
            return None

        participant = obj.other_participant(
            request.user
        )

        # ----------------------------------------------------
        # EMPLOYER
        # ----------------------------------------------------

        employer = getattr(
            participant,
            "employer_profile",
            None,
        )

        if employer:

            profile_photo = ""

            try:
                if employer.company_logo:
                    profile_photo = employer.company_logo.url
            except Exception:
                profile_photo = ""

            return {
                "user_id": participant.id,

                "role": "employer",

                "name": (
                    employer.contact_name
                    or employer.company_name
                    or participant.username
                ),

                "email": (
                    participant.email
                    or getattr(
                        employer,
                        "company_email",
                        "",
                    )
                    or ""
                ),

                "profile_id": employer.id,

                "company_name": (
                    employer.company_name
                    or ""
                ),

                "profile_photo": profile_photo,
            }

        # ----------------------------------------------------
        # JOBSEEKER
        # ----------------------------------------------------

        jobseeker = getattr(
            participant,
            "jobseeker_profile",
            None,
        )

        if jobseeker:

            profile_photo = ""

            try:
                if jobseeker.profile_photo:
                    profile_photo = (
                        jobseeker.profile_photo.url
                    )
            except Exception:
                profile_photo = ""

            return {
                "user_id": participant.id,

                "role": "jobseeker",

                "name": (
                    jobseeker.full_name
                    or participant.get_full_name()
                    or participant.username
                ),

                "email": (
                    participant.email
                    or ""
                ),

                "profile_id": jobseeker.id,

                "company_name": "",

                "profile_photo": profile_photo,
            }

        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        return {
            "user_id": participant.id,

            "role": "user",

            "name": (
                participant.get_full_name()
                or participant.username
            ),

            "email": participant.email or "",

            "profile_id": None,

            "company_name": "",

            "profile_photo": "",
        }

    def get_last_message(self, obj):

        message = (
            obj.messages
            .order_by(
                "-created_at",
                "-id",
            )
            .first()
        )

        if not message:
            return None

        return {
            "id": message.id,

            "text": message.text,

            "sender_id": message.sender_id,

            "is_read": message.is_read,

            "created_at": message.created_at,
        }

    def get_unread_count(self, obj):

        request = self.context.get("request")

        if not request:
            return 0

        return (
            obj.messages
            .filter(
                is_read=False
            )
            .exclude(
                sender=request.user
            )
            .count()
        )


class ChatMessageSerializer(serializers.ModelSerializer):

    sender_name = serializers.SerializerMethodField()

    mine = serializers.SerializerMethodField()

    class Meta:

        model = Message

        fields = [
            "id",
            "conversation",
            "sender",
            "sender_name",
            "mine",
            "text",
            "is_read",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "conversation",
            "sender",
            "sender_name",
            "mine",
            "is_read",
            "created_at",
            "updated_at",
        ]

    def get_sender_name(self, obj):

        jobseeker = getattr(
            obj.sender,
            "jobseeker_profile",
            None,
        )

        if jobseeker:

            return (
                jobseeker.full_name
                or obj.sender.username
            )

        employer = getattr(
            obj.sender,
            "employer_profile",
            None,
        )

        if employer:

            return (
                employer.company_name
                or employer.contact_name
                or obj.sender.username
            )

        return (
            obj.sender.get_full_name()
            or obj.sender.username
        )

    def get_mine(self, obj):

        request = self.context.get("request")

        return bool(
            request
            and obj.sender_id == request.user.id
        )