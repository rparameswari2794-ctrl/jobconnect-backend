from django.urls import path

from adminpanel.views import (
    ForgotPasswordView,
    VerifyOTPView,
    ResetPasswordView,
    LoginView,
)


urlpatterns = [
    path(
        "login/",
        LoginView.as_view(),
        name="login"
    ),


    path(
        "forgot-password/",
        ForgotPasswordView.as_view(),
        name="forgot-password"
    ),

    path(
        "verify-otp/",
        VerifyOTPView.as_view(),
        name="verify-otp"
    ),

    path(
        "reset-password/",
        ResetPasswordView.as_view(),
        name="reset-password"
    ),
]