from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FinancialGoal, GoalAutomaticSaving
from .serializers import GoalAutomaticSavingSerializer
from .services import calculate_next_run_at


class GoalAutomaticSavingView(APIView):
    permission_classes = [IsAuthenticated]

    def get_goal(self, request, goal_id):
        return get_object_or_404(
            FinancialGoal,
            id=goal_id,
            user=request.user,
        )

    def get(self, request, goal_id):
        goal = self.get_goal(request, goal_id)

        automatic_saving = get_object_or_404(
            GoalAutomaticSaving,
            goal=goal,
        )

        serializer = GoalAutomaticSavingSerializer(automatic_saving)

        return Response(serializer.data)

    def post(self, request, goal_id):
        goal = self.get_goal(request, goal_id)

        if goal.status != FinancialGoal.Status.ACTIVE:
            return Response(
                {
                    "detail": (
                        "Automatic saving can only be created "
                        "for an active goal."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if GoalAutomaticSaving.objects.filter(goal=goal).exists():
            return Response(
                {
                    "detail": (
                        "Automatic saving already exists "
                        "for this goal."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = GoalAutomaticSavingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        frequency = serializer.validated_data["frequency"]
        interval = serializer.validated_data.get("interval")

        next_run_at = calculate_next_run_at(
            timezone.now(),
            frequency,
            interval,
        )

        automatic_saving = serializer.save(
            goal=goal,
            next_run_at=next_run_at,
        )

        return Response(
            GoalAutomaticSavingSerializer(automatic_saving).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request, goal_id):
        goal = self.get_goal(request, goal_id)

        automatic_saving = get_object_or_404(
            GoalAutomaticSaving,
            goal=goal,
        )

        old_frequency = automatic_saving.frequency
        old_interval = automatic_saving.interval
        old_is_active = automatic_saving.is_active

        serializer = GoalAutomaticSavingSerializer(
            automatic_saving,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        frequency = serializer.validated_data.get(
            "frequency",
            old_frequency,
        )
        interval = serializer.validated_data.get(
            "interval",
            old_interval,
        )
        is_active = serializer.validated_data.get(
            "is_active",
            old_is_active,
        )

        frequency_changed = frequency != old_frequency
        interval_changed = interval != old_interval
        reactivated = not old_is_active and is_active

        if frequency_changed or interval_changed or reactivated:
            next_run_at = calculate_next_run_at(
                timezone.now(),
                frequency,
                interval,
            )

            automatic_saving = serializer.save(
                next_run_at=next_run_at,
            )
        else:
            automatic_saving = serializer.save()

        return Response(
            GoalAutomaticSavingSerializer(automatic_saving).data,
        )

    def delete(self, request, goal_id):
        goal = self.get_goal(request, goal_id)

        automatic_saving = get_object_or_404(
            GoalAutomaticSaving,
            goal=goal,
        )

        automatic_saving.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )