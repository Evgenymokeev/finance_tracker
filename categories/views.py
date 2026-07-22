from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from .models import Category
from .serializers import CategorySerializer


@extend_schema(
    tags=["Categories"]
)
class CategoryViewSet(viewsets.ModelViewSet):

    serializer_class = CategorySerializer

    permission_classes = [
        IsAuthenticated,
    ]

    search_fields = [
        "name",
    ]

    ordering_fields = [
        "name",
    ]

    def get_queryset(self):
        return Category.objects.filter(
            user=self.request.user
        ).order_by("name",
    "-created_at")


    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user
        )

# Create your views here.
