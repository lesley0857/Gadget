from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
import random

User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def save_user(self, request, sociallogin, form=None):
        user = sociallogin.user

        # Ensure email exists
        if not user.email:
            raise ValueError("Email is required")

        # Generate username automatically
        if not user.username:
            base_username = user.email.split('@')[0]
            username = base_username

            # Ensure uniqueness
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{random.randint(1000,9999)}"

            user.username = username

        user.save()
        sociallogin.save(request)

        return user