"""What the accounts API sends and accepts."""

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """The public shape of a user, embedded in tasks and comments."""

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class RegisterSerializer(serializers.ModelSerializer):
    """POST /auth/register/: username + password, optionally email and a name."""

    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "password"]

    def validate(self, attrs):
        # Django's validators (length, common passwords, similarity to the username, ...).
        user = User(**{name: value for name, value in attrs.items() if name != "password"})
        try:
            password_validation.validate_password(attrs["password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from None
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)  # hashes the password
