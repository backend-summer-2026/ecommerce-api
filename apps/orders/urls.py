from django.urls import path

from apps.orders.views import (
    AdminOrderListView,
    AdminOrderNotesView,
    AdminOrderStatusUpdateView,
    CheckoutPreviewView,
    CouponValidateView,
    OrderCancelView,
    OrderDetailView,
    OrderInvoiceView,
    OrderListCreateView,
    OrderTrackingView,
)

app_name = 'orders'

urlpatterns = [
    # Checkout preview & coupon validation
    path('checkout/preview/', CheckoutPreviewView.as_view(), name='checkout-preview'),
    path('coupons/validate/', CouponValidateView.as_view(), name='coupon-validate'),

    # Admin management endpoints (placed before parameterized paths to prevent URL collision)
    path('admin/', AdminOrderListView.as_view(), name='admin-order-list'),
    path('admin/<str:order_number>/status/', AdminOrderStatusUpdateView.as_view(), name='admin-order-status'),
    path('admin/<str:order_number>/notes/', AdminOrderNotesView.as_view(), name='admin-order-notes'),

    # Customer orders list & creation
    path('', OrderListCreateView.as_view(), name='order-list-create'),

    # Single order parameterized endpoints
    path('<str:order_number>/', OrderDetailView.as_view(), name='order-detail'),
    path('<str:order_number>/cancel/', OrderCancelView.as_view(), name='order-cancel'),
    path('<str:order_number>/tracking/', OrderTrackingView.as_view(), name='order-tracking'),
    path('<str:order_number>/invoice/', OrderInvoiceView.as_view(), name='order-invoice'),
]
