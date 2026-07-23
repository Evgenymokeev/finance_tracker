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

        value = value.strip()

        user = self.context["request"].user

        queryset = Category.objects.filter(
            user=user,
            name__iexact=value
        )

        if self.instance:
            queryset = queryset.exclude(
                id=self.instance.id
            )

        if queryset.exists():
            raise serializers.ValidationError(
                "Такая категория уже существует."
            )

        return value
