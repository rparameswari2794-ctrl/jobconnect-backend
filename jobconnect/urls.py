from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

from rest_framework_simplejwt.views import TokenRefreshView


def home(request):
    return JsonResponse({
        "message": "JobConnect API is running successfully."
    })


urlpatterns = [

    path(
        "",
        home,
        name="home"
    ),

    path(
        "admin/",
        admin.site.urls
    ),

    # =====================================================
    # COMMON AUTH
    # =====================================================

    path(
        "api/auth/",
        include("jobconnect.auth_urls")
    ),

    # =====================================================
    # ADMIN PANEL
    # =====================================================

    path(
        "api/admin/",
        include("adminpanel.urls")
    ),
    path(
        "api/auth/",
        include("adminpanel.auth_urls")
    ),

    # =====================================================
    # JOB SEEKER
    # =====================================================

    path(
        "api/auth/jobseeker/",
        include("jobseeker.urls")
    ),

    # =====================================================
    # EMPLOYER
    # =====================================================

    path(
        "api/auth/employer/",
        include("employer.urls")
    ),

    # =====================================================
    # JWT REFRESH
    # =====================================================

    path(
        "api/auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh"
    ),
]


if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )