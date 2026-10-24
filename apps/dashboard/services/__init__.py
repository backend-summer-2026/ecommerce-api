from apps.dashboard.services.audit_service import log_staff_activity
from apps.dashboard.services.analytics_service import (
    get_dashboard_kpis,
    get_sales_chart_series,
    get_top_products_report,
    get_top_customers_report,
)
from apps.dashboard.services.inventory_service import (
    adjust_variant_stock,
    get_inventory_statistics,
)

__all__ = [
    'log_staff_activity',
    'get_dashboard_kpis',
    'get_sales_chart_series',
    'get_top_products_report',
    'get_top_customers_report',
    'adjust_variant_stock',
    'get_inventory_statistics',
]
