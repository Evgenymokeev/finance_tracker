from rest_framework.permissions import BasePermission

from .models import HouseholdMembership


class IsHouseholdOwner(BasePermission):
    """
    Разрешает изменение и удаление Household
    только пользователю с ролью OWNER.
    """

    def has_object_permission(
        self,
        request,
        view,
        obj,
    ):
        return HouseholdMembership.objects.filter(
            household=obj,
            user=request.user,
            role=HouseholdMembership.Role.OWNER,
        ).exists()