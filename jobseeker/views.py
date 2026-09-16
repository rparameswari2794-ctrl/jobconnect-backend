# ============================================================
# jobseeker/views.py
# COMPLETE CLEAN VERSION
# ============================================================

from datetime import timedelta, datetime
import random
import re

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models, transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

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

from .serializers import (
    JobSeekerProfileSerializer,
    EducationSerializer,
    ExperienceSerializer,
    ProjectSerializer,
    JobSeekerSignupSerializer,
    ConversationSerializer,
    ChatMessageSerializer,
)

# Change this import if your Job model is in a different app.
from employer.models import Job


# ============================================================
# CONSTANTS
# ============================================================

TRACKED_PROFILE_FIELDS = [
    "full_name",
    "phone",
    "location",
    "headline",
    "skills",
    "linkedin",
    "disability",
    "disability_category",
    "disability_type",
    "disability_percentage",
    "disability_certificate",
    "resume",
    "aadhaar",
    "profile_photo",
]


FIELD_LABELS = {
    "full_name": "Full Name",
    "phone": "Phone",
    "location": "Location",
    "headline": "Headline",
    "skills": "Skills",
    "linkedin": "LinkedIn",
    "disability": "Disability Status",
    "disability_category": "Disability Category",
    "disability_type": "Disability Type",
    "disability_percentage": "Disability Percentage",
    "disability_certificate": "Disability Certificate",
    "resume": "Resume",
    "aadhaar": "Aadhaar",
    "profile_photo": "Profile Photo",
}


# ============================================================
# HELPER - GET JOB SEEKER PROFILE
# ============================================================

def get_jobseeker_profile(request):
    """
    Get the logged-in user's JobSeekerProfile.
    """

    try:
        return JobSeekerProfile.objects.get(
            user=request.user
        )

    except JobSeekerProfile.DoesNotExist:
        return None


# ============================================================
# HELPER - PROFILE BY USER
# ============================================================

def get_jobseeker_profile_by_user(user):

    try:
        return JobSeekerProfile.objects.get(
            user=user
        )

    except JobSeekerProfile.DoesNotExist:
        return None


# ============================================================
# AI JOB MATCHING
# ============================================================

AI_MATCH_THRESHOLD = 50


def _normalize_match_text(value):
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)

    return text


def _tokenize_match_text(value):
    text = _normalize_match_text(value)

    if not text:
        return set()

    words = re.findall(r"[a-zA-Z0-9+#.]+", text)

    stop_words = {
        "and", "the", "for", "with", "from", "that", "this",
        "are", "you", "your", "our", "will", "have", "has",
        "job", "role", "work", "working", "years", "year",
        "using", "required", "requirements", "candidate", "candidates",
        "should", "must", "into", "their", "they", "them", "who",
        "is", "be", "to", "of", "in", "on", "a", "an", "at", "or",
        "as", "by", "it", "we", "about", "also", "develop",
        "development", "looking", "seeking", "responsible",
        "responsibilities", "experience", "developer", "engineer",
        "software", "technology", "technologies",
    }

    return {
        word.strip(".#")
        for word in words
        if len(word.strip(".#")) >= 2
        and word.strip(".#") not in stop_words
    }


def _split_skill_values(value):
    if value is None:
        return set()

    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = re.split(r"[,;\n|]+", str(value))

    result = set()

    for item in values:
        if isinstance(item, dict):
            item = (
                item.get("name")
                or item.get("skill_name")
                or ""
            )

        item = _normalize_match_text(item)

        if item:
            result.add(item)

    return result


# ============================================================
# SKILL FAMILIES
# ============================================================

SKILL_FAMILIES = {
    "frontend": {
        "frontend", "front end", "frontend development",
        "ui development", "web frontend", "react", "reactjs",
        "react.js", "javascript", "typescript", "html", "html5",
        "css", "css3", "tailwind", "tailwindcss", "bootstrap",
        "angular", "vue", "nextjs", "next.js", "redux",
        "responsive design", "web development",
    },

    "backend": {
        "backend", "back end", "backend development",
        "server side", "python", "django", "django rest framework",
        "drf", "flask", "fastapi", "java", "spring", "spring boot",
        "node", "nodejs", "node.js", "express", "expressjs",
        "php", "laravel", "c#", ".net", "dotnet", "rest api",
        "rest", "api development", "microservices",
    },

    "fullstack": {
        "full stack", "fullstack", "full stack development",
        "fullstack development", "web application development",
    },

    "database": {
        "database", "sql", "mysql", "postgresql", "postgres",
        "sqlite", "oracle", "mongodb", "mongo", "redis",
        "database design", "database management",
    },

    "devops": {
        "devops", "docker", "kubernetes", "k8s", "jenkins",
        "ci cd", "cicd", "github actions", "gitlab ci", "aws",
        "azure", "gcp", "cloud", "terraform", "ansible", "linux",
    },

    "data": {
        "data science", "data analyst", "data analysis",
        "machine learning", "ml", "artificial intelligence", "ai",
        "deep learning", "nlp", "pandas", "numpy", "scikit learn",
        "sklearn", "tensorflow", "pytorch", "power bi", "tableau",
        "statistics", "data engineering", "data engineer",
    },

    "testing": {
        "testing", "qa", "quality assurance", "manual testing",
        "automation testing", "selenium", "cypress", "playwright",
        "pytest", "unit testing", "integration testing",
    },

    "mobile": {
        "android", "ios", "mobile development", "react native",
        "flutter", "dart", "kotlin", "swift", "swiftui",
    },

    "design": {
        "ui design", "ux design", "ui ux", "figma", "adobe xd",
        "wireframing", "prototyping", "user experience",
        "user interface",
    },

    "programming": {
        "python", "java", "javascript", "typescript", "c", "c++",
        "c#", ".net", "go", "golang", "rust", "php", "ruby",
        "kotlin", "swift",
    },

    "version_control": {
        "git", "github", "gitlab", "bitbucket", "version control",
    },
}


# ============================================================
# RELATED FAMILY WEIGHTS
# ============================================================

RELATED_FAMILY_WEIGHTS = {
    "frontend": {
        "frontend": 1.00,
        "fullstack": 0.88,
        "backend": 0.55,
        "design": 0.60,
        "programming": 0.65,
        "testing": 0.45,
        "database": 0.20,
        "devops": 0.20,
    },

    "backend": {
        "backend": 1.00,
        "fullstack": 0.88,
        "frontend": 0.55,
        "programming": 0.80,
        "database": 0.75,
        "devops": 0.55,
        "testing": 0.45,
        "data": 0.45,
    },

    "fullstack": {
        "fullstack": 1.00,
        "frontend": 0.90,
        "backend": 0.90,
        "programming": 0.75,
        "database": 0.70,
        "devops": 0.55,
        "testing": 0.45,
    },

    "database": {
        "database": 1.00,
        "backend": 0.75,
        "fullstack": 0.70,
        "data": 0.70,
        "devops": 0.45,
        "testing": 0.25,
    },

    "devops": {
        "devops": 1.00,
        "backend": 0.55,
        "fullstack": 0.55,
        "database": 0.45,
        "programming": 0.45,
        "testing": 0.50,
    },

    "data": {
        "data": 1.00,
        "programming": 0.65,
        "database": 0.70,
        "backend": 0.45,
        "fullstack": 0.35,
        "testing": 0.20,
    },

    "testing": {
        "testing": 1.00,
        "backend": 0.45,
        "frontend": 0.45,
        "fullstack": 0.45,
        "programming": 0.40,
        "devops": 0.50,
    },

    "mobile": {
        "mobile": 1.00,
        "frontend": 0.60,
        "programming": 0.70,
        "backend": 0.40,
        "fullstack": 0.45,
        "testing": 0.40,
    },

    "design": {
        "design": 1.00,
        "frontend": 0.65,
        "fullstack": 0.40,
    },

    "programming": {
        "programming": 1.00,
        "backend": 0.80,
        "frontend": 0.65,
        "fullstack": 0.75,
        "data": 0.65,
        "mobile": 0.70,
        "testing": 0.50,
        "devops": 0.45,
    },

    "version_control": {
        "version_control": 1.00,
        "frontend": 0.35,
        "backend": 0.35,
        "fullstack": 0.35,
        "devops": 0.60,
    },
}


def _get_skill_families(skills):
    families = set()

    normalized_skills = {
        _normalize_match_text(skill)
        for skill in skills
        if skill
    }

    for skill in normalized_skills:
        for family_name, family_skills in SKILL_FAMILIES.items():
            normalized_family_skills = {
                _normalize_match_text(item)
                for item in family_skills
            }

            if skill in normalized_family_skills:
                families.add(family_name)
                continue

            if any(
                family_skill in skill
                or skill in family_skill
                for family_skill in normalized_family_skills
                if family_skill
            ):
                families.add(family_name)

    return families


def calculate_skill_match(profile, job):
    profile_skills = _split_skill_values(profile.skills)
    job_skills = _split_skill_values(
        getattr(job, "skills", "")
    )

    if not job_skills or not profile_skills:
        return 0.0

    profile_families = _get_skill_families(
        profile_skills
    )

    total_score = 0.0

    for job_skill in job_skills:

        best_match = 0.0

        # Direct skill match.
        for profile_skill in profile_skills:

            if job_skill == profile_skill:
                best_match = max(
                    best_match,
                    1.0
                )

            elif (
                job_skill in profile_skill
                or profile_skill in job_skill
            ):
                best_match = max(
                    best_match,
                    0.92
                )

        # Related skill-family match.
        job_skill_families = _get_skill_families(
            {job_skill}
        )

        for job_family in job_skill_families:

            weights = RELATED_FAMILY_WEIGHTS.get(
                job_family,
                {}
            )

            for profile_family in profile_families:

                best_match = max(
                    best_match,
                    weights.get(
                        profile_family,
                        0.0
                    )
                )

        total_score += best_match

    return round(
        min(
            100.0,
            (total_score / len(job_skills)) * 100
        ),
        2
    )


def _profile_experience_text(profile):
    values = []

    for item in profile.experiences.all():
        values.extend([
            item.job_title or "",
            item.company or "",
            item.employment_type or "",
            item.description or "",
        ])

    return " ".join(values)


def _profile_education_text(profile):
    values = []

    for item in profile.educations.all():
        values.extend([
            item.degree or "",
            item.university or "",
            item.college or "",
            item.activities or "",
        ])

    return " ".join(values)


def _profile_project_text(profile):
    values = []

    for item in profile.projects.all():
        values.extend([
            item.name or "",
            item.project_type or "",
            item.technologies or "",
            item.description or "",
        ])

    return " ".join(values)


def _keyword_similarity(profile_text, job_text):
    profile_tokens = _tokenize_match_text(
        profile_text
    )

    job_tokens = _tokenize_match_text(
        job_text
    )

    if not job_tokens or not profile_tokens:
        return 0.0

    return round(
        (
            len(profile_tokens & job_tokens)
            / len(job_tokens)
        ) * 100,
        2
    )


# ============================================================
# ROLE MATCHING
# ============================================================

ROLE_FAMILIES = {
    "frontend": {
        "frontend developer",
        "front end developer",
        "frontend engineer",
        "ui developer",
        "web developer",
        "react developer",
        "javascript developer",
        "typescript developer",
        "angular developer",
        "vue developer",
    },

    "backend": {
        "backend developer",
        "back end developer",
        "backend engineer",
        "python developer",
        "django developer",
        "java developer",
        "spring boot developer",
        "node developer",
        "nodejs developer",
        "api developer",
    },

    "fullstack": {
        "full stack developer",
        "fullstack developer",
        "full stack engineer",
        "fullstack engineer",
        "web application developer",
        "software developer",
        "software engineer",
    },

    "data": {
        "data analyst",
        "data scientist",
        "machine learning engineer",
        "ml engineer",
        "ai engineer",
        "data engineer",
    },

    "testing": {
        "qa engineer",
        "qa tester",
        "software tester",
        "test engineer",
        "automation tester",
        "quality analyst",
    },

    "devops": {
        "devops engineer",
        "cloud engineer",
        "site reliability engineer",
        "sre",
    },

    "mobile": {
        "android developer",
        "ios developer",
        "mobile developer",
        "flutter developer",
        "react native developer",
    },

    "design": {
        "ui designer",
        "ux designer",
        "ui ux designer",
        "product designer",
        "graphic designer",
    },
}


ROLE_RELATIONSHIPS = {
    "frontend": {
        "frontend": 1.00,
        "fullstack": 0.88,
        "backend": 0.55,
        "design": 0.60,
    },

    "backend": {
        "backend": 1.00,
        "fullstack": 0.88,
        "frontend": 0.55,
        "devops": 0.50,
        "data": 0.45,
    },

    "fullstack": {
        "fullstack": 1.00,
        "frontend": 0.90,
        "backend": 0.90,
        "programming": 0.75,
        "devops": 0.50,
    },

    "data": {
        "data": 1.00,
        "backend": 0.45,
        "programming": 0.65,
        "database": 0.75,
    },

    "testing": {
        "testing": 1.00,
        "frontend": 0.45,
        "backend": 0.45,
        "fullstack": 0.45,
        "devops": 0.50,
    },

    "devops": {
        "devops": 1.00,
        "backend": 0.55,
        "fullstack": 0.55,
        "database": 0.45,
    },

    "mobile": {
        "mobile": 1.00,
        "frontend": 0.60,
        "fullstack": 0.45,
        "backend": 0.40,
    },

    "design": {
        "design": 1.00,
        "frontend": 0.65,
        "fullstack": 0.40,
    },
}


def _detect_role_families(text):
    normalized_text = _normalize_match_text(
        text
    )

    result = set()

    for family, role_names in ROLE_FAMILIES.items():

        for role_name in role_names:

            normalized_role = _normalize_match_text(
                role_name
            )

            if normalized_role in normalized_text:
                result.add(family)
                break

    # Explicit role keywords.
    if (
        "full stack" in normalized_text
        or "fullstack" in normalized_text
    ):
        result.add("fullstack")

    if (
        "frontend" in normalized_text
        or "front end" in normalized_text
    ):
        result.add("frontend")

    if (
        "backend" in normalized_text
        or "back end" in normalized_text
    ):
        result.add("backend")

    return result


def calculate_role_match(profile, job):

    profile_role_text = " ".join([
        profile.headline or "",
        _profile_experience_text(profile),
        _profile_project_text(profile),
        profile.skills or "",
    ])

    job_role_text = " ".join([
        str(
            getattr(
                job,
                "title",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "description",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "roles_responsibilities",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "skills",
                ""
            )
            or ""
        ),
    ])

    profile_roles = _detect_role_families(
        profile_role_text
    )

    job_roles = _detect_role_families(
        job_role_text
    )

    if not job_roles:
        return 50.0

    if not profile_roles:
        return 0.0

    best_score = 0.0

    for job_role in job_roles:

        weights = ROLE_RELATIONSHIPS.get(
            job_role,
            {}
        )

        for profile_role in profile_roles:

            best_score = max(
                best_score,
                weights.get(
                    profile_role,
                    0.0
                )
            )

    return round(
        best_score * 100,
        2
    )


# ============================================================
# EXPERIENCE MATCH
# ============================================================

def calculate_experience_match(profile, job):

    profile_text = _profile_experience_text(
        profile
    )

    if not profile_text.strip():
        return 0.0

    job_text = " ".join([
        str(
            getattr(
                job,
                "title",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "experience",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "minimum_experience",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "maximum_experience",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "description",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "roles_responsibilities",
                ""
            )
            or ""
        ),
    ])

    return _keyword_similarity(
        profile_text,
        job_text
    )


# ============================================================
# EDUCATION MATCH
# ============================================================

def calculate_education_match(profile, job):

    profile_text = _profile_education_text(
        profile
    )

    required_text = str(
        getattr(
            job,
            "education_details",
            ""
        )
        or ""
    )

    if not required_text.strip():
        return 100.0

    if not profile_text.strip():
        return 0.0

    return _keyword_similarity(
        profile_text,
        required_text
    )


# ============================================================
# PROFILE KEYWORD MATCH
# ============================================================

def calculate_profile_keyword_match(
    profile,
    job
):

    profile_text = " ".join([
        profile.headline or "",
        profile.skills or "",
        _profile_experience_text(profile),
        _profile_project_text(profile),
        _profile_education_text(profile),
    ])

    job_text = " ".join([
        str(
            getattr(
                job,
                "title",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "description",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "roles_responsibilities",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "skills",
                ""
            )
            or ""
        ),

        str(
            getattr(
                job,
                "education_details",
                ""
            )
            or ""
        ),
    ])

    return _keyword_similarity(
        profile_text,
        job_text
    )


# ============================================================
# FINAL AI MATCH SCORE
# ============================================================

def calculate_ai_match_score(
    profile,
    job
):

    skill_score = calculate_skill_match(
        profile,
        job
    )

    role_score = calculate_role_match(
        profile,
        job
    )

    keyword_score = calculate_profile_keyword_match(
        profile,
        job
    )

    experience_score = calculate_experience_match(
        profile,
        job
    )

    education_score = calculate_education_match(
        profile,
        job
    )

    # --------------------------------------------------------
    # WEIGHTS
    #
    # Skills       = 40%
    # Role         = 25%
    # Keywords     = 15%
    # Experience   = 12%
    # Education    = 8%
    # --------------------------------------------------------

    score = (
        skill_score * 0.40
        + role_score * 0.25
        + keyword_score * 0.15
        + experience_score * 0.12
        + education_score * 0.08
    )

    return round(
        max(
            0.0,
            min(
                100.0,
                score
            )
        ),
        2
    )


def _get_match_level(score):

    if score >= 85:
        return "Excellent Match"

    if score >= 70:
        return "Strong Match"

    if score >= 55:
        return "Good Match"

    if score >= 40:
        return "Related Match"

    return "Low Match"


def get_job_match_data(
    profile,
    job
):

    score = calculate_ai_match_score(
        profile,
        job
    )

    skill_score = calculate_skill_match(
        profile,
        job
    )

    role_score = calculate_role_match(
        profile,
        job
    )

    return {
        "ai_match_score": score,
        "match_score": score,
        "ai_match_threshold": AI_MATCH_THRESHOLD,
        "can_apply_by_match":
            score >= AI_MATCH_THRESHOLD,
        "match_level":
            _get_match_level(score),
        "skill_match_score":
            skill_score,
        "role_match_score":
            role_score,
    }


# ============================================================
# HELPER - SNAPSHOT PROFILE
# ============================================================

def snapshot_profile_fields(profile):
    """
    Take a snapshot of fields before updating.
    Used to detect changed profile fields.
    """

    snapshot = {}

    for field in TRACKED_PROFILE_FIELDS:

        value = getattr(
            profile,
            field,
            None
        )

        if hasattr(value, "name"):
            value = value.name

        snapshot[field] = value

    return snapshot


# ============================================================
# HELPER - GET CHANGED FIELDS
# ============================================================

def get_changed_fields(
    old_snapshot,
    new_snapshot
):

    changed = {}

    for field in TRACKED_PROFILE_FIELDS:

        old_value = old_snapshot.get(field)
        new_value = new_snapshot.get(field)

        if old_value != new_value:

            changed[field] = {
                "old": old_value,
                "new": new_value,
            }

    return changed


# ============================================================
# HELPER - NOTIFY ADMIN ABOUT JOBSEEKER PROFILE UPDATE
# ============================================================

def notify_admin_of_profile_update(
    profile,
    changed_fields
):

    if not changed_fields:
        return

    changed_labels = []

    for field in changed_fields.keys():

        changed_labels.append(
            FIELD_LABELS.get(
                field,
                field
            )
        )

    fields_text = ", ".join(
        changed_labels
    )

    message = (
        f"Job seeker {profile.full_name} "
        f"has updated their profile.\n\n"
        f"Updated fields:\n"
        f"{fields_text}\n\n"
        f"Approval status: "
        f"{profile.approval_status}"
    )

    # ========================================================
    # YOUR SINGLE ADMIN
    # ========================================================

    admin = User.objects.filter(
        is_staff=True,
        is_active=True
    ).first()

    if not admin:
        return

    # ========================================================
    # IN-APP NOTIFICATION
    # ========================================================

    Notification.objects.create(
        recipient=admin,
        title="Jobseeker Profile Updated",
        message=message,
        notification_type="PROFILE",
    )

    # ========================================================
    # EMAIL NOTIFICATION
    # ========================================================

    if admin.email:

        try:

            send_mail(
                subject="JobConnect - Profile Updated",
                message=message,
                from_email=None,
                recipient_list=[
                    admin.email
                ],
                fail_silently=True,
            )

        except Exception as error:

            print(
                "ADMIN EMAIL ERROR:",
                str(error)
            )


# ============================================================
# HELPER - BUILD COMPLETE PROFILE RESPONSE
# ============================================================

def build_profile_response(
    profile,
    request
):

    profile.refresh_from_db()

    serializer = JobSeekerProfileSerializer(
        profile,
        context={
            "request": request
        }
    )

    data = dict(
        serializer.data
    )

    # ========================================================
    # EDUCATION
    # ========================================================

    education = Education.objects.filter(
        jobseeker=profile
    ).order_by(
        "-start_year",
        "-id"
    )

    data["education"] = EducationSerializer(
        education,
        many=True,
        context={
            "request": request
        }
    ).data

    # ========================================================
    # EXPERIENCE
    # ========================================================

    experience = Experience.objects.filter(
        jobseeker=profile
    ).order_by(
        "-id"
    )

    data["experience"] = ExperienceSerializer(
        experience,
        many=True,
        context={
            "request": request
        }
    ).data

    # ========================================================
    # PROJECTS
    # ========================================================

    projects = Project.objects.filter(
        jobseeker=profile
    ).order_by(
        "-id"
    )

    data["projects"] = ProjectSerializer(
        projects,
        many=True,
        context={
            "request": request
        }
    ).data

    # ========================================================
    # DISABILITY
    # ========================================================

    data["disability"] = bool(
        profile.disability
    )

    data["disability_category"] = (
        profile.disability_category or ""
    )

    data["disability_type"] = (
        profile.disability_type or ""
    )

    data["disability_percentage"] = (
        profile.disability_percentage
        if profile.disability_percentage is not None
        else None
    )

    data["disability_details"] = {

        "has_disability": bool(
            profile.disability
        ),

        "category": (
            profile.disability_category or ""
        ),

        "type": (
            profile.disability_type or ""
        ),

        "percentage": (
            profile.disability_percentage
            if profile.disability_percentage is not None
            else None
        ),
    }

    # ========================================================
    # APPROVAL INFORMATION
    # ========================================================

    data["approval_status"] = (
        profile.approval_status
    )

    data["profile_completed"] = (
        profile.profile_completed
    )

    data["rejection_reason"] = (
        profile.rejection_reason or ""
    )

    data["can_edit"] = True

    data["can_submit"] = (
        profile.approval_status != "pending"
    )

    return data


# ============================================================
# SIGNUP
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class JobSeekerSignupView(APIView):

    permission_classes = [
        AllowAny
    ]

    authentication_classes = []

    def post(self, request):

        serializer = JobSeekerSignupSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message":
                    "Registration failed.",

                    "errors":
                    serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = serializer.save()

        return Response(
            {
                "message":
                "Job seeker registered successfully.",

                "user_id":
                user.id,
            },
            status=status.HTTP_201_CREATED
        )


# ============================================================
# LOGIN
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class JobSeekerLoginView(APIView):

    permission_classes = [
        AllowAny
    ]

    authentication_classes = []

    def post(self, request):

        email = (
            request.data.get("email")
            or ""
        ).strip()

        password = (
            request.data.get("password")
            or ""
        )

        if not email or not password:

            return Response(
                {
                    "message":
                    "Email and password are required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = None

        try:

            user_obj = User.objects.get(
                email__iexact=email
            )

            user = authenticate(
                username=user_obj.username,
                password=password
            )

        except User.DoesNotExist:

            user = None

        if user is None:

            return Response(
                {
                    "message":
                    "Invalid email or password."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:

            return Response(
                {
                    "message":
                    "Your account is inactive."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(
            user
        )

        profile = get_jobseeker_profile_by_user(
            user
        )

        response_data = {

            "message":
            "Login successful.",

            "access":
            str(refresh.access_token),

            "refresh":
            str(refresh),

            "user": {
                "id":
                user.id,

                "username":
                user.username,

                "email":
                user.email,
            },
        }

        if profile:

            response_data["profile"] = (
                build_profile_response(
                    profile,
                    request
                )
            )

        return Response(
            response_data,
            status=status.HTTP_200_OK
        )


# ============================================================
# GET CURRENT USER
# ============================================================

class CurrentUserView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def get(self, request):

        user = request.user

        profile = get_jobseeker_profile(
            request
        )

        data = {

            "id":
            user.id,

            "username":
            user.username,

            "email":
            user.email,

            "first_name":
            user.first_name,

            "last_name":
            user.last_name,
        }

        if profile:

            data["profile"] = (
                build_profile_response(
                    profile,
                    request
                )
            )

        return Response(
            data,
            status=status.HTTP_200_OK
        )


# ============================================================
# JOB SEEKER PROFILE
# GET + PATCH
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class JobSeekerProfileView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    # ========================================================
    # GET PROFILE
    # ========================================================

    def get(self, request):

        profile = get_jobseeker_profile(
            request
        )

        if profile is None:

            return Response(
                {
                    "message":
                    "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        profile.refresh_from_db()

        data = build_profile_response(
            profile,
            request
        )

        # Explicit disability information

        data["disability"] = bool(
            profile.disability
        )

        data["disability_category"] = (
            profile.disability_category or ""
        )

        data["disability_type"] = (
            profile.disability_type or ""
        )

        data["disability_percentage"] = (
            profile.disability_percentage
            if profile.disability_percentage is not None
            else None
        )

        data["disability_details"] = {

            "has_disability":
            bool(profile.disability),

            "category":
            profile.disability_category or "",

            "type":
            profile.disability_type or "",

            "percentage":
            profile.disability_percentage
            if profile.disability_percentage is not None
            else None,
        }

        # Approval/submission state

        data["approval_status"] = (
            profile.approval_status
        )

        data["profile_completed"] = (
            profile.profile_completed
        )

        data["can_edit"] = True

        data["can_submit"] = (
            profile.approval_status != "pending"
        )

        return Response(
            data,
            status=status.HTTP_200_OK
        )

    # ========================================================
    # PATCH PROFILE
    # ========================================================

    @transaction.atomic
    def patch(self, request):

        profile = get_jobseeker_profile(
            request
        )

        if profile is None:

            return Response(
                {
                    "message":
                    "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        profile.refresh_from_db()

        # ----------------------------------------------------
        # Keep old values for change tracking
        # ----------------------------------------------------

        old_snapshot = snapshot_profile_fields(
            profile
        )

        # ----------------------------------------------------
        # Copy incoming data
        # ----------------------------------------------------

        data = request.data.copy()

        # ----------------------------------------------------
        # DISABILITY NORMALIZATION
        # ----------------------------------------------------

        disability_was_sent = (
            "disability" in data
        )

        disability_value = (
            profile.disability
        )

        disability_category = (
            profile.disability_category or ""
        )

        disability_type = (
            profile.disability_type or ""
        )

        disability_percentage = (
            profile.disability_percentage
        )

        if disability_was_sent:

            raw_disability = data.get(
                "disability"
            )

            # Convert string/FormData values to boolean

            if isinstance(
                raw_disability,
                bool
            ):

                disability_value = (
                    raw_disability
                )

            else:

                disability_value = (
                    str(raw_disability)
                    .strip()
                    .lower()
                    in [
                        "true",
                        "1",
                        "yes",
                        "on"
                    ]
                )

            # ------------------------------------------------
            # PERSON HAS DISABILITY
            # ------------------------------------------------

            if disability_value:

                raw_category = data.get(
                    "disability_category",
                    ""
                )

                disability_category = (
                    str(raw_category).strip()
                    if raw_category is not None
                    else ""
                )

                if not disability_category:

                    return Response(
                        {
                            "message":
                            "Disability category is required.",

                            "errors": {
                                "disability_category": [
                                    "Please select a disability category."
                                ]
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                raw_type = data.get(
                    "disability_type",
                    ""
                )

                disability_type = (
                    str(raw_type).strip()
                    if raw_type is not None
                    else ""
                )

                if not disability_type:

                    return Response(
                        {
                            "message":
                            "Disability type is required.",

                            "errors": {
                                "disability_type": [
                                    "Please enter the type of disability."
                                ]
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                raw_percentage = data.get(
                    "disability_percentage",
                    ""
                )

                if (
                    raw_percentage is None
                    or str(
                        raw_percentage
                    ).strip() == ""
                ):

                    return Response(
                        {
                            "message":
                            "Disability percentage is required.",

                            "errors": {
                                "disability_percentage": [
                                    "Please enter the percentage of disability."
                                ]
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                try:

                    disability_percentage = int(
                        str(
                            raw_percentage
                        ).strip()
                    )

                except (
                    ValueError,
                    TypeError
                ):

                    return Response(
                        {
                            "message":
                            "Invalid disability percentage.",

                            "errors": {
                                "disability_percentage": [
                                    "Disability percentage must be a number."
                                ]
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if not (
                    1 <= disability_percentage <= 100
                ):

                    return Response(
                        {
                            "message":
                            "Invalid disability percentage.",

                            "errors": {
                                "disability_percentage": [
                                    "Disability percentage must be between 1 and 100."
                                ]
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Normalize data sent to serializer

                data["disability"] = True

                data["disability_category"] = (
                    disability_category
                )

                data["disability_type"] = (
                    disability_type
                )

                data["disability_percentage"] = (
                    disability_percentage
                )

            # ------------------------------------------------
            # PERSON DOES NOT HAVE DISABILITY
            # ------------------------------------------------

            else:

                disability_value = False
                disability_category = ""
                disability_type = ""
                disability_percentage = None

                data["disability"] = False

                data["disability_category"] = ""

                data["disability_type"] = ""

                data["disability_percentage"] = None

        # ----------------------------------------------------
        # SAVE PROFILE
        # ----------------------------------------------------

        serializer = JobSeekerProfileSerializer(
            profile,
            data=data,
            partial=True,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message":
                    "Profile validation failed.",

                    "errors":
                    serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        profile = serializer.save()

        # ----------------------------------------------------
        # EXPLICITLY SAVE DISABILITY VALUES
        # ----------------------------------------------------

        if disability_was_sent:

            profile.disability = (
                disability_value
            )

            profile.disability_category = (
                disability_category
            )

            profile.disability_type = (
                disability_type
            )

            profile.disability_percentage = (
                disability_percentage
            )

            profile.save(
                update_fields=[
                    "disability",
                    "disability_category",
                    "disability_type",
                    "disability_percentage",
                    "updated_at",
                ]
            )

        profile.refresh_from_db()

        # ----------------------------------------------------
        # IMPORTANT:
        # DO NOT CHANGE approval_status HERE
        # ----------------------------------------------------
        #
        # PATCH only edits the profile.
        #
        # SubmitProfileView is responsible for:
        #
        # profile_completed = True
        # approval_status = "pending"
        #
        # ----------------------------------------------------

        # ----------------------------------------------------
        # DETECT CHANGED FIELDS
        # ----------------------------------------------------

        new_snapshot = snapshot_profile_fields(
            profile
        )

        changed_fields = get_changed_fields(
            old_snapshot,
            new_snapshot
        )

        # ----------------------------------------------------
        # NOTIFY ADMIN OF PROFILE UPDATE
        # ----------------------------------------------------

        if changed_fields:

            try:

                notify_admin_of_profile_update(
                    profile,
                    changed_fields
                )

            except Exception as error:

                print(
                    "ADMIN NOTIFICATION ERROR:",
                    error
                )

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        response_data = build_profile_response(
            profile,
            request
        )

        response_data["disability"] = bool(
            profile.disability
        )

        response_data["disability_category"] = (
            profile.disability_category or ""
        )

        response_data["disability_type"] = (
            profile.disability_type or ""
        )

        response_data["disability_percentage"] = (
            profile.disability_percentage
            if profile.disability_percentage is not None
            else None
        )

        response_data["disability_details"] = {

            "has_disability":
            bool(profile.disability),

            "category":
            profile.disability_category or "",

            "type":
            profile.disability_type or "",

            "percentage":
            profile.disability_percentage
            if profile.disability_percentage is not None
            else None,
        }

        response_data["approval_status"] = (
            profile.approval_status
        )

        response_data["profile_completed"] = (
            profile.profile_completed
        )

        response_data["can_edit"] = True

        response_data["can_submit"] = (
            profile.approval_status != "pending"
        )

        response_data["updated_fields"] = list(
            changed_fields.keys()
        )

        response_data["message"] = (
            "Profile updated successfully."
        )

        return Response(
            response_data,
            status=status.HTTP_200_OK
        )


# ============================================================
# EDUCATION LIST + CREATE
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class EducationListCreateView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def get(self, request):

        profile = get_jobseeker_profile(
            request
        )

        if not profile:

            return Response(
                {
                    "message":
                    "Profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        education = Education.objects.filter(
            jobseeker=profile
        ).order_by(
            "-start_year",
            "-id"
        )

        serializer = EducationSerializer(
            education,
            many=True,
            context={
                "request": request
            }
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def post(self, request):

        profile = get_jobseeker_profile(
            request
        )

        if not profile:

            return Response(
                {
                    "message":
                    "Profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EducationSerializer(
            data=request.data,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        education = serializer.save(
            jobseeker=profile
        )

        return Response(
            EducationSerializer(
                education,
                context={
                    "request": request
                }
            ).data,
            status=status.HTTP_201_CREATED
        )


# ============================================================
# EDUCATION DETAIL
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class EducationDetailView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def get_object(
        self,
        request,
        pk
    ):

        profile = get_jobseeker_profile(
            request
        )

        if not profile:
            return None

        try:

            return Education.objects.get(
                id=pk,
                jobseeker=profile
            )

        except Education.DoesNotExist:

            return None

    def put(
        self,
        request,
        pk
    ):

        education = self.get_object(
            request,
            pk
        )

        if not education:

            return Response(
                {
                    "message":
                    "Education not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EducationSerializer(
            education,
            data=request.data,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        education = serializer.save()

        return Response(
            EducationSerializer(
                education,
                context={
                    "request": request
                }
            ).data,
            status=status.HTTP_200_OK
        )

    def patch(
        self,
        request,
        pk
    ):

        education = self.get_object(
            request,
            pk
        )

        if not education:

            return Response(
                {
                    "message":
                    "Education not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EducationSerializer(
            education,
            data=request.data,
            partial=True,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        education = serializer.save()

        return Response(
            EducationSerializer(
                education,
                context={
                    "request": request
                }
            ).data,
            status=status.HTTP_200_OK
        )

    def delete(
        self,
        request,
        pk
    ):

        education = self.get_object(
            request,
            pk
        )

        if not education:

            return Response(
                {
                    "message":
                    "Education not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        education.delete()

        return Response(
            {
                "message":
                "Education deleted successfully."
            },
            status=status.HTTP_204_NO_CONTENT
        )


# ============================================================
# EXPERIENCE LIST + CREATE
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class ExperienceListCreateView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def get(self, request):

        profile = get_jobseeker_profile(
            request
        )

        if not profile:

            return Response(
                {
                    "message":
                    "Profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        experiences = Experience.objects.filter(
            jobseeker=profile
        ).order_by(
            "-id"
        )

        serializer = ExperienceSerializer(
            experiences,
            many=True,
            context={
                "request": request
            }
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def post(self, request):

        profile = get_jobseeker_profile(
            request
        )

        if not profile:

            return Response(
                {
                    "message":
                    "Profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ExperienceSerializer(
            data=request.data,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        experience = serializer.save(
            jobseeker=profile
        )

        return Response(
            ExperienceSerializer(
                experience,
                context={
                    "request": request
                }
            ).data,
            status=status.HTTP_201_CREATED
        )


# ============================================================
# EXPERIENCE DETAIL
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class ExperienceDetailView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def get_object(
        self,
        request,
        pk
    ):

        profile = get_jobseeker_profile(
            request
        )

        if not profile:
            return None

        try:

            return Experience.objects.get(
                id=pk,
                jobseeker=profile
            )

        except Experience.DoesNotExist:

            return None

    def put(
        self,
        request,
        pk
    ):

        experience = self.get_object(
            request,
            pk
        )

        if not experience:

            return Response(
                {
                    "message":
                    "Experience not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ExperienceSerializer(
            experience,
            data=request.data,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        experience = serializer.save()

        return Response(
            ExperienceSerializer(
                experience,
                context={
                    "request": request
                }
            ).data,
            status=status.HTTP_200_OK
        )

    def patch(
        self,
        request,
        pk
    ):

        experience = self.get_object(
            request,
            pk
        )

        if not experience:

            return Response(
                {
                    "message":
                    "Experience not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ExperienceSerializer(
            experience,
            data=request.data,
            partial=True,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        experience = serializer.save()

        return Response(
            ExperienceSerializer(
                experience,
                context={
                    "request": request
                }
            ).data,
            status=status.HTTP_200_OK
        )

    def delete(
        self,
        request,
        pk
    ):

        experience = self.get_object(
            request,
            pk
        )

        if not experience:

            return Response(
                {
                    "message":
                    "Experience not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        experience.delete()

        return Response(
            {
                "message":
                "Experience deleted successfully."
            },
            status=status.HTTP_204_NO_CONTENT
        )



# ============================================================
# PROJECT LIST + CREATE
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class ProjectListCreateView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    # ========================================================
    # GET PROJECTS
    # ========================================================

    def get(self, request):

        profile = get_jobseeker_profile(request)

        if not profile:

            return Response(
                {
                    "message": "Profile not found.",
                    "projects": [],
                },
                status=status.HTTP_404_NOT_FOUND
            )

        projects = (
            Project.objects
            .filter(jobseeker=profile)
            .order_by("-id")
        )

        serializer = ProjectSerializer(
            projects,
            many=True,
            context={
                "request": request
            }
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # ========================================================
    # CREATE PROJECT
    # ========================================================

    @transaction.atomic
    def post(self, request):

        profile = get_jobseeker_profile(request)

        if not profile:

            return Response(
                {
                    "message":
                    "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # ----------------------------------------------------
        # COPY REQUEST DATA
        # ----------------------------------------------------

        data = request.data.copy()

        # ----------------------------------------------------
        # NORMALIZE STRING VALUES
        # ----------------------------------------------------

        string_fields = [
            "name",
            "project_type",
            "technologies",
            "project_url",
            "description",
        ]

        for field in string_fields:

            if field in data:

                value = data.get(field)

                if value is None:

                    data[field] = ""

                else:

                    data[field] = str(value).strip()

        # ----------------------------------------------------
        # PROJECT NAME IS REQUIRED
        # ----------------------------------------------------

        if not data.get("name"):

            return Response(
                {
                    "message":
                    "Project name is required.",

                    "errors": {
                        "name": [
                            "Project name is required."
                        ]
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------------------------
        # REMOVE EMPTY OPTIONAL VALUES
        #
        # This prevents serializers with URL/choice fields
        # from receiving unnecessary empty strings.
        # ----------------------------------------------------

        optional_fields = [
            "project_type",
            "technologies",
            "project_url",
            "description",
        ]

        for field in optional_fields:

            if field in data:

                value = data.get(field)

                if value in ["", None]:

                    data.pop(field, None)

        # ----------------------------------------------------
        # VALIDATE PROJECT URL IF PROVIDED
        # ----------------------------------------------------

        project_url = data.get("project_url")

        if project_url:

            project_url = str(
                project_url
            ).strip()

            # Allow users to enter:
            #
            # example.com
            # www.example.com
            # https://example.com
            # http://example.com

            if (
                not project_url.startswith("http://")
                and not project_url.startswith("https://")
            ):

                project_url = (
                    "https://"
                    + project_url
                )

            data["project_url"] = project_url

        # ----------------------------------------------------
        # SERIALIZER
        # ----------------------------------------------------

        serializer = ProjectSerializer(
            data=data,
            context={
                "request": request
            }
        )

        # ----------------------------------------------------
        # VALIDATION ERROR
        # ----------------------------------------------------

        if not serializer.is_valid():

            return Response(
                {
                    "message":
                    "Project validation failed.",

                    "errors":
                    serializer.errors,

                    # Useful while debugging frontend/backend
                    # field-name mismatches.
                    "received_data":
                    {
                        key: value
                        for key, value in data.items()
                    },
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------------------------
        # SAVE PROJECT
        # ----------------------------------------------------

        project = serializer.save(
            jobseeker=profile
        )

        project.refresh_from_db()

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        response_data = ProjectSerializer(
            project,
            context={
                "request": request
            }
        ).data

        return Response(
            {
                "message":
                "Project created successfully.",

                "project":
                response_data,

                # Keep this available for frontends that
                # expect the project object directly.
                "data":
                response_data,
            },
            status=status.HTTP_201_CREATED
        )


# ============================================================
# PROJECT DETAIL
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class ProjectDetailView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    # ========================================================
    # GET OBJECT
    # ========================================================

    def get_object(
        self,
        request,
        pk
    ):

        profile = get_jobseeker_profile(request)

        if not profile:
            return None

        try:

            return Project.objects.get(
                id=pk,
                jobseeker=profile
            )

        except Project.DoesNotExist:

            return None

    # ========================================================
    # GET SINGLE PROJECT
    # ========================================================

    def get(
        self,
        request,
        pk
    ):

        project = self.get_object(
            request,
            pk
        )

        if not project:

            return Response(
                {
                    "message":
                    "Project not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ProjectSerializer(
            project,
            context={
                "request": request
            }
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    # ========================================================
    # PUT PROJECT
    # ========================================================

    @transaction.atomic
    def put(
        self,
        request,
        pk
    ):

        project = self.get_object(
            request,
            pk
        )

        if not project:

            return Response(
                {
                    "message":
                    "Project not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        data = request.data.copy()

        string_fields = [
            "name",
            "project_type",
            "technologies",
            "project_url",
            "description",
        ]

        for field in string_fields:

            if field in data:

                value = data.get(field)

                if value is None:

                    data[field] = ""

                else:

                    data[field] = str(value).strip()

        if not data.get("name"):

            return Response(
                {
                    "message":
                    "Project name is required.",

                    "errors": {
                        "name": [
                            "Project name is required."
                        ]
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        project_url = data.get(
            "project_url"
        )

        if project_url:

            project_url = str(
                project_url
            ).strip()

            if (
                not project_url.startswith("http://")
                and not project_url.startswith("https://")
            ):

                project_url = (
                    "https://"
                    + project_url
                )

            data["project_url"] = project_url

        serializer = ProjectSerializer(
            project,
            data=data,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message":
                    "Project validation failed.",

                    "errors":
                    serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        project = serializer.save()

        project.refresh_from_db()

        response_data = ProjectSerializer(
            project,
            context={
                "request": request
            }
        ).data

        return Response(
            {
                "message":
                "Project updated successfully.",

                "project":
                response_data,

                "data":
                response_data,
            },
            status=status.HTTP_200_OK
        )

    # ========================================================
    # PATCH PROJECT
    # ========================================================

    @transaction.atomic
    def patch(
        self,
        request,
        pk
    ):

        project = self.get_object(
            request,
            pk
        )

        if not project:

            return Response(
                {
                    "message":
                    "Project not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        data = request.data.copy()

        string_fields = [
            "name",
            "project_type",
            "technologies",
            "project_url",
            "description",
        ]

        for field in string_fields:

            if field in data:

                value = data.get(field)

                if value is None:

                    data[field] = ""

                else:

                    data[field] = str(value).strip()

        # ----------------------------------------------------
        # Validate name only if it was supplied
        # ----------------------------------------------------

        if (
            "name" in data
            and not data.get("name")
        ):

            return Response(
                {
                    "message":
                    "Project name is required.",

                    "errors": {
                        "name": [
                            "Project name is required."
                        ]
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------------------------
        # Normalize URL
        # ----------------------------------------------------

        if data.get("project_url"):

            project_url = str(
                data.get("project_url")
            ).strip()

            if (
                not project_url.startswith("http://")
                and not project_url.startswith("https://")
            ):

                project_url = (
                    "https://"
                    + project_url
                )

            data["project_url"] = project_url

        serializer = ProjectSerializer(
            project,
            data=data,
            partial=True,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message":
                    "Project validation failed.",

                    "errors":
                    serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        project = serializer.save()

        project.refresh_from_db()

        response_data = ProjectSerializer(
            project,
            context={
                "request": request
            }
        ).data

        return Response(
            {
                "message":
                "Project updated successfully.",

                "project":
                response_data,

                "data":
                response_data,
            },
            status=status.HTTP_200_OK
        )

    # ========================================================
    # DELETE PROJECT
    # ========================================================

    @transaction.atomic
    def delete(
        self,
        request,
        pk
    ):

        project = self.get_object(
            request,
            pk
        )

        if not project:

            return Response(
                {
                    "message":
                    "Project not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        project.delete()

        return Response(
            {
                "message":
                "Project deleted successfully.",

                "project_id":
                pk,
            },
            status=status.HTTP_200_OK
        )



# ============================================================
# SUBMIT PROFILE FOR APPROVAL
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class SubmitProfileView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    @transaction.atomic
    def post(self, request):

        profile = get_jobseeker_profile(
            request
        )

        if not profile:

            return Response(
                {
                    "message":
                    "Job seeker profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        profile.refresh_from_db()

        # =====================================================
        # ALREADY PENDING
        # =====================================================

        if (
            profile.profile_completed
            and profile.approval_status == "pending"
        ):

            return Response(
                {
                    "message":
                    "Your profile is already submitted "
                    "and is waiting for admin approval.",

                    "approval_status":
                    "pending",

                    "profile_completed":
                    profile.profile_completed,

                    "can_submit":
                    False,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        errors = {}

        # =====================================================
        # BASIC PROFILE VALIDATION
        # =====================================================

        if not (
            profile.full_name or ""
        ).strip():

            errors["full_name"] = (
                "Full name is required."
            )

        if not (
            profile.phone or ""
        ).strip():

            errors["phone"] = (
                "Phone number is required."
            )

        if not (
            profile.location or ""
        ).strip():

            errors["location"] = (
                "Location is required."
            )

        if not (
            profile.headline or ""
        ).strip():

            errors["headline"] = (
                "Headline is required."
            )

        if not (
            profile.skills or ""
        ).strip():

            errors["skills"] = (
                "Skills are required."
            )

        # =====================================================
        # DISABILITY VALIDATION
        # =====================================================

        if profile.disability:

            if not (
                profile.disability_category
                and profile.disability_category.strip()
            ):

                errors["disability_category"] = (
                    "Disability category is required."
                )

            if not (
                profile.disability_type
                and profile.disability_type.strip()
            ):

                errors["disability_type"] = (
                    "Disability type is required."
                )

            if (
                profile.disability_percentage
                is None
            ):

                errors["disability_percentage"] = (
                    "Disability percentage is required."
                )

            elif not (
                1
                <= profile.disability_percentage
                <= 100
            ):

                errors["disability_percentage"] = (
                    "Disability percentage must be "
                    "between 1 and 100."
                )

        # =====================================================
        # REQUIRED DOCUMENTS
        # =====================================================

        if not profile.profile_photo:

            errors["profile_photo"] = (
                "Profile photo is required."
            )

        if not profile.resume:

            errors["resume"] = (
                "Resume is required."
            )

        if not profile.aadhaar:

            errors["aadhaar"] = (
                "Aadhaar document is required."
            )

        # =====================================================
        # STOP IF PROFILE IS INCOMPLETE
        # =====================================================

        if errors:

            return Response(
                {
                    "message":
                    "Please complete your profile "
                    "before submitting.",

                    "errors":
                    errors,

                    "profile_completed":
                    profile.profile_completed,

                    "approval_status":
                    profile.approval_status,

                    "can_submit":
                    True,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # SUBMIT
        # =====================================================

        previous_status = (
            profile.approval_status
        )

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

        profile.refresh_from_db()

        # =====================================================
        # NOTIFICATION
        # =====================================================

        if previous_status == "approved":

            notification_message = (
                "Your updated profile has been "
                "submitted again for admin approval."
            )

        else:

            notification_message = (
                "Your profile has been submitted "
                "for admin approval."
            )

        Notification.objects.create(
            recipient=profile.user,
            title="Profile Submitted",
            message=notification_message,
            notification_type="ADMIN",
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        data = build_profile_response(
            profile,
            request
        )

        data["message"] = (
            "Profile submitted successfully "
            "for admin approval."
        )

        data["approval_status"] = "pending"

        data["profile_completed"] = True

        data["can_submit"] = False

        return Response(
            data,
            status=status.HTTP_200_OK
        )



# ============================================================
# JOB LIST
# ============================================================

class JobListView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):

        try:
            profile = get_jobseeker_profile(request)

            if not profile:
                return Response(
                    {"message": "Job seeker profile not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Only jobs that are currently open for applications.
            jobs = (
                Job.objects
                .select_related("employer")
                .filter(
                    status="live",
                    is_active=True,
                )
                .order_by("-id")
            )

            result = []

            def split_list(value):
                if value is None:
                    return []
                if isinstance(value, (list, tuple)):
                    return [str(item).strip() for item in value if str(item).strip()]
                return [
                    item.strip()
                    for item in re.split(r"[,;\n|]+", str(value))
                    if item.strip()
                ]

            for job in jobs:

                employer = getattr(job, "employer", None)
                company_name = (
                    getattr(employer, "company_name", "")
                    if employer
                    else ""
                ) or ""

                try:
                    job_type_display = job.get_job_type_display()
                except Exception:
                    job_type_display = getattr(job, "job_type", "") or ""

                try:
                    work_mode_display = job.get_work_mode_display()
                except Exception:
                    work_mode_display = getattr(job, "work_mode", "") or ""

                try:
                    experience_display = job.get_experience_display()
                except Exception:
                    experience_display = getattr(job, "experience", "") or ""

                salary_min = getattr(job, "salary_min", None)
                salary_max = getattr(job, "salary_max", None)

                if salary_min is not None and salary_max is not None:
                    salary_display = f"₹{salary_min} - ₹{salary_max}"
                elif salary_min is not None:
                    salary_display = f"₹{salary_min}+"
                elif salary_max is not None:
                    salary_display = f"Up to ₹{salary_max}"
                else:
                    salary_display = ""

                skills = split_list(getattr(job, "skills", ""))
                responsibilities = split_list(
                    getattr(job, "roles_responsibilities", "")
                )
                features = split_list(
                    getattr(job, "key_features", "")
                )

                minimum_experience = getattr(
                    job, "minimum_experience", None
                )
                maximum_experience = getattr(
                    job, "maximum_experience", None
                )

                match_data = get_job_match_data(profile, job)

                result.append(
                    {
                        "id": job.id,
                        "job_id": job.id,

                        "title": job.title or "",
                        "job_title": job.title or "",
                        "description": job.description or "",
                        "job_description": job.description or "",
                        "location": job.location or "",
                        "job_location": job.location or "",

                        "company": company_name,
                        "company_name": company_name,
                        "employer_name": company_name,

                        "job_type": getattr(job, "job_type", "") or "",
                        "job_type_display": job_type_display,
                        "employment_type": job_type_display,

                        "work_mode": getattr(job, "work_mode", "") or "",
                        "work_mode_display": work_mode_display,
                        "workplace_type": work_mode_display,

                        "salary": salary_display,
                        "salary_display": salary_display,
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "min_salary": salary_min,
                        "max_salary": salary_max,

                        "experience": experience_display,
                        "experience_display": experience_display,
                        "minimum_experience": minimum_experience,
                        "maximum_experience": maximum_experience,
                        "min_experience": minimum_experience,
                        "max_experience": maximum_experience,

                        "education": job.education_details or "",
                        "education_details": job.education_details or "",
                        "qualification": job.education_details or "",

                        "skills": skills,
                        "required_skills": skills,

                        "roles_responsibilities": responsibilities,
                        "responsibilities": responsibilities,

                        "key_features": features,
                        "features": features,
                        "benefits": features,

                        "created_at": job.created_at,
                        "posted_at": job.created_at,
                        "published_at": job.created_at,

                        "status": job.status,
                        "is_active": job.is_active,
                        "is_disability_job": bool(getattr(job, "is_disability_job", False)),
                        "is_published": True,

                        **match_data,
                    }
                )

            return Response(
                result,
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            print("JOB LIST ERROR:", str(e))
            return Response(
                {
                    "message": "Unable to load jobs.",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ============================================================
# APPLY FOR JOB
# ============================================================

@method_decorator(csrf_exempt, name="dispatch")
class ApplyJobView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request, job_id):

        profile = get_jobseeker_profile(request)

        if not profile:
            return Response(
                {"message": "Job seeker profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        profile.refresh_from_db()

        # Profile must be fully completed first.
        if not profile.profile_completed:
            return Response(
                {
                    "message": (
                        "Please complete your jobseeker profile "
                        "before applying."
                    ),
                    "approval_status": profile.approval_status,
                    "profile_completed": False,
                    "can_apply": False,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Admin approval is mandatory.
        approval_status = (
            profile.approval_status or ""
        ).strip().lower()

        if approval_status != "approved":
            if approval_status == "pending":
                message = (
                    "Your jobseeker profile is waiting for admin "
                    "approval. You cannot apply for jobs until "
                    "your profile is approved."
                )
            elif approval_status == "rejected":
                message = (
                    "Your jobseeker profile was rejected. Please "
                    "update your profile and submit it again for approval."
                )
            else:
                message = (
                    "Your jobseeker profile is not approved for job applications."
                )

            return Response(
                {
                    "message": message,
                    "approval_status": profile.approval_status,
                    "profile_completed": profile.profile_completed,
                    "can_apply": False,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            job = (
                Job.objects
                .select_related("employer")
                .get(id=job_id)
            )
        except Job.DoesNotExist:
            return Response(
                {"message": "Job not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Closed/inactive jobs cannot receive applications.
        if job.status != "live" or not job.is_active:
            return Response(
                {
                    "message": "This job is no longer open for applications.",
                    "job_status": job.status,
                    "is_active": job.is_active,
                    "can_apply": False,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # AI match threshold.
        match_data = get_job_match_data(profile, job)
        match_score = match_data["ai_match_score"]

        if match_score < AI_MATCH_THRESHOLD:
            return Response(
                {
                    "message": (
                        f"Your AI job match score is {match_score}%. "
                        f"You need at least {AI_MATCH_THRESHOLD}% to apply for this job."
                    ),
                    "ai_match_score": match_score,
                    "match_score": match_score,
                    "ai_match_threshold": AI_MATCH_THRESHOLD,
                    "can_apply_by_match": False,
                    "can_apply": False,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        existing = (
            JobApplication.objects
            .filter(jobseeker=profile, job=job)
            .first()
        )

        if existing:
            return Response(
                {
                    "message": "You have already applied for this job.",
                    "application_id": existing.id,
                    "status": existing.status,
                    "ai_match_score": match_score,
                    "can_apply": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        application = JobApplication.objects.create(
            jobseeker=profile,
            job=job,
            status="APPLIED",
        )

        return Response(
            {
                "message": "Job application submitted successfully.",
                "application_id": application.id,
                "status": application.status,
                "ai_match_score": match_score,
                "ai_match_threshold": AI_MATCH_THRESHOLD,
                "can_apply": True,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# MY APPLICATIONS
# ============================================================

class MyApplicationsView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def get(self, request):

        profile = get_jobseeker_profile(
            request
        )

        if not profile:

            return Response(
                {
                    "message":
                    "Profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        applications = (
            JobApplication.objects
            .filter(
                jobseeker=profile
            )
            .select_related(
                "job",
                "job__employer"
            )
            .order_by(
                "-applied_at"
            )
        )

        result = []

        for application in applications:

            job = application.job

            employer = getattr(
                job,
                "employer",
                None
            )

            company_name = ""

            if employer:

                company_name = (
                    getattr(
                        employer,
                        "company_name",
                        ""
                    )
                    or ""
                )

            # ====================================================
            # JOB TYPE DISPLAY
            # ====================================================

            try:

                job_type_display = (
                    job.get_job_type_display()
                )

            except Exception:

                job_type_display = (
                    getattr(
                        job,
                        "job_type",
                        ""
                    )
                    or ""
                )

            # ====================================================
            # WORK MODE DISPLAY
            # ====================================================

            try:

                work_mode_display = (
                    job.get_work_mode_display()
                )

            except Exception:

                work_mode_display = (
                    getattr(
                        job,
                        "work_mode",
                        ""
                    )
                    or ""
                )

            # ====================================================
            # EXPERIENCE DISPLAY
            # ====================================================

            try:

                experience_display = (
                    job.get_experience_display()
                )

            except Exception:

                experience_display = (
                    getattr(
                        job,
                        "experience",
                        ""
                    )
                    or ""
                )

            # ====================================================
            # SALARY
            # ====================================================

            salary_min = getattr(
                job,
                "salary_min",
                None
            )

            salary_max = getattr(
                job,
                "salary_max",
                None
            )

            if (
                salary_min is not None
                and salary_max is not None
            ):

                salary_display = (
                    f"₹{salary_min} - ₹{salary_max}"
                )

            elif salary_min is not None:

                salary_display = (
                    f"₹{salary_min}+"
                )

            elif salary_max is not None:

                salary_display = (
                    f"Up to ₹{salary_max}"
                )

            else:

                salary_display = ""

            # ====================================================
            # SKILLS
            # ====================================================

            raw_skills = getattr(
                job,
                "skills",
                ""
            )

            if isinstance(
                raw_skills,
                (list, tuple)
            ):

                skills = [
                    str(item).strip()
                    for item in raw_skills
                    if str(item).strip()
                ]

            else:

                skills = [
                    item.strip()
                    for item in re.split(
                        r"[,;\n|]+",
                        str(raw_skills or "")
                    )
                    if item.strip()
                ]

            # ====================================================
            # RESPONSIBILITIES
            # ====================================================

            raw_responsibilities = getattr(
                job,
                "roles_responsibilities",
                ""
            )

            if isinstance(
                raw_responsibilities,
                (list, tuple)
            ):

                responsibilities = [
                    str(item).strip()
                    for item in raw_responsibilities
                    if str(item).strip()
                ]

            else:

                responsibilities = [
                    item.strip()
                    for item in re.split(
                        r"[,;\n|]+",
                        str(raw_responsibilities or "")
                    )
                    if item.strip()
                ]

            # ====================================================
            # KEY FEATURES
            # ====================================================

            raw_features = getattr(
                job,
                "key_features",
                ""
            )

            if isinstance(
                raw_features,
                (list, tuple)
            ):

                features = [
                    str(item).strip()
                    for item in raw_features
                    if str(item).strip()
                ]

            else:

                features = [
                    item.strip()
                    for item in re.split(
                        r"[,;\n|]+",
                        str(raw_features or "")
                    )
                    if item.strip()
                ]

            # ====================================================
            # FULL JOB DATA
            # ====================================================

            job_details = {

                "id":
                job.id,

                "job_id":
                job.id,

                "title":
                getattr(
                    job,
                    "title",
                    ""
                ) or "",

                "job_title":
                getattr(
                    job,
                    "title",
                    ""
                ) or "",

                "description":
                getattr(
                    job,
                    "description",
                    ""
                ) or "",

                "job_description":
                getattr(
                    job,
                    "description",
                    ""
                ) or "",

                "location":
                getattr(
                    job,
                    "location",
                    ""
                ) or "",

                "job_location":
                getattr(
                    job,
                    "location",
                    ""
                ) or "",

                "company":
                company_name,

                "company_name":
                company_name,

                "employer_name":
                company_name,

                # ------------------------------------------------
                # JOB TYPE
                # ------------------------------------------------

                "job_type":
                getattr(
                    job,
                    "job_type",
                    ""
                ) or "",

                "job_type_display":
                job_type_display,

                "employment_type":
                job_type_display,

                # ------------------------------------------------
                # WORK MODE
                # ------------------------------------------------

                "work_mode":
                getattr(
                    job,
                    "work_mode",
                    ""
                ) or "",

                "work_mode_display":
                work_mode_display,

                "workplace_type":
                work_mode_display,

                # ------------------------------------------------
                # EXPERIENCE
                # ------------------------------------------------

                "experience":
                getattr(
                    job,
                    "experience",
                    ""
                ) or "",

                "experience_display":
                experience_display,

                "minimum_experience":
                getattr(
                    job,
                    "minimum_experience",
                    None
                ),

                "maximum_experience":
                getattr(
                    job,
                    "maximum_experience",
                    None
                ),

                "min_experience":
                getattr(
                    job,
                    "minimum_experience",
                    None
                ),

                "max_experience":
                getattr(
                    job,
                    "maximum_experience",
                    None
                ),

                # ------------------------------------------------
                # SALARY
                # ------------------------------------------------

                "salary":
                salary_display,

                "salary_display":
                salary_display,

                "salary_min":
                salary_min,

                "salary_max":
                salary_max,

                "min_salary":
                salary_min,

                "max_salary":
                salary_max,

                # ------------------------------------------------
                # EDUCATION
                # ------------------------------------------------

                "education":
                getattr(
                    job,
                    "education_details",
                    ""
                ) or "",

                "education_details":
                getattr(
                    job,
                    "education_details",
                    ""
                ) or "",

                "qualification":
                getattr(
                    job,
                    "education_details",
                    ""
                ) or "",

                # ------------------------------------------------
                # SKILLS
                # ------------------------------------------------

                "skills":
                skills,

                "required_skills":
                skills,

                # ------------------------------------------------
                # RESPONSIBILITIES
                # ------------------------------------------------

                "roles_responsibilities":
                responsibilities,

                "responsibilities":
                responsibilities,

                # ------------------------------------------------
                # FEATURES
                # ------------------------------------------------

                "key_features":
                features,

                "features":
                features,

                "benefits":
                features,

                # ------------------------------------------------
                # JOB STATUS
                # ------------------------------------------------

                "status":
                getattr(
                    job,
                    "status",
                    ""
                ) or "",

                "is_active":
                getattr(
                    job,
                    "is_active",
                    False
                ),

                "is_disability_job":
                bool(
                    getattr(
                        job,
                        "is_disability_job",
                        False
                    )
                ),

                # ------------------------------------------------
                # DATES
                # ------------------------------------------------

                "created_at":
                getattr(
                    job,
                    "created_at",
                    None
                ),

                "posted_at":
                getattr(
                    job,
                    "created_at",
                    None
                ),

                "published_at":
                getattr(
                    job,
                    "created_at",
                    None
                ),
            }

            # ====================================================
            # APPLICATION DATA
            # ====================================================

            result.append(

                {
                    # --------------------------------------------
                    # APPLICATION
                    # --------------------------------------------

                    "id":
                    application.id,

                    "application_id":
                    application.id,

                    "status":
                    application.status,

                    "application_status":
                    application.status,

                    "applied_at":
                    application.applied_at,

                    # --------------------------------------------
                    # BASIC JOB DATA
                    # --------------------------------------------

                    "job_id":
                    job.id,

                    "job_title":
                    getattr(
                        job,
                        "title",
                        ""
                    ) or "",

                    "location":
                    getattr(
                        job,
                        "location",
                        ""
                    ) or "",

                    "company":
                    company_name,

                    "company_name":
                    company_name,

                    # --------------------------------------------
                    # COMPLETE JOB OBJECT
                    # --------------------------------------------

                    "job":
                    job_details,

                    # --------------------------------------------
                    # EXPLICIT JOB DETAILS OBJECT
                    # --------------------------------------------

                    "job_details":
                    job_details,
                }
            )

        return Response(
            result,
            status=status.HTTP_200_OK
        )
    

# ============================================================
# NOTIFICATION LIST VIEW
# ============================================================

class NotificationListView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def get(self, request):

        notifications = (
            Notification.objects.filter(
                recipient=request.user
            )
            .order_by(
                "-created_at"
            )
        )

        data = []

        for notification in notifications:

            data.append(
                {
                    "id":
                    notification.id,

                    "title":
                    notification.title,

                    "message":
                    notification.message,

                    "notification_type":
                    notification.notification_type,

                    "notification_type_display":
                    (
                        notification
                        .get_notification_type_display()
                    ),

                    "is_read":
                    notification.is_read,

                    "created_at":
                    notification.created_at,
                }
            )

        unread_count = (
            Notification.objects.filter(
                recipient=request.user,
                is_read=False
            ).count()
        )

        return Response(
            {
                "notifications":
                data,

                "unread_count":
                unread_count,
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# NOTIFICATION DETAIL / MARK AS READ
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class NotificationReadView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def patch(
        self,
        request,
        notification_id
    ):

        try:

            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )

        except Notification.DoesNotExist:

            return Response(
                {
                    "message":
                    "Notification not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        notification.is_read = True

        notification.save(
            update_fields=[
                "is_read"
            ]
        )

        return Response(
            {
                "message":
                "Notification marked as read.",

                "notification": {

                    "id":
                    notification.id,

                    "title":
                    notification.title,

                    "message":
                    notification.message,

                    "notification_type":
                    notification.notification_type,

                    "notification_type_display":
                    (
                        notification
                        .get_notification_type_display()
                    ),

                    "is_read":
                    notification.is_read,

                    "created_at":
                    notification.created_at,
                }
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# FORGOT PASSWORD
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class ForgotPasswordView(APIView):

    permission_classes = [
        AllowAny
    ]

    authentication_classes = []

    def post(self, request):

        email = (
            request.data.get("email")
            or ""
        ).strip().lower()

        if not email:

            return Response(
                {
                    "message":
                    "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            user = User.objects.get(
                email__iexact=email
            )

        except User.DoesNotExist:

            return Response(
                {
                    "message":
                    "No account found with this email."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        otp = str(
            random.randint(
                100000,
                999999
            )
        )

        request.session[
            "password_reset_otp"
        ] = otp

        request.session[
            "password_reset_email"
        ] = email

        request.session[
            "password_reset_otp_created"
        ] = timezone.now().isoformat()

        try:

            send_mail(
                subject="JobConnect Password Reset OTP",

                message=(
                    f"Your JobConnect password reset "
                    f"OTP is {otp}. "
                    f"The OTP is valid for 10 minutes."
                ),

                from_email=None,

                recipient_list=[
                    email
                ],

                fail_silently=False,
            )

        except Exception as e:

            print(
                "PASSWORD RESET EMAIL ERROR:",
                str(e)
            )

            return Response(
                {
                    "message":
                    "Unable to send OTP email.",

                    "error":
                    str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {
                "message":
                "OTP sent successfully."
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# VERIFY OTP
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class VerifyOTPView(APIView):

    permission_classes = [
        AllowAny
    ]

    authentication_classes = []

    def post(self, request):

        otp = (
            request.data.get("otp")
            or ""
        ).strip()

        saved_otp = (
            request.session.get(
                "password_reset_otp"
            )
        )

        created_string = (
            request.session.get(
                "password_reset_otp_created"
            )
        )

        if not saved_otp:

            return Response(
                {
                    "message":
                    "OTP not found or expired."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not created_string:

            return Response(
                {
                    "message":
                    "OTP expired."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            created_time = (
                timezone.datetime.fromisoformat(
                    created_string
                )
            )

            if timezone.is_naive(
                created_time
            ):

                created_time = (
                    timezone.make_aware(
                        created_time
                    )
                )

        except Exception:

            return Response(
                {
                    "message":
                    "Invalid OTP session."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if (
            timezone.now()
            - created_time
            > timedelta(minutes=10)
        ):

            request.session.pop(
                "password_reset_otp",
                None
            )

            return Response(
                {
                    "message":
                    "OTP has expired."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp != saved_otp:

            return Response(
                {
                    "message":
                    "Invalid OTP."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        request.session[
            "password_reset_verified"
        ] = True

        return Response(
            {
                "message":
                "OTP verified successfully."
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# RESET PASSWORD
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class ResetPasswordView(APIView):

    permission_classes = [
        AllowAny
    ]

    authentication_classes = []

    def post(self, request):

        email = (
            request.data.get("email")
            or request.session.get(
                "password_reset_email"
            )
            or ""
        ).strip().lower()

        new_password = (
            request.data.get(
                "new_password"
            )
            or request.data.get(
                "password"
            )
            or ""
        )

        confirm_password = (
            request.data.get(
                "confirm_password"
            )
            or ""
        )

        verified = request.session.get(
            "password_reset_verified",
            False
        )

        if not verified:

            return Response(
                {
                    "message":
                    "Please verify OTP first."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not email:

            return Response(
                {
                    "message":
                    "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not new_password:

            return Response(
                {
                    "message":
                    "New password is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if (
            confirm_password
            and new_password
            != confirm_password
        ):

            return Response(
                {
                    "message":
                    "Passwords do not match."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(new_password) < 8:

            return Response(
                {
                    "message":
                    "Password must contain at least "
                    "8 characters."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            user = User.objects.get(
                email__iexact=email
            )

        except User.DoesNotExist:

            return Response(
                {
                    "message":
                    "User not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        user.set_password(
            new_password
        )

        user.save(
            update_fields=[
                "password"
            ]
        )

        request.session.pop(
            "password_reset_otp",
            None
        )

        request.session.pop(
            "password_reset_email",
            None
        )

        request.session.pop(
            "password_reset_otp_created",
            None
        )

        request.session.pop(
            "password_reset_verified",
            None
        )

        return Response(
            {
                "message":
                "Password reset successfully."
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# PROFILE STATUS
# ============================================================

class ProfileStatusView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def get(self, request):

        profile = get_jobseeker_profile(
            request
        )

        if not profile:

            return Response(
                {
                    "profile_exists":
                    False,

                    "approval_status":
                    None,

                    "profile_completed":
                    False,
                },
                status=status.HTTP_200_OK
            )

        profile.refresh_from_db()

        return Response(
            {
                "profile_exists":
                True,

                "approval_status":
                profile.approval_status,

                "profile_completed":
                profile.profile_completed,

                "rejection_reason":
                profile.rejection_reason or "",

                "can_edit":
                True,

                "can_submit":
                profile.approval_status
                != "pending",
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# LOGOUT
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class LogoutView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def post(self, request):

        refresh_token = (
            request.data.get(
                "refresh"
            )
            or request.data.get(
                "refresh_token"
            )
        )

        if refresh_token:

            try:

                token = RefreshToken(
                    refresh_token
                )

                token.blacklist()

            except Exception as e:

                print(
                    "LOGOUT TOKEN ERROR:",
                    str(e)
                )

        return Response(
            {
                "message":
                "Logged out successfully."
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# MARK ALL NOTIFICATIONS AS READ
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class MarkAllNotificationsReadView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def patch(self, request):

        updated_count = (
            Notification.objects.filter(
                recipient=request.user,
                is_read=False
            )
            .update(
                is_read=True
            )
        )

        return Response(
            {
                "message":
                "All notifications marked as read.",

                "updated_count":
                updated_count,

                "unread_count":
                0,
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# DELETE NOTIFICATION
# ============================================================

@method_decorator(
    csrf_exempt,
    name="dispatch"
)
class NotificationDeleteView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    authentication_classes = [
        JWTAuthentication
    ]

    def delete(
        self,
        request,
        notification_id
    ):

        try:

            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )

        except Notification.DoesNotExist:

            return Response(
                {
                    "message":
                    "Notification not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        notification.delete()

        return Response(
            {
                "message":
                "Notification deleted successfully."
            },
            status=status.HTTP_204_NO_CONTENT
        )

# ============================================================
# CHAT HELPERS
# ============================================================


def _chat_role(user):
    if hasattr(user, "employer_profile"):
        return "employer"
    if hasattr(user, "jobseeker_profile"):
        return "jobseeker"
    return None


def _profile_user(participant_type, profile_id):
    if participant_type == "employer":
        from employer.models import EmployerProfile
        profile = (
            EmployerProfile.objects
            .select_related("user")
            .filter(pk=profile_id)
            .first()
        )
    elif participant_type == "jobseeker":
        profile = (
            JobSeekerProfile.objects
            .select_related("user")
            .filter(pk=profile_id)
            .first()
        )
    else:
        profile = None
    return profile.user if profile else None


def _get_conversation_for_user(conversation_id, user):
    return (
        Conversation.objects
        .filter(pk=conversation_id)
        .filter(
            models.Q(participant_one=user)
            | models.Q(participant_two=user)
        )
        .first()
    )


# ============================================================
# GET / CREATE CONVERSATIONS
# ============================================================

class ConversationListCreateView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        conversations = (
            Conversation.objects
            .filter(
                models.Q(participant_one=request.user)
                | models.Q(participant_two=request.user)
            )
            .select_related(
                "participant_one",
                "participant_two",
            )
            .prefetch_related("messages")
            .order_by("-updated_at")
        )

        serializer = ConversationSerializer(
            conversations,
            many=True,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        participant_type = str(
            request.data.get("participant_type", "")
        ).strip().lower()

        participant_id = request.data.get("participant_id")

        if participant_type not in {"employer", "jobseeker"}:
            return Response(
                {"detail": "participant_type must be employer or jobseeker."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            participant_id = int(participant_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "A valid participant_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_role = _chat_role(request.user)

        if current_role is None:
            return Response(
                {"detail": "Your account is not configured for chat."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if current_role == participant_type:
            return Response(
                {
                    "detail": (
                        "Chat is available only between Employer and Jobseeker."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        other_user = _profile_user(
            participant_type,
            participant_id,
        )

        if not other_user:
            return Response(
                {"detail": "The requested profile was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if other_user.id == request.user.id:
            return Response(
                {"detail": "You cannot chat with yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connected = False

        if current_role == "jobseeker" and participant_type == "employer":
            connected = (
                JobApplication.objects
                .filter(
                    jobseeker__user=request.user,
                    job__employer__user=other_user,
                )
                .exists()
            )
        elif current_role == "employer" and participant_type == "jobseeker":
            connected = (
                JobApplication.objects
                .filter(
                    jobseeker__user=other_user,
                    job__employer__user=request.user,
                )
                .exists()
            )

        if not connected:
            return Response(
                {
                    "detail": (
                        "Chat is available only between users "
                        "connected through a job application."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        first_user, second_user = sorted(
            [request.user, other_user],
            key=lambda user: user.id,
        )

        conversation, created = (
            Conversation.objects.get_or_create(
                participant_one=first_user,
                participant_two=second_user,
            )
        )

        serializer = ConversationSerializer(
            conversation,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )


# ============================================================
# MESSAGES
# ============================================================

class ConversationMessagesView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, conversation_id):
        conversation = _get_conversation_for_user(
            conversation_id,
            request.user,
        )

        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        Message.objects.filter(
            conversation=conversation,
            is_read=False,
        ).exclude(
            sender=request.user
        ).update(
            is_read=True
        )

        messages = (
            conversation.messages
            .select_related("sender")
            .all()
        )

        serializer = ChatMessageSerializer(
            messages,
            many=True,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, conversation_id):
        conversation = _get_conversation_for_user(
            conversation_id,
            request.user,
        )

        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        text = str(
            request.data.get("text", "")
        ).strip()

        if not text:
            return Response(
                {"detail": "Message cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(text) > 5000:
            return Response(
                {"detail": "Message cannot exceed 5000 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
        )

        conversation.save(update_fields=["updated_at"])

        serializer = ChatMessageSerializer(
            message,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# MARK CHAT AS READ
# ============================================================

class ConversationReadView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def patch(self, request, conversation_id):
        conversation = _get_conversation_for_user(
            conversation_id,
            request.user,
        )

        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        Message.objects.filter(
            conversation=conversation,
            is_read=False,
        ).exclude(
            sender=request.user
        ).update(
            is_read=True
        )

        return Response(
            {"message": "Messages marked as read."},
            status=status.HTTP_200_OK,
        )


# ============================================================
# DELETE CONVERSATION
# ============================================================

class ConversationDeleteView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def delete(self, request, conversation_id):
        conversation = _get_conversation_for_user(
            conversation_id,
            request.user,
        )

        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        conversation.delete()
        return Response(
            status=status.HTTP_204_NO_CONTENT
        )
