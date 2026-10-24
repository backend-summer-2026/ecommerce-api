from rest_framework import serializers
from apps.dashboard.models import DailyMetricSnapshot


class DailyMetricSnapshotSerializer(serializers.ModelSerializer):
    """
    Serializer for daily aggregated KPI snapshots.
    """
    class Meta:
        model = DailyMetricSnapshot
        fields = [
            'date',
            'total_revenue',
            'total_orders',
            'completed_orders_count',
            'cancelled_orders_count',
            'new_customers_count',
            'total_items_sold',
            'average_order_value',
            'refunded_amount',
            'extra_metrics',
            'created_at',
            'updated_at',
        ]


class SalesChartPointSerializer(serializers.Serializer):
    """
    Data point in daily/weekly sales and order timeseries chart.
    """
    date = serializers.CharField()
    revenue = serializers.CharField()
    orders_count = serializers.IntegerField()


class TopProductSerializer(serializers.Serializer):
    """
    Sales performance metrics for top products.
    """
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    sku = serializers.CharField()
    total_sold = serializers.IntegerField()
    total_revenue = serializers.CharField()


class TopCustomerSerializer(serializers.Serializer):
    """
    Top spender customer profile summary.
    """
    customer_id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    phone_number = serializers.CharField(allow_null=True)
    total_orders = serializers.IntegerField()
    total_spent = serializers.CharField()


class KPIDashboardSerializer(serializers.Serializer):
    """
    Executive overview KPI payload.
    """
    period = serializers.DictField()
    kpis = serializers.DictField()
    growth = serializers.DictField()
