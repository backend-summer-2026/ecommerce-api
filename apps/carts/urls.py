from django.urls import path

from apps.carts.views import (
    AddToCartAPIView,
    CartDetailAPIView,
    CartItemDetailAPIView,
    CartSummaryAPIView,
    ClearCartAPIView,
    MergeCartAPIView,
)

app_name = 'carts'

urlpatterns = [
    path('', CartDetailAPIView.as_view(), name='cart-detail'),
    path('count/', CartSummaryAPIView.as_view(), name='cart-summary'),
    path('items/', AddToCartAPIView.as_view(), name='cart-add-item'),
    path('items/<int:item_id>/', CartItemDetailAPIView.as_view(), name='cart-item-detail'),
    path('clear/', ClearCartAPIView.as_view(), name='cart-clear'),
    path('merge/', MergeCartAPIView.as_view(), name='cart-merge'),
]
