from django.urls import path

from apps.payments.views import (
    AdminPaymentDetailView,
    AdminPaymentListView,
    AdminRefundCreateView,
    AdminRefundDetailView,
    AdminRefundListView,
    AdminTransactionListView,
    ClickWebhookView,
    PaymeWebhookView,
    PayWithSavedCardView,
    PaymentCancelView,
    PaymentDetailView,
    PaymentInitializeView,
    PaymentListView,
    SavedCardDefaultView,
    SavedCardDeleteView,
    SavedCardListCreateView,
    SavedCardVerifyView,
    UzumWebhookView,
)

app_name = 'payments'

urlpatterns = [
    # Customer payment operations
    path('initialize/', PaymentInitializeView.as_view(), name='payment-initialize'),
    path('pay-with-card/', PayWithSavedCardView.as_view(), name='pay-with-card'),

    # Customer saved bank cards (1-click checkout)
    path('cards/', SavedCardListCreateView.as_view(), name='card-list-create'),
    path('cards/<int:pk>/verify/', SavedCardVerifyView.as_view(), name='card-verify'),
    path('cards/<int:pk>/default/', SavedCardDefaultView.as_view(), name='card-set-default'),
    path('cards/<int:pk>/', SavedCardDeleteView.as_view(), name='card-delete'),

    # Payment gateways server-to-server callbacks (Webhooks)
    path('webhooks/payme/', PaymeWebhookView.as_view(), name='webhook-payme'),
    path('webhooks/click/', ClickWebhookView.as_view(), name='webhook-click'),
    path('webhooks/uzum/', UzumWebhookView.as_view(), name='webhook-uzum'),

    # Admin management & financial audit endpoints
    path('admin/refunds/', AdminRefundListView.as_view(), name='admin-refund-list'),
    path('admin/refunds/<str:refund_number>/', AdminRefundDetailView.as_view(), name='admin-refund-detail'),
    path('admin/transactions/', AdminTransactionListView.as_view(), name='admin-transaction-list'),
    path('admin/', AdminPaymentListView.as_view(), name='admin-payment-list'),
    path('admin/<str:payment_number>/refund/', AdminRefundCreateView.as_view(), name='admin-payment-refund'),
    path('admin/<str:payment_number>/', AdminPaymentDetailView.as_view(), name='admin-payment-detail'),

    # Customer payment listing & single payment parameterized endpoints
    path('', PaymentListView.as_view(), name='payment-list'),
    path('<str:payment_number>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('<str:payment_number>/cancel/', PaymentCancelView.as_view(), name='payment-cancel'),
]
