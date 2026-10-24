from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.payments.models import Refund
from apps.dashboard.models import DailyMetricSnapshot

User = get_user_model()


def get_dashboard_kpis(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Computes aggregated high-level business KPIs over a given time window.
    Defaults to the last 30 days if dates are not provided.
    """
    today = timezone.localdate()
    if not date_to:
        date_to = today
    if not date_from:
        date_from = date_to - timedelta(days=29)

    # Current period metrics
    orders_qs = Order.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    total_orders = orders_qs.count()

    paid_orders = orders_qs.filter(payment_status='PAID')
    rev_agg = paid_orders.aggregate(total_rev=Sum('total_price'), aov=Avg('total_price'))
    total_revenue = rev_agg['total_rev'] or Decimal('0.00')
    aov = rev_agg['aov'] or Decimal('0.00')

    completed_orders = orders_qs.filter(status__in=['DELIVERED', 'CONFIRMED', 'PROCESSING', 'SHIPPED']).count()
    cancelled_orders = orders_qs.filter(status='CANCELLED').count()

    items_agg = OrderItem.objects.filter(
        order__created_at__date__gte=date_from,
        order__created_at__date__lte=date_to,
    ).aggregate(total_items=Sum('quantity'))
    total_items_sold = items_agg['total_items'] or 0

    new_customers = User.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
        role='customer',
    ).count()

    refund_agg = Refund.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
        status='COMPLETED',
    ).aggregate(total_refund=Sum('amount'))
    refunded_amount = refund_agg['total_refund'] or Decimal('0.00')

    # Previous period for growth comparison
    delta_days = (date_to - date_from).days + 1
    prev_date_to = date_from - timedelta(days=1)
    prev_date_from = prev_date_to - timedelta(days=delta_days - 1)

    prev_orders = Order.objects.filter(created_at__date__gte=prev_date_from, created_at__date__lte=prev_date_to)
    prev_paid = prev_orders.filter(payment_status='PAID')
    prev_revenue = prev_paid.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    prev_total_orders = prev_orders.count()

    def calc_growth(current, previous):
        if previous and previous > 0:
            growth = ((float(current) - float(previous)) / float(previous)) * 100
            return round(growth, 1)
        return 100.0 if current > 0 else 0.0

    return {
        'period': {
            'date_from': str(date_from),
            'date_to': str(date_to),
            'days': delta_days,
        },
        'kpis': {
            'total_revenue': str(total_revenue),
            'total_orders': total_orders,
            'completed_orders_count': completed_orders,
            'cancelled_orders_count': cancelled_orders,
            'average_order_value': str(round(aov, 2)),
            'new_customers_count': new_customers,
            'total_items_sold': total_items_sold,
            'refunded_amount': str(refunded_amount),
        },
        'growth': {
            'revenue_growth_pct': calc_growth(total_revenue, prev_revenue),
            'orders_growth_pct': calc_growth(total_orders, prev_total_orders),
        },
    }


def get_sales_chart_series(days: int = 30) -> List[Dict[str, Any]]:
    """
    Returns daily timeseries data for revenue and order count over the last N days.
    """
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)

    # Fetch daily snapshots if exist
    snapshots = {
        s.date: s
        for s in DailyMetricSnapshot.objects.filter(date__gte=start_date, date__lte=today)
    }

    # Also aggregate real-time from orders for missing days
    orders_by_date = (
        Order.objects.filter(created_at__date__gte=start_date, created_at__date__lte=today)
        .values('created_at__date')
        .annotate(
            order_count=Count('id'),
            revenue=Sum('total_price', filter=Q(payment_status='PAID')),
        )
    )
    orders_map = {row['created_at__date']: row for row in orders_by_date}

    results = []
    current_day = start_date
    while current_day <= today:
        if current_day in snapshots:
            snap = snapshots[current_day]
            revenue = snap.total_revenue
            orders_count = snap.total_orders
        elif current_day in orders_map:
            row = orders_map[current_day]
            revenue = row['revenue'] or Decimal('0.00')
            orders_count = row['order_count'] or 0
        else:
            revenue = Decimal('0.00')
            orders_count = 0

        results.append({
            'date': str(current_day),
            'revenue': str(revenue),
            'orders_count': orders_count,
        })
        current_day += timedelta(days=1)

    return results


def get_top_products_report(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Returns top selling products aggregated by quantity sold and total revenue.
    """
    items = (
        OrderItem.objects.filter(order__payment_status='PAID')
        .values('variant__product__id', 'variant__product__name', 'variant__sku')
        .annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('total_price'),
        )
        .order_by('-total_sold')[:limit]
    )

    results = []
    for item in items:
        results.append({
            'product_id': item['variant__product__id'],
            'product_name': item['variant__product__name'],
            'sku': item['variant__sku'],
            'total_sold': item['total_sold'] or 0,
            'total_revenue': str(item['total_revenue'] or Decimal('0.00')),
        })
    return results


def get_top_customers_report(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Returns top customer accounts by completed order count and total spend.
    """
    customers = (
        Order.objects.filter(payment_status='PAID')
        .values('user__id', 'user__email', 'user__first_name', 'user__last_name', 'user__phone_number')
        .annotate(
            total_orders=Count('id'),
            total_spent=Sum('total_price'),
        )
        .order_by('-total_spent')[:limit]
    )

    results = []
    for c in customers:
        full_name = f"{c['user__first_name'] or ''} {c['user__last_name'] or ''}".strip() or 'N/A'
        results.append({
            'customer_id': c['user__id'],
            'email': c['user__email'],
            'name': full_name,
            'phone_number': c['user__phone_number'],
            'total_orders': c['total_orders'] or 0,
            'total_spent': str(c['total_spent'] or Decimal('0.00')),
        })
    return results
