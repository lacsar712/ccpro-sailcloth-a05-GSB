from rest_framework.permissions import BasePermission

from accounts.models import User


class IsAdminRole(BasePermission):
    """仅管理员角色可写；操作工只读。"""

    message = "仅管理员可维护树脂浴浓度带"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "role", None) == User.ROLE_ADMIN
        )
