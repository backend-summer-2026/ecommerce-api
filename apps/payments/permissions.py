from rest_framework import permissions


class IsOwnerOrStaff(permissions.BasePermission):
    """
    Object-level permission allowing only the owner of the payment/card/refund
    or staff/admin users to access and manipulate it.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff:
            return True

        # Check user attribute on the object (Payment, SavedCard, etc.)
        if hasattr(obj, 'user'):
            return obj.user == request.user

        # If object is Refund, check payment user
        if hasattr(obj, 'payment') and hasattr(obj.payment, 'user'):
            return obj.payment.user == request.user

        return False


class IsStaffUser(permissions.BasePermission):
    """
    Permission allowing only staff administrators.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
