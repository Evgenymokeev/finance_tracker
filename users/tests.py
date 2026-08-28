from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APITestCase


class UserProfileAPITest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        self.client.force_authenticate(
            user=self.user
        )

    def test_get_profile(self):
        response = self.client.get(
            "/api/v1/auth/profile/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["username"],
            "testuser"
        )

        self.assertEqual(
            response.data["email"],
            "test@example.com"
        )

    def test_update_profile(self):
        data = {
            "first_name": "Evgeny",
            "last_name": "Mokeev",
            "email": "newemail@example.com"
        }

        response = self.client.patch(
            "/api/v1/auth/profile/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.user.refresh_from_db()

        self.assertEqual(
            self.user.first_name,
            "Evgeny"
        )

        self.assertEqual(
            self.user.last_name,
            "Mokeev"
        )

        self.assertEqual(
            self.user.email,
            "newemail@example.com"
        )

    def test_update_profile_with_existing_email(self):
        User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="testpass123"
        )

        data = {
            "email": "another@example.com"
        }

        response = self.client.patch(
            "/api/v1/auth/profile/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "email",
            response.data
        )

    def test_change_password(self):
        data = {
            "old_password": "testpass123",
            "new_password": "newpassword123"
        }

        response = self.client.post(
            "/api/v1/auth/change-password/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password(
                "newpassword123"
            )
        )

    def test_change_password_with_wrong_old_password(self):
        data = {
            "old_password": "wrongpassword",
            "new_password": "newpassword123"
        }

        response = self.client.post(
            "/api/v1/auth/change-password/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_change_password_with_short_password(self):
        data = {
            "old_password": "testpass123",
            "new_password": "1234567"
        }

        response = self.client.post(
            "/api/v1/auth/change-password/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_register(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpass123"
        }

        response = self.client.post(
            "/api/v1/auth/register/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertTrue(
            User.objects.filter(
                username="newuser"
            ).exists()
        )

    def test_register_with_short_password(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "1234567"
        }

        response = self.client.post(
            "/api/v1/auth/register/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_register_with_existing_email(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "username": "anotheruser",
            "email": "test@example.com",
            "password": "newpass123"
        }

        response = self.client.post(
            "/api/v1/auth/register/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "email",
            response.data
        )

# Create your tests here.
