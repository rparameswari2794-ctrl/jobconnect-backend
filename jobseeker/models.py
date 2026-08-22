from django.db import models
from django.contrib.auth.models import User





class JobSeekerProfile(models.Model):

    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="jobseeker_profile"
    )

    full_name = models.CharField(max_length=150)

    phone = models.CharField(
        max_length=20,
        blank=True
    )
    linkedin = models.URLField(
    blank=True
    )

    headline = models.CharField(
    max_length=300,
    blank=True
    )

    

    skills = models.TextField(
        blank=True
    )


    location = models.CharField(
        max_length=150,
        blank=True
    )
    aadhaar = models.FileField(
        upload_to="aadhaar/",
        blank=True,
        null=True
    )

    resume = models.FileField(
        upload_to="resumes/",
        blank=True,
        null=True
    )

    profile_photo = models.ImageField(
        upload_to="jobseekers/",
        blank=True,
        null=True
    )

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

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.full_name
    
class JobApplication(models.Model):

    STATUS_CHOICES = [
    ("APPLIED", "Applied"),
    ("UNDER REVIEW", "Under Review"),
    ("SHORTLISTED", "Shortlisted"),
    ("INTERVIEW SCHEDULED", "Interview Scheduled"),
    ("REJECTED", "Rejected"),
    ("HIRED", "Hired"),
]

    jobseeker = models.ForeignKey(
        "JobSeekerProfile",
        on_delete=models.CASCADE,
        related_name="job_applications"
    )

    job = models.ForeignKey(
        "employer.Job",
        on_delete=models.CASCADE,
        related_name="applications"
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="APPLIED"
    )

    applied_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-applied_at"]

    def __str__(self):
        return f"{self.jobseeker.full_name} - {self.job.title}"
    

class Education(models.Model):

    jobseeker = models.ForeignKey(
        JobSeekerProfile,
        on_delete=models.CASCADE,
        related_name="educations"
    )

    degree = models.CharField(
        max_length=200
    )

    university = models.CharField(
        max_length=200,
        blank=True
    )

    college = models.CharField(
        max_length=200,
        blank=True
    )

    start_year = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    end_year = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    passing_month_year = models.CharField(
        max_length=50,
        blank=True
    )

    percentage_cgpa = models.CharField(
        max_length=100,
        blank=True
    )

    activities = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.jobseeker.full_name} - {self.degree}"
    

class Experience(models.Model):

    jobseeker = models.ForeignKey(
        JobSeekerProfile,
        on_delete=models.CASCADE,
        related_name="experiences"
    )

    job_title = models.CharField(
        max_length=200
    )

    company = models.CharField(
        max_length=200
    )

    employment_type = models.CharField(
        max_length=100,
        blank=True
    )

    start_date = models.CharField(
        max_length=50,
        blank=True
    )

    end_date = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        default=None
    )

    is_current = models.BooleanField(
        default=False
    )

    description = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.jobseeker.full_name} - {self.job_title}"
    

class Project(models.Model):

    jobseeker = models.ForeignKey(
        JobSeekerProfile,
        on_delete=models.CASCADE,
        related_name="projects"
    )

    name = models.CharField(
        max_length=200
    )

    project_type = models.CharField(
        max_length=200,
        blank=True
    )

    technologies = models.CharField(
        max_length=500,
        blank=True
    )

    project_url = models.URLField(
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.jobseeker.full_name} - {self.name}"