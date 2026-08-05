from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APITestCase


class CategoryAPITest(APITestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )

        self.client.force_authenticate(
            user=self.user
        )


    def test_create_category(self):

        data = {
            "name": "Спорт"
        }

        response = self.client.post(
            "/api/v1/categories/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )


    def test_list_categories(self):

        response = self.client.get(
            "/api/v1/categories/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

# Create your tests here.
