from apps.dashboard.serializers.analytics_serializers import (
    DailyMetricSnapshotSerializer,
    SalesChartPointSerializer,
    TopProductSerializer,
    TopCustomerSerializer,
    KPIDashboardSerializer,
)
from apps.dashboard.serializers.inventory_serializers import (
    DashboardInventoryListSerializer,
    StockAdjustmentSerializer,
    StockMovementLogSerializer,
    InventoryStatisticsSerializer,
)
from apps.dashboard.serializers.order_serializers import (
    DashboardOrderItemSerializer,
    DashboardOrderAddressSerializer,
    DashboardOrderListSerializer,
    DashboardOrderDetailSerializer,
    OrderStatusUpdateSerializer,
    OrderInternalNoteSerializer,
)
from apps.dashboard.serializers.customer_serializers import (
    DashboardCustomerListSerializer,
    DashboardCustomerDetailSerializer,
    CustomerStatusToggleSerializer,
)
from apps.dashboard.serializers.alert_audit_serializers import (
    StaffActivityLogSerializer,
    SystemAlertSerializer,
)

__all__ = [
    'DailyMetricSnapshotSerializer',
    'SalesChartPointSerializer',
    'TopProductSerializer',
    'TopCustomerSerializer',
    'KPIDashboardSerializer',
    'DashboardInventoryListSerializer',
    'StockAdjustmentSerializer',
    'StockMovementLogSerializer',
    'InventoryStatisticsSerializer',
    'DashboardOrderItemSerializer',
    'DashboardOrderAddressSerializer',
    'DashboardOrderListSerializer',
    'DashboardOrderDetailSerializer',
    'OrderStatusUpdateSerializer',
    'OrderInternalNoteSerializer',
    'DashboardCustomerListSerializer',
    'DashboardCustomerDetailSerializer',
    'CustomerStatusToggleSerializer',
    'StaffActivityLogSerializer',
    'SystemAlertSerializer',
]
