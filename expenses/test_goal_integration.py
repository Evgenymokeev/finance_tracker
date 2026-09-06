from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from categories.models import Category
from expenses.models import Expense
from goals.models import FinancialGoal


@pytest.mark.django_db
class TestExpenseGoalIntegration:
    """
    Интеграционные тесты связи Expense ↔ FinancialGoal.

    Проверяем, что расход может:

    - создаваться без финансовой цели;
    - связываться с собственной финансовой целью пользователя;
    - изменять связанную финансовую цель;
    - отвязываться от финансовой цели;
    - фильтроваться по финансовой цели.

    Также проверяем безопасность:

    - нельзя привязать чужую финансовую цель;
    - нельзя изменить расход так, чтобы он ссылался
      на чужую финансовую цель.

    Главное бизнес-правило интеграции:

        Expense.goal
            |
            └── показывает, на какую финансовую цель
                был связан расход.

        FinancialGoal.current_amount
            |
            └── показывает, сколько денег накоплено.

    Связывание расхода с целью НЕ изменяет
    FinancialGoal.current_amount автоматически.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """
        Подготавливает тестовые данные перед каждым тестом.

        Создаются:

        - два пользователя;
        - API-клиент;
        - категория первого пользователя;
        - две финансовые цели первого пользователя;
        - финансовая цель второго пользователя.

        Второй пользователь и его цель нужны для проверки
        изоляции данных между пользователями.
        """

        # Первый пользователь.
        self.user = User.objects.create_user(
            username="user1",
            password="password123",
        )

        # Второй пользователь.

        # Нужен для проверки, что user1 не может
        # использовать финансовую цель user2.
        self.other_user = User.objects.create_user(
            username="user2",
            password="password123",
        )

        # Создаём API-клиент для выполнения HTTP-запросов.
        self.client = APIClient()

        # Авторизовываем API-клиент от имени первого пользователя.
        self.client.force_authenticate(
            user=self.user
        )

        # Создаём категорию, принадлежащую первому пользователю.
        self.category = Category.objects.create(
            user=self.user,
            name="Еда",
        )

        # Первая финансовая цель первого пользователя.
        self.goal = FinancialGoal.objects.create(
            user=self.user,
            title="Новый ноутбук",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("10000.00"),
        )

        # Вторая финансовая цель того же пользователя.

        # Нужна для проверки изменения связи:
        #
        # Expense -> goal
        #
        # меняется на:
        #
        # Expense -> second_goal
        self.second_goal = FinancialGoal.objects.create(
            user=self.user,
            title="Путешествие",
            target_amount=Decimal("100000.00"),
            current_amount=Decimal("20000.00"),
        )

        # Финансовая цель другого пользователя.

        # Используется для проверки безопасности:
        # user1 не должен иметь возможность
        # привязать к расходу цель user2.
        self.other_goal = FinancialGoal.objects.create(
            user=self.other_user,
            title="Чужая цель",
            target_amount=Decimal("30000.00"),
            current_amount=Decimal("5000.00"),
        )

    def create_expense_data(self, **extra_data):
        """
        Возвращает стандартные данные для создания расхода.

        Метод нужен, чтобы не дублировать одинаковые данные
        во всех тестах.

        Через **extra_data можно передать дополнительные значения
        или изменить существующие.

        Например:

            self.create_expense_data(
                goal=self.goal.id
            )

        создаст обычные данные расхода и добавит финансовую цель.
        """

        data = {
            "title": "Кофе",
            "amount": "250.00",
            "category": self.category.id,
            "date": "2026-09-01",
            "description": "Кофе после работы",
        }

        # Добавляем или заменяем переданные поля.
        data.update(extra_data)

        return data

    def test_expense_can_be_created_without_goal(self):
        """
        Проверяет, что финансовая цель является необязательной.

        Ожидаемое поведение:

        - расход успешно создаётся;
        - API возвращает HTTP 201 Created;
        - goal у созданного расхода равен None.

        Это важно для обратной совместимости.

        Пользователь должен иметь возможность создавать обычные
        расходы, не связывая их с финансовыми целями.
        """

        response = self.client.post(
            "/api/v1/expenses/",
            self.create_expense_data(),
            format="json",
        )

        # Проверяем успешное создание расхода.
        assert response.status_code == 201

        # Получаем созданный расход непосредственно из БД.

        # Не используем response.data["id"], потому что текущий
        # endpoint создания расхода не обязан возвращать ID
        # созданного объекта в response.data.
        expense = Expense.objects.get(
            user=self.user,
            title="Кофе",
        )

        # Проверяем, что расход не связан ни с одной целью.
        assert expense.goal is None

    def test_expense_can_be_linked_to_own_goal(self):
        """
        Проверяет возможность привязать расход
        к финансовой цели текущего пользователя.

        Ожидаемое поведение:

        - расход успешно создаётся;
        - финансовая цель принадлежит текущему пользователю;
        - связь Expense -> FinancialGoal сохраняется в БД.
        """

        response = self.client.post(
            "/api/v1/expenses/",
            self.create_expense_data(
                goal=self.goal.id
            ),
            format="json",
        )

        # Проверяем успешное создание расхода.
        assert response.status_code == 201

        # Получаем созданный расход из БД.
        expense = Expense.objects.get(
            user=self.user,
            title="Кофе",
        )

        # Проверяем, что расход связан именно с нашей целью.
        assert expense.goal == self.goal

    def test_user_cannot_attach_other_users_goal(self):
        """
        Проверяет защиту от привязки чужой финансовой цели.

        Сценарий:

        - текущий пользователь = user1;
        - финансовая цель принадлежит user2;
        - user1 пытается создать расход
          с финансовой целью user2.

        Ожидаемое поведение:

        - API возвращает HTTP 400;
        - расход с чужой целью не создаётся.

        Это важная проверка безопасности и изоляции данных.
        """

        response = self.client.post(
            "/api/v1/expenses/",
            self.create_expense_data(
                goal=self.other_goal.id
            ),
            format="json",
        )

        # Запрос должен быть отклонён.
        assert response.status_code == 400

        # Проверяем, что расход с чужой целью
        # не появился в базе данных.
        assert not Expense.objects.filter(
            goal=self.other_goal
        ).exists()

    def test_get_expense_returns_goal(self):
        """
        Проверяет, что API возвращает финансовую цель
        при получении существующего расхода.

        Создаём расход, связанный с goal.

        Затем выполняем GET-запрос.

        Ожидаемое поведение:

            response.data["goal"] == goal.id

        Это необходимо frontend/mobile/Telegram-клиенту,
        чтобы понимать, к какой финансовой цели
        относится расход.
        """

        expense = Expense.objects.create(
            user=self.user,
            title="Чехол для ноутбука",
            amount=Decimal("2500.00"),
            category=self.category,
            date="2026-09-01",
            description="Чехол",
            goal=self.goal,
        )

        response = self.client.get(
            f"/api/v1/expenses/{expense.id}/"
        )

        # Проверяем успешный GET-запрос.
        assert response.status_code == 200

        # Проверяем, что API возвращает ID финансовой цели.
        assert response.data["goal"] == self.goal.id

    def test_expense_goal_can_be_changed(self):
        """
        Проверяет изменение финансовой цели
        у существующего расхода.

        Сначала:

            Expense -> self.goal

        Затем меняем связь:

            Expense -> self.second_goal

        Ожидаемое поведение:

        - PATCH успешно выполняется;
        - новая финансовая цель сохраняется в БД.
        """

        expense = Expense.objects.create(
            user=self.user,
            title="Покупка",
            amount=Decimal("1000.00"),
            category=self.category,
            date="2026-09-01",
            description="Покупка",
            goal=self.goal,
        )

        response = self.client.patch(
            f"/api/v1/expenses/{expense.id}/",
            {
                "goal": self.second_goal.id
            },
            format="json",
        )

        # Проверяем успешное изменение.
        assert response.status_code == 200

        # Обновляем объект из БД.
        expense.refresh_from_db()

        # Проверяем новую связь.
        assert expense.goal == self.second_goal

    def test_expense_goal_can_be_cleared(self):
        """
        Проверяет возможность отвязать расход
        от финансовой цели.

        Пользователь отправляет:

            {
                "goal": null
            }

        Ожидаемое поведение:

        - PATCH успешно выполняется;
        - goal становится None.

        Это важно, потому что пользователь может сначала
        привязать расход к цели, а позже убрать эту связь.
        """

        expense = Expense.objects.create(
            user=self.user,
            title="Покупка",
            amount=Decimal("1000.00"),
            category=self.category,
            date="2026-09-01",
            description="Покупка",
            goal=self.goal,
        )

        response = self.client.patch(
            f"/api/v1/expenses/{expense.id}/",
            {
                "goal": None
            },
            format="json",
        )

        # Проверяем успешное изменение.
        assert response.status_code == 200

        # Получаем актуальное состояние расхода из БД.
        expense.refresh_from_db()

        # Проверяем, что финансовая цель была удалена из связи.
        assert expense.goal is None

    def test_deleting_goal_does_not_delete_expense(self):
        """
        Проверяет поведение при удалении финансовой цели.

        В модели Expense используется:

            on_delete=models.SET_NULL

        Поэтому при удалении FinancialGoal:

        - сам Expense должен остаться;
        - Expense.goal должен стать None.

        Это защищает историю расходов от удаления
        вместе с финансовой целью.
        """

        expense = Expense.objects.create(
            user=self.user,
            title="Покупка",
            amount=Decimal("1000.00"),
            category=self.category,
            date="2026-09-01",
            description="Покупка",
            goal=self.goal,
        )

        # Удаляем финансовую цель.
        self.goal.delete()

        # Обновляем расход из БД.
        expense.refresh_from_db()

        # Проверяем, что расход всё ещё существует.
        assert Expense.objects.filter(
            id=expense.id
        ).exists()

        # Проверяем, что связь автоматически стала None.
        assert expense.goal is None

    def test_linking_expense_does_not_change_goal_current_amount(self):
        """
        Проверяет главное бизнес-правило интеграции.

        Пример:

            target_amount = 50000
            current_amount = 10000

        Создаём расход:

            amount = 2500

        и связываем его с финансовой целью.

        После этого:

            current_amount == 10000

        должно остаться без изменений.

        НЕ должно происходить:

            10000 - 2500 = 7500

        и не должно происходить:

            10000 + 2500 = 12500

        Связь расхода с целью является только информационной.

        Пополнение цели выполняется через deposit,
        а снятие — через withdraw.
        """

        # Запоминаем первоначальную сумму цели.
        initial_amount = self.goal.current_amount

        response = self.client.post(
            "/api/v1/expenses/",
            self.create_expense_data(
                title="Чехол для ноутбука",
                amount="2500.00",
                goal=self.goal.id,
            ),
            format="json",
        )

        # Проверяем успешное создание расхода.
        assert response.status_code == 201

        # Получаем актуальное состояние цели из БД.
        self.goal.refresh_from_db()

        # Проверяем главное бизнес-правило:
        # создание расхода не меняет накопленную сумму цели.
        assert self.goal.current_amount == initial_amount

    def test_expenses_can_be_filtered_by_goal(self):
        """
        Проверяет фильтрацию расходов по финансовой цели.

        Создаются два расхода:

        - первый связан с self.goal;
        - второй связан с self.second_goal.

        Затем выполняется запрос:

            GET /api/v1/expenses/?goal=<ID>

        Ожидаемое поведение:

        API должен вернуть только расходы,
        связанные с указанной финансовой целью.
        """

        # Расход для первой цели.
        expense_for_first_goal = Expense.objects.create(
            user=self.user,
            title="Покупка 1",
            amount=Decimal("1000.00"),
            category=self.category,
            date="2026-09-01",
            description="Покупка",
            goal=self.goal,
        )

        # Расход для второй цели.
        Expense.objects.create(
            user=self.user,
            title="Покупка 2",
            amount=Decimal("2000.00"),
            category=self.category,
            date="2026-09-01",
            description="Покупка",
            goal=self.second_goal,
        )

        # Запрашиваем расходы только первой финансовой цели.
        response = self.client.get(
            "/api/v1/expenses/",
            {
                "goal": self.goal.id
            },
        )

        # Проверяем успешный запрос.
        assert response.status_code == 200

        # Получаем список результатов.
        results = response.data["results"]

        # Должен вернуться только один расход.
        assert len(results) == 1

        # Это должен быть расход первой цели.
        assert results[0]["id"] == expense_for_first_goal.id

    def test_user_cannot_change_expense_to_other_users_goal(self):
        """
        Проверяет защиту при изменении существующего расхода.

        Сценарий:

        1. Расход принадлежит user1.
        2. Расход связан с собственной целью user1.
        3. user1 пытается изменить goal
           на цель user2.

        Ожидаемое поведение:

        - API возвращает HTTP 400;
        - старая связь с self.goal сохраняется.

        Этот тест дополняет проверку создания расхода
        с чужой целью.

        Таким образом мы закрываем оба потенциальных
        пути нарушения безопасности:

        CREATE:
            нельзя создать расход с чужой целью.

        UPDATE:
            нельзя изменить существующий расход
            на чужую цель.
        """

        expense = Expense.objects.create(
            user=self.user,
            title="Покупка",
            amount=Decimal("1000.00"),
            category=self.category,
            date="2026-09-01",
            description="Покупка",
            goal=self.goal,
        )

        response = self.client.patch(
            f"/api/v1/expenses/{expense.id}/",
            {
                "goal": self.other_goal.id
            },
            format="json",
        )

        # Запрос должен быть отклонён.
        assert response.status_code == 400

        # Получаем актуальное состояние расхода.
        expense.refresh_from_db()

        # Проверяем, что старая цель осталась.
        assert expense.goal == self.goal