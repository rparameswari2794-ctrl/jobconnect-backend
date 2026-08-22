from django.contrib.auth import authenticate


def authenticate_by_email(email, password):
    """
    Authenticate Django User using email and password.
    """

    email = email.strip().lower()

    try:
        from django.contrib.auth.models import User

        user = User.objects.get(email__iexact=email)

    except User.DoesNotExist:
        return None

    return authenticate(
        username=user.username,
        password=password
    )