from rest_framework import permissions


class IsNotificationOwner(permissions.BasePermission):
    """
    Object-level permission allowing only the owner of a notification
    (or administrative staff) to view, update, or delete it.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class IsAdminOrStaff(permissions.BasePermission):
    """
    Permission allowing access only to admin/staff users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser))
