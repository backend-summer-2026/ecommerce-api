from django.urls import path
from apps.dashboard.views import (
    DashboardAuditLogsAPIView,
    DashboardCustomerDetailAPIView,
    DashboardCustomerListAPIView,
    DashboardCustomerToggleStatusAPIView,
    DashboardInventoryListAPIView,
    DashboardInventoryStatsAPIView,
    DashboardLowStockAPIView,
    DashboardOrderDetailAPIView,
    DashboardOrderListAPIView,
    DashboardOrderNotesListCreateAPIView,
    DashboardOrderStatusUpdateAPIView,
    DashboardOverviewAPIView,
    DashboardSalesChartAPIView,
    DashboardStockAdjustmentAPIView,
    DashboardStockMovementLogsAPIView,
    DashboardSystemAlertResolveAPIView,
    DashboardSystemAlertsListAPIView,
    DashboardTopCustomersAPIView,
    DashboardTopProductsAPIView,
)

app_name = 'dashboard'

urlpatterns = [
    # Analytics
    path('analytics/overview/', DashboardOverviewAPIView.as_view(), name='analytics-overview'),
    path('analytics/sales-chart/', DashboardSalesChartAPIView.as_view(), name='analytics-sales-chart'),
    path('analytics/top-products/', DashboardTopProductsAPIView.as_view(), name='analytics-top-products'),
    path('analytics/top-customers/', DashboardTopCustomersAPIView.as_view(), name='analytics-top-customers'),

    # Inventory
    path('inventory/', DashboardInventoryListAPIView.as_view(), name='inventory-list'),
    path('inventory/low-stock/', DashboardLowStockAPIView.as_view(), name='inventory-low-stock'),
    path('inventory/stats/', DashboardInventoryStatsAPIView.as_view(), name='inventory-stats'),
    path('inventory/<int:variant_id>/adjust/', DashboardStockAdjustmentAPIView.as_view(), name='inventory-adjust'),
    path('inventory/logs/', DashboardStockMovementLogsAPIView.as_view(), name='inventory-logs'),

    # Orders
    path('orders/', DashboardOrderListAPIView.as_view(), name='order-list'),
    path('orders/<str:order_number>/', DashboardOrderDetailAPIView.as_view(), name='order-detail'),
    path('orders/<str:order_number>/status/', DashboardOrderStatusUpdateAPIView.as_view(), name='order-status-update'),
    path('orders/<str:order_number>/notes/', DashboardOrderNotesListCreateAPIView.as_view(), name='order-notes'),

    # Customers
    path('customers/', DashboardCustomerListAPIView.as_view(), name='customer-list'),
    path('customers/<int:pk>/', DashboardCustomerDetailAPIView.as_view(), name='customer-detail'),
    path('customers/<int:pk>/toggle-status/', DashboardCustomerToggleStatusAPIView.as_view(), name='customer-toggle-status'),

    # Audit & Alerts
    path('audit-logs/', DashboardAuditLogsAPIView.as_view(), name='audit-logs'),
    path('alerts/', DashboardSystemAlertsListAPIView.as_view(), name='alerts-list'),
    path('alerts/<int:pk>/resolve/', DashboardSystemAlertResolveAPIView.as_view(), name='alert-resolve'),
]
