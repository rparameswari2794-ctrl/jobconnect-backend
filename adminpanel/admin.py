from django.contrib import admin
from .models import PasswordResetOTP


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "otp",
        "created_at",
        "expires_at",
        "is_verified",
    )
    list_filter = ("is_verified",)
    search_fields = ("user__email", "otp")