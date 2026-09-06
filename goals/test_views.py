from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import FinancialGoal


class FinancialGoalViewSetTests(APITestCase):
    """
    Тесты CRUD API для финансовых целей.

    Проверяем:
    - создание цели;
    - получение списка;
    - получение одной цели;
    - изменение;
    - удаление;
    - изоляцию целей разных пользователей;
    - запрет доступа без авторизации.
    """

    def setUp(self):
        # Создаём двух пользователей.
        # Они нужны для проверки, что пользователь
        # не может работать с чужими финансовыми целями.
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="otherpassword123",
        )

        # Авторизуем основного пользователя.
        self.client.force_authenticate(
            user=self.user
        )

    def create_goal(self, user=None):
        """
        Вспомогательный метод для создания финансовой цели.

        Если пользователь не передан,
        цель создаётся для self.user.
        """

        if user is None:
            user = self.user

        return FinancialGoal.objects.create(
            user=user,
            title="Накопить на MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("10000.00"),
        )

    def test_create_goal(self):
        """
        Проверяет создание финансовой цели через API.

        Ожидаем:
        - HTTP 201 Created;
        - цель принадлежит текущему пользователю;
        - данные сохраняются в базе.
        """

        url = reverse("financial-goal-list")

        data = {
            "title": "Накопить на автомобиль",
            "target_amount": "500000.00",
            "current_amount": "100000.00",
            "description": "Моя финансовая цель",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        goal = FinancialGoal.objects.get(
            id=response.data["id"]
        )

        self.assertEqual(
            goal.user,
            self.user,
        )

        self.assertEqual(
            goal.title,
            "Накопить на автомобиль",
        )

        self.assertEqual(
            goal.target_amount,
            Decimal("500000.00"),
        )

    def test_list_goals_returns_only_current_user_goals(self):
        """
        Проверяет изоляцию данных пользователей.

        Если существуют цели двух пользователей,
        API должен вернуть только цели текущего пользователя.
        """

        own_goal = self.create_goal(
            user=self.user
        )

        self.create_goal(
            user=self.other_user
        )

        url = reverse("financial-goal-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["count"],
            1,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            own_goal.id,
        )

    def test_retrieve_own_goal(self):
        """
        Проверяет получение конкретной цели
        текущего пользователя.
        """

        goal = self.create_goal()

        url = reverse(
            "financial-goal-detail",
            kwargs={"pk": goal.id},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            goal.id,
        )

        self.assertEqual(
            response.data["title"],
            "Накопить на MacBook",
        )

    def test_update_own_goal(self):
        """
        Проверяет изменение собственной финансовой цели.
        """

        goal = self.create_goal()

        url = reverse(
            "financial-goal-detail",
            kwargs={"pk": goal.id},
        )

        data = {
            "title": "Накопить на новый MacBook",
            "target_amount": "60000.00",
            "current_amount": "15000.00",
        }

        response = self.client.patch(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        goal.refresh_from_db()

        self.assertEqual(
            goal.title,
            "Накопить на новый MacBook",
        )

        self.assertEqual(
            goal.target_amount,
            Decimal("60000.00"),
        )

        self.assertEqual(
            goal.current_amount,
            Decimal("15000.00"),
        )

    def test_delete_own_goal(self):
        """
        Проверяет удаление собственной финансовой цели.
        """

        goal = self.create_goal()

        url = reverse(
            "financial-goal-detail",
            kwargs={"pk": goal.id},
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            FinancialGoal.objects.filter(
                id=goal.id
            ).exists()
        )

    def test_cannot_retrieve_other_user_goal(self):
        """
        Проверяет, что пользователь не может получить
        финансовую цель другого пользователя.

        Так как get_queryset() возвращает только собственные цели,
        API отвечает 404 Not Found.
        """

        goal = self.create_goal(
            user=self.other_user
        )

        url = reverse(
            "financial-goal-detail",
            kwargs={"pk": goal.id},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_cannot_update_other_user_goal(self):
        """
        Проверяет, что пользователь не может изменить
        финансовую цель другого пользователя.
        """

        goal = self.create_goal(
            user=self.other_user
        )

        url = reverse(
            "financial-goal-detail",
            kwargs={"pk": goal.id},
        )

        data = {
            "title": "Попытка изменить чужую цель",
        }

        response = self.client.patch(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        goal.refresh_from_db()

        self.assertEqual(
            goal.title,
            "Накопить на MacBook",
        )

    def test_cannot_delete_other_user_goal(self):
        """
        Проверяет, что пользователь не может удалить
        финансовую цель другого пользователя.
        """

        goal = self.create_goal(
            user=self.other_user
        )

        url = reverse(
            "financial-goal-detail",
            kwargs={"pk": goal.id},
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertTrue(
            FinancialGoal.objects.filter(
                id=goal.id
            ).exists()
        )

    def test_unauthenticated_user_cannot_list_goals(self):
        """
        Проверяет, что список финансовых целей
        недоступен неавторизованному пользователю.
        """

        self.client.force_authenticate(
            user=None
        )

        url = reverse("financial-goal-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_unauthenticated_user_cannot_create_goal(self):
        """
        Проверяет, что неавторизованный пользователь
        не может создать финансовую цель.
        """

        self.client.force_authenticate(
            user=None
        )

        url = reverse("financial-goal-list")

        data = {
            "title": "Чужая цель",
            "target_amount": "10000.00",
            "current_amount": "0.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )