from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category

        fields = [
            "id",
            "name",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]


    def validate_name(self, value):

        user = self.context["request"].user

        if Category.objects.filter(
            user=user,
            name__iexact=value
        ).exists():

            raise serializers.ValidationError(
                "Такая категория уже существует."
            )

        return value
