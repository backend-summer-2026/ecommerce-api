from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db.models import Sum
from rest_framework import serializers

from apps.orders.models import Order

User = get_user_model()


class DashboardCustomerListSerializer(serializers.ModelSerializer):
    """
    Customer summary representation in backoffice CRM list.
    """
    total_orders_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'role',
            'is_active',
            'is_staff',
            'total_orders_count',
            'total_spent',
            'created_at',
        ]

    def get_total_orders_count(self, obj) -> int:
        return obj.orders.count()

    def get_total_spent(self, obj) -> str:
        spent = obj.orders.filter(payment_status='PAID').aggregate(total=Sum('total_price'))['total']
        return str(spent or Decimal('0.00'))


class DashboardCustomerDetailSerializer(serializers.ModelSerializer):
    """
    Full customer CRM dossier including aggregated financial lifetime value and recent orders.
    """
    total_orders_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    recent_orders = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'role',
            'is_active',
            'is_staff',
            'total_orders_count',
            'total_spent',
            'recent_orders',
            'created_at',
            'updated_at',
        ]

    def get_total_orders_count(self, obj) -> int:
        return obj.orders.count()

    def get_total_spent(self, obj) -> str:
        spent = obj.orders.filter(payment_status='PAID').aggregate(total=Sum('total_price'))['total']
        return str(spent or Decimal('0.00'))

    def get_recent_orders(self, obj):
        from apps.dashboard.serializers.order_serializers import DashboardOrderListSerializer
        orders = obj.orders.order_by('-created_at')[:10]
        return DashboardOrderListSerializer(orders, many=True).data


class CustomerStatusToggleSerializer(serializers.Serializer):
    """
    Payload for activating or suspending a customer account.
    """
    is_active = serializers.BooleanField(
        required=True,
        help_text="Set customer account active or blocked status",
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Operational or security justification for status change",
    )
