from rest_framework import serializers

from .models import HelpRequest, HelpMessage



# ============================================================
# HELP MESSAGE SERIALIZER
# ============================================================

class HelpMessageSerializer(serializers.ModelSerializer):

    sender_id = serializers.IntegerField(
        source="sender.id",
        read_only=True
    )

    sender_name = serializers.SerializerMethodField()

    sender_role = serializers.SerializerMethodField()

    class Meta:
        model = HelpMessage

        fields = [
            "id",
            "sender_id",
            "sender_name",
            "sender_role",
            "message",
            "is_read",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "sender_id",
            "sender_name",
            "sender_role",
            "is_read",
            "created_at",
        ]

    def get_sender_name(self, obj):

        user = obj.sender

        full_name = f"{user.first_name} {user.last_name}".strip()

        return full_name or user.username

    def get_sender_role(self, obj):

        user = obj.sender

        if user.is_staff or user.is_superuser:
            return "admin"

        if hasattr(user, "employer_profile"):
            return "employer"

        if hasattr(user, "jobseeker_profile"):
            return "jobseeker"

        return "user"


# ============================================================
# HELP REQUEST SERIALIZER
# ============================================================

class HelpRequestSerializer(serializers.ModelSerializer):

    user_name = serializers.SerializerMethodField()

    user_role = serializers.SerializerMethodField()

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True
    )

    messages = HelpMessageSerializer(
        many=True,
        read_only=True
    )

    # Used only when creating a new support request
    message = serializers.CharField(
        write_only=True,
        required=True
    )

    class Meta:
        model = HelpRequest

        fields = [
            "id",
            "user_name",
            "user_role",
            "subject",
            "status",
            "status_display",
            "is_read",
            "resolved_at",
            "created_at",
            "updated_at",
            "messages",
            "message",
        ]

        read_only_fields = [
            "id",
            "user_name",
            "user_role",
            "status",
            "status_display",
            "is_read",
            "resolved_at",
            "created_at",
            "updated_at",
            "messages",
        ]

    def get_user_name(self, obj):

        user = obj.user

        full_name = f"{user.first_name} {user.last_name}".strip()

        return full_name or user.username

    def get_user_role(self, obj):

        user = obj.user

        if user.is_staff or user.is_superuser:
            return "admin"

        if hasattr(user, "employer_profile"):
            return "employer"

        if hasattr(user, "jobseeker_profile"):
            return "jobseeker"

        return "user"

    def create(self, validated_data):

        message = validated_data.pop("message")

        request = self.context["request"]

        help_request = HelpRequest.objects.create(
            user=request.user,
            subject=validated_data["subject"],
        )

        HelpMessage.objects.create(
            help_request=help_request,
            sender=request.user,
            message=message,
            is_read=False,
        )

        return help_request


# ============================================================
# REPLY SERIALIZER
# ============================================================

class HelpReplySerializer(serializers.Serializer):

    message = serializers.CharField(
        required=True,
        allow_blank=False
    )


# ============================================================
# OPTIONAL ADMIN ACTION RESPONSE
# ============================================================

class HelpActionResponseSerializer(serializers.Serializer):

    detail = serializers.CharField()