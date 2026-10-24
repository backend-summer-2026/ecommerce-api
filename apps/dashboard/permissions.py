from rest_framework.permissions import BasePermission


class IsStaffOrAdminUser(BasePermission):
    """
    Allows access only to authenticated users who are staff members,
    have the 'admin' role, or are superusers.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.role == 'admin' or request.user.is_superuser)
        )


class IsAdminOnly(BasePermission):
    """
    Allows access only to superusers or users explicitly designated as admin.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.role == 'admin')
        )
