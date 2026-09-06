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
    - пополнять свои цели.
    """

    serializer_class = FinancialGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Возвращает только финансовые цели
        текущего пользователя.
        """

        return FinancialGoal.objects.filter(
            user=self.request.user
        )

    def perform_create(self, serializer):
        """
        Автоматически привязывает новую цель
        к текущему авторизованному пользователю.
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

        Пример запроса:

        {
            "amount": "5000.00"
        }

        После пополнения:
        - увеличивается current_amount;
        - пересчитывается progress_percent;
        - пересчитывается remaining_amount;
        - если цель достигнута, status становится completed.
        """

        goal = self.get_object()

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

        Пример запроса:

        {
            "amount": "5000.00"
        }

        После снятия:
        - уменьшается current_amount;
        - пересчитывается progress_percent;
        - пересчитывается remaining_amount;
        - если цель ранее была completed,
          она снова становится active.
        """

        goal = self.get_object()

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
