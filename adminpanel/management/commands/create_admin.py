import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create Django superuser if it does not exist"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        username = os.environ.get("admin")
        email = os.environ.get("jobconnect@gmail.com")
        password = os.environ.get("job123")

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "Admin credentials are not configured."
                )
            )
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f"Superuser '{username}' already exists."
                )
            )
            return

        User.objects.create_superuser(
            username=username,
            email=email or "",
            password=password,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Superuser '{username}' created successfully."
            )
        )