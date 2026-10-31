from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from .deposit_serializers import GoalDepositSerializer
from .models import (
    FinancialGoal,
    GoalAutomaticSaving,
    GoalSavingTransaction,
)
from .serializers import (
    FinancialGoalSerializer,
    GoalSavingTransactionSerializer,
)
from .withdraw_serializers import GoalWithdrawSerializer


@extend_schema(
    tags=["Goals"],
)
class FinancialGoalViewSet(viewsets.ModelViewSet):
    """
    CRUD API для финансовых целей пользователя.

    Пользователь может:
    - создавать свои цели;
    - просматривать только свои цели;
    - изменять только свои цели;
    - удалять только свои цели;
    - пополнять свои цели;
    - снимать деньги со своих целей;
    - отменять активные цели.
    """

    serializer_class = FinancialGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Возвращает только финансовые цели текущего пользователя.
        """

        return FinancialGoal.objects.filter(
            user=self.request.user
        )

    def _get_locked_object(self):
        """
        Получает финансовую цель с блокировкой строки в БД.

        select_for_update() предотвращает одновременное изменение
        баланса и статуса одной цели несколькими запросами.

        Метод должен вызываться внутри transaction.atomic().
        """

        queryset = (
            self.filter_queryset(self.get_queryset())
            .select_for_update()
        )

        goal = get_object_or_404(
            queryset,
            pk=self.kwargs["pk"],
        )

        self.check_object_permissions(
            self.request,
            goal,
        )

        return goal

    def perform_create(self, serializer):
        """
        Автоматически связывает новую цель с текущим пользователем.
        """

        serializer.save(
            user=self.request.user
        )

    @extend_schema(
        request=GoalDepositSerializer,
        responses=FinancialGoalSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="deposit",
    )
    def deposit(self, request, pk=None):
        """
        Пополняет финансовую цель.

        POST /api/v1/goals/{id}/deposit/

        Пример:
        {
            "amount": "5000.00"
        }

        Правила:
        - cancelled цель нельзя пополнять;
        - completed цель нельзя пополнять;
        - сумма пополнения не может превышать остаток до цели;
        - при достижении target_amount цель становится completed.

        Изменение баланса и создание транзакции выполняются
        в одной атомарной операции.
        """

        serializer = GoalDepositSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        amount = serializer.validated_data["amount"]

        with transaction.atomic():
            goal = self._get_locked_object()

            # Отменённую цель больше нельзя пополнять.
            if goal.status == FinancialGoal.Status.CANCELLED:
                return Response(
                    {
                        "status": (
                            "Cancelled goals cannot receive deposits."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Завершённую цель нельзя пополнять повторно.
            if goal.status == FinancialGoal.Status.COMPLETED:
                return Response(
                    {
                        "status": (
                            "Completed goals cannot receive deposits."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            remaining_amount = (
                goal.target_amount - goal.current_amount
            )

            if remaining_amount <= 0:
                return Response(
                    {
                        "status": (
                            "Goal has no remaining amount to deposit."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Нельзя зачислить больше, чем осталось до цели.
            effective_amount = min(
                amount,
                remaining_amount,
            )

            goal.current_amount += effective_amount

            # Проверяем достижение целевой суммы.
            if goal.current_amount >= goal.target_amount:
                goal.current_amount = goal.target_amount
                goal.status = FinancialGoal.Status.COMPLETED

            goal.save()

            # Если цель достигнута, отключаем автоматические накопления.
            # Обновление выполняется в той же транзакции,
            # что изменение баланса и создание истории пополнения.
            if goal.status == FinancialGoal.Status.COMPLETED:
                GoalAutomaticSaving.objects.filter(
                    goal=goal,
                    is_active=True,
                ).update(
                    is_active=False,
                )

            # Сохраняем историю пополнения.
            GoalSavingTransaction.objects.create(
                goal=goal,
                amount=effective_amount,
                transaction_type=(
                    GoalSavingTransaction.TransactionType.DEPOSIT
                ),
                source=(
                    GoalSavingTransaction.Source.MANUAL
                ),
            )

            response_serializer = FinancialGoalSerializer(
                goal
            )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=GoalWithdrawSerializer,
        responses=FinancialGoalSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="withdraw",
    )
    def withdraw(self, request, pk=None):
        """
        Снимает деньги с финансовой цели.

        POST /api/v1/goals/{id}/withdraw/

        Пример:
        {
            "amount": "5000.00"
        }

        Правила:
        - cancelled цель нельзя изменять;
        - нельзя снять больше текущей суммы;
        - если completed цель уменьшилась ниже target_amount,
          она снова становится active.

        Изменение баланса и создание транзакции выполняются
        в одной атомарной операции.
        """

        serializer = GoalWithdrawSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        amount = serializer.validated_data["amount"]

        with transaction.atomic():
            goal = self._get_locked_object()

            # Отменённую цель больше нельзя изменять.
            if goal.status == FinancialGoal.Status.CANCELLED:
                return Response(
                    {
                        "status": (
                            "Cancelled goals cannot be withdrawn from."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Проверяем доступный баланс после получения блокировки.
            if amount > goal.current_amount:
                return Response(
                    {
                        "amount": (
                            "Withdraw amount cannot exceed "
                            "the current goal amount."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            goal.current_amount -= amount

            # Если снятие уменьшило завершённую цель ниже target,
            # возвращаем её в активное состояние.
            if (
                goal.current_amount < goal.target_amount
                and goal.status == FinancialGoal.Status.COMPLETED
            ):
                goal.status = FinancialGoal.Status.ACTIVE

            goal.save()

            # Сохраняем историю снятия.
            GoalSavingTransaction.objects.create(
                goal=goal,
                amount=amount,
                transaction_type=(
                    GoalSavingTransaction.TransactionType.WITHDRAWAL
                ),
                source=(
                    GoalSavingTransaction.Source.MANUAL
                ),
            )

            response_serializer = FinancialGoalSerializer(
                goal
            )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses=FinancialGoalSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="cancel",
    )
    def cancel(self, request, pk=None):
        """
        Отменяет финансовую цель.

        POST /api/v1/goals/{id}/cancel/

        Правила:
        - active -> cancelled;
        - completed нельзя отменить;
        - cancelled нельзя отменить повторно;
        - текущая накопленная сумма не изменяется.

        Изменение статуса выполняется атомарно.
        """

        with transaction.atomic():
            goal = self._get_locked_object()

            # Завершённую цель отменять нельзя.
            if goal.status == FinancialGoal.Status.COMPLETED:
                return Response(
                    {
                        "status": (
                            "Completed goals cannot be cancelled."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Нельзя отменить уже отменённую цель повторно.
            if goal.status == FinancialGoal.Status.CANCELLED:
                return Response(
                    {
                        "status": (
                            "Goal is already cancelled."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Active -> Cancelled.
            goal.status = FinancialGoal.Status.CANCELLED
            goal.save()

            response_serializer = FinancialGoalSerializer(
                goal
            )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses=GoalSavingTransactionSerializer(many=True),
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="transactions",
    )
    def transactions(self, request, pk=None):
        """
        Возвращает историю операций финансовой цели.

        История содержит:
        - ручные пополнения;
        - ручные снятия;
        - автоматические пополнения.

        Доступ к истории возможен только для финансовой цели
        текущего авторизованного пользователя.

        Endpoint предназначен только для чтения.
        """

        goal = self.get_object()

        transactions = GoalSavingTransaction.objects.filter(
            goal=goal
        )

        serializer = GoalSavingTransactionSerializer(
            transactions,
            many=True,
        )

        return Response(
            serializer.data
        )
