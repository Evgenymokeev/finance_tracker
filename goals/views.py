from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .deposit_serializers import GoalDepositSerializer
from .models import FinancialGoal
from .serializers import FinancialGoalSerializer
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
        return FinancialGoal.objects.filter(
            user=self.request.user
        )

    def perform_create(self, serializer):
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
        - если после пополнения достигнут target_amount,
          цель становится completed.
        """

        goal = self.get_object()

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

        serializer = GoalDepositSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        amount = serializer.validated_data["amount"]

        goal.current_amount += amount

        if goal.current_amount >= goal.target_amount:
            goal.current_amount = goal.target_amount
            goal.status = FinancialGoal.Status.COMPLETED

        goal.save()

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
        """

        goal = self.get_object()

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

        serializer = GoalWithdrawSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        amount = serializer.validated_data["amount"]

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

        if (
            goal.current_amount < goal.target_amount
            and goal.status
            == FinancialGoal.Status.COMPLETED
        ):
            goal.status = FinancialGoal.Status.ACTIVE

        goal.save()

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
        """

        goal = self.get_object()

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
