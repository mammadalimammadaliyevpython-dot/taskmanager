"""The user model."""

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Django's stock user, under our own name.

    Nothing is added yet; having the model in the project from the first migration means
    fields (avatar, timezone, ...) can be added later without a painful migration.
    """

    def __str__(self):
        return self.username
