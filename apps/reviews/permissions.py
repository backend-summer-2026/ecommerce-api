from rest_framework import permissions


class IsReviewOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission allowing read access to anyone,
    but write/delete access only to the review author (or staff/admin).
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff or request.user.is_superuser:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'review') and hasattr(obj.review, 'user'):
            return obj.review.user == request.user
        return False


class IsAdminOrStaffUser(permissions.BasePermission):
    """
    Permission allowing access exclusively to staff/admin members.
    Used for moderation, review rejection, and seller reply management.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )
