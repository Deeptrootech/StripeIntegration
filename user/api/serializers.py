from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers


class AuthSerializer(serializers.Serializer):
    """serializer for the user authentication object"""

    email = serializers.EmailField()
    password = serializers.CharField(
        style={"input_type": "password"}, trim_whitespace=False
    )

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError("Credentials not valid..!!")
        attrs["user"] = user
        return attrs
