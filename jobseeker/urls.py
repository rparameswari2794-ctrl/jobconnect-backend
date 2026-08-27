from django.urls import path

from .views import (
    JobSeekerSignupView,
    JobSeekerLoginView,
    JobSeekerProfileView,


    EducationView,
    EducationDetailView,

    ExperienceView,
    ExperienceDetailView,

    ProjectView,
    ProjectDetailView,

    JobSeekerJobDetailView,

    MyApplicationsView,
    JobApplicationDetailView,
    ApplyJobView,

    SubmitProfileView,
    JobListView,

    JobSeekerProjectListCreateView,
    JobSeekerProjectDetailView,
)


urlpatterns = [

    # =====================================================
    # AUTH
    # =====================================================

    path(
        "signup/",
        JobSeekerSignupView.as_view(),
        name="jobseeker-signup"
    ),
    
    path(
        "login/",
        JobSeekerLoginView.as_view(),
        name="jobseeker-login"
    ),
    


    # =====================================================
    # PROFILE
    # =====================================================

    path(
        "profile/",
        JobSeekerProfileView.as_view(),
        name="jobseeker-profile"
    ),

    path(
        "submit-profile/",
        SubmitProfileView.as_view(),
        name="submit-profile",
    ),



    # =====================================================
    # EDUCATION
    # =====================================================

    path(
        "education/",
        EducationView.as_view(),
        name="education"
    ),

    path(
        "education/<int:education_id>/",
        EducationDetailView.as_view(),
        name="education-detail"
    ),


    # =====================================================
    # EXPERIENCE
    # =====================================================

    path(
        "experience/",
        ExperienceView.as_view(),
        name="experience"
    ),

    path(
        "experience/<int:experience_id>/",
        ExperienceDetailView.as_view(),
        name="experience-detail"
    ),


    # =====================================================
    # FIND JOBS
    # =====================================================

    path(
        "jobs/",
        JobListView.as_view(),
        name="job-list"
    ),

    # IMPORTANT:
    # Use job_id because your view method is:
    # def get(self, request, job_id)

    path(
        "jobs/<int:job_id>/",
        JobSeekerJobDetailView.as_view(),
        name="jobseeker-job-detail"
    ),

    path(
        "jobs/<int:job_id>/apply/",
        ApplyJobView.as_view(),
        name="apply-job"
    ),


    # =====================================================
    # PROJECTS
    # =====================================================

    path(
        "project/",
        ProjectView.as_view(),
        name="project"
    ),

    path(
        "project/<int:project_id>/",
        ProjectDetailView.as_view(),
        name="project-detail"
    ),

    # If your frontend uses /projects/
    path(
        "projects/",
        JobSeekerProjectListCreateView.as_view(),
        name="jobseeker-projects"
    ),

    path(
        "projects/<int:pk>/",
        JobSeekerProjectDetailView.as_view(),
        name="jobseeker-project-detail"
    ),


    # =====================================================
    # MY APPLICATIONS
    # =====================================================

    path(
        "applications/",
        MyApplicationsView.as_view(),
        name="my-applications"
    ),

    path(
        "applications/<int:application_id>/",
        JobApplicationDetailView.as_view(),
        name="application-detail"
    ),
]