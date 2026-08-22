from django.db import models
from django.contrib.auth.models import User


# =========================================================
# EMPLOYER PROFILE
# =========================================================

class EmployerProfile(models.Model):

    # =====================================================
    # APPROVAL STATUS
    # =====================================================

    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    # =====================================================
    # REPRESENTATIVE POSITION
    # =====================================================

    REPRESENTATIVE_POSITION_CHOICES = [
        ("director", "Director"),
        ("ceo", "CEO"),
        ("proprietor", "Proprietor"),
        ("hr", "HR"),
        ("manager", "Manager"),
        ("authorized_person", "Authorized Person"),
        ("other", "Other"),
    ]

    # =====================================================
    # USER
    # =====================================================

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employer_profile"
    )

    # =====================================================
    # COMPANY INFORMATION
    # =====================================================

    company_name = models.CharField(
        max_length=200
    )

    contact_name = models.CharField(
        max_length=150
    )

    representative_position = models.CharField(
        max_length=30,
        choices=REPRESENTATIVE_POSITION_CHOICES,
        blank=True
    )

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    company_email = models.EmailField(
        blank=True
    )

    company_description = models.TextField(
        blank=True
    )

    website = models.URLField(
        blank=True
    )

    location = models.CharField(
        max_length=150,
        blank=True
    )

    # =====================================================
    # COMPANY LOGO
    # =====================================================

    company_logo = models.ImageField(
        upload_to="employers/",
        blank=True,
        null=True
    )

    # =====================================================
    # VERIFICATION DOCUMENTS
    # =====================================================

    company_gst_certificate = models.FileField(
        upload_to="employer_documents/gst/",
        blank=True,
        null=True
    )

    company_registration_certificate = models.FileField(
        upload_to="employer_documents/registration/",
        blank=True,
        null=True
    )

    authorization_letter = models.FileField(
        upload_to="employer_documents/authorization/",
        blank=True,
        null=True
    )

    # =====================================================
    # PROFILE STATUS
    # =====================================================

    profile_completed = models.BooleanField(
        default=False
    )

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default="pending"
    )

    rejection_reason = models.TextField(
        blank=True,
        default=""
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.company_name


# =========================================================
# JOB
# =========================================================

class Job(models.Model):

    # =====================================================
    # JOB TYPE
    # =====================================================

    JOB_TYPE_CHOICES = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("contract", "Contract"),
        ("internship", "Internship"),
    ]

    # =====================================================
    # EXPERIENCE
    # =====================================================

    EXPERIENCE_CHOICES = [
        ("fresher", "Fresher"),
        ("0-2", "0-2 Years"),
        ("2-5", "2-5 Years"),
        ("5+", "5+ Years"),
    ]

    # =====================================================
    # JOB STATUS
    # =====================================================

    STATUS_CHOICES = [
        ("live", "Live"),
        ("closed", "Closed"),
    ]

    # =====================================================
    # EMPLOYER
    # =====================================================

    employer = models.ForeignKey(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name="jobs"
    )

    # =====================================================
    # BASIC JOB INFORMATION
    # =====================================================

    title = models.CharField(
        max_length=200
    )

    description = models.TextField()

    skills = models.TextField()

    # =====================================================
    # ROLES & RESPONSIBILITIES
    # =====================================================

    roles_responsibilities = models.TextField(
        blank=True,
        default=""
    )

    # =====================================================
    # KEY FEATURES / WHAT THIS ROLE OFFERS
    # =====================================================

    key_features = models.TextField(
        blank=True,
        default=""
    )

    # =====================================================
    # EDUCATION DETAILS
    # =====================================================

    education_details = models.TextField(
        blank=True,
        default=""
    )

    # =====================================================
    # LOCATION
    # =====================================================

    location = models.CharField(
        max_length=150
    )
    # =====================================================
# WORK MODE
# =====================================================

    WORK_MODE_CHOICES = [
        ("onsite", "On-site"),
        ("hybrid", "Hybrid"),
        ("remote", "Remote"),
    ]

    work_mode = models.CharField(
        max_length=20,
        choices=WORK_MODE_CHOICES,
        default="onsite"
    )

    # =====================================================
    # JOB TYPE
    # =====================================================

    job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPE_CHOICES
    )

    # =====================================================
    # EXPERIENCE CATEGORY
    # =====================================================

    experience = models.CharField(
        max_length=20,
        choices=EXPERIENCE_CHOICES
    )

    # =====================================================
    # MINIMUM EXPERIENCE
    #
    # Example:
    # 0 = Fresher
    # 1 = 1 year
    # 2 = 2 years
    # =====================================================

    minimum_experience = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    # =====================================================
    # MAXIMUM EXPERIENCE
    #
    # Example:
    # 2 = up to 2 years
    # 5 = up to 5 years
    # =====================================================

    maximum_experience = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    # =====================================================
    # SALARY
    # =====================================================

    salary_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    salary_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    # =====================================================
    # STATUS
    # =====================================================

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="live"
    )

    # =====================================================
    # ACTIVE FLAG
    # =====================================================

    is_active = models.BooleanField(
        default=True
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    # =====================================================
    # STRING
    # =====================================================

    def __str__(self):
        return self.title