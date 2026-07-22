from django.contrib.auth.models import User
from rest_framework import serializers


class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True
)
    email = serializers.EmailField(
    required=True
)

    
    

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
        )

    def create(self, validated_data):

        user = User.objects.create_user(
            **validated_data
        )

        return user