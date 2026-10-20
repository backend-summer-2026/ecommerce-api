import uuid
from typing import Optional

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts.models import Cart, CartItem
from apps.carts.serializers import (
    AddToCartSerializer,
    CartSerializer,
    CartSummarySerializer,
    MergeCartSerializer,
    UpdateCartItemSerializer,
)
from apps.carts.services import CartService


def _attach_cart_headers(response: Response, cart: Optional[Cart], new_session_key: Optional[str] = None) -> Response:
    """
    Attaches X-Session-Key and X-Cart-ID headers to HTTP responses for seamless guest session tracking.
    """
    if new_session_key:
        response['X-Session-Key'] = new_session_key
    elif cart and cart.session_key:
        response['X-Session-Key'] = cart.session_key

    if cart:
        response['X-Cart-ID'] = str(cart.id)

    return response


class CartDetailAPIView(APIView):
    """
    GET /api/v1/cart/
    Retrieves the customer's active shopping cart with all items, computed totals,
    discounts, and real-time alerts.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        cart, created, new_key = CartService.get_or_create_cart(request)
        optimized_cart = CartService.get_optimized_cart(cart.id) or cart
        serializer = CartSerializer(optimized_cart, context={'request': request})
        response = Response(serializer.data, status=status.HTTP_200_OK)
        return _attach_cart_headers(response, cart, new_key)


class CartSummaryAPIView(APIView):
    """
    GET /api/v1/cart/count/
    Returns a lightweight summary of cart items and total price, ideal for navbar badges.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        cart = CartService.get_active_cart(request)
        if not cart:
            data = {
                'id': None,
                'total_items': 0,
                'unique_items_count': 0,
                'total_price': '0.00',
                'is_empty': True,
            }
            return Response(data, status=status.HTTP_200_OK)

        serializer = CartSummarySerializer(cart)
        return _attach_cart_headers(Response(serializer.data, status=status.HTTP_200_OK), cart)


class AddToCartAPIView(APIView):
    """
    POST /api/v1/cart/items/
    Adds a product variant to the customer's active cart or increments existing quantity.
    Enforces real-time stock availability check.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        variant_id = serializer.validated_data['variant_id']
        quantity = serializer.validated_data.get('quantity', 1)

        cart, created, new_key = CartService.get_or_create_cart(request)

        try:
            CartService.add_item(cart=cart, variant_id=variant_id, quantity=quantity)
        except ValidationError as e:
            detail = e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)}
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        optimized_cart = CartService.get_optimized_cart(cart.id) or cart
        cart_data = CartSerializer(optimized_cart, context={'request': request}).data
        response = Response(cart_data, status=status.HTTP_201_CREATED)
        return _attach_cart_headers(response, cart, new_key)


class CartItemDetailAPIView(APIView):
    """
    PATCH /api/v1/cart/items/<int:item_id>/ - Update item quantity
    DELETE /api/v1/cart/items/<int:item_id>/ - Remove item from cart
    """
    permission_classes = [AllowAny]

    def patch(self, request, item_id: int):
        serializer = UpdateCartItemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cart = CartService.get_active_cart(request)
        if not cart:
            return Response({'detail': "Active cart not found."}, status=status.HTTP_404_NOT_FOUND)

        quantity = serializer.validated_data['quantity']

        try:
            CartService.update_item_quantity(cart=cart, item_id=item_id, quantity=quantity)
        except CartItem.DoesNotExist:
            return Response(
                {'detail': "Cart item not found in current cart."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as e:
            detail = e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)}
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        optimized_cart = CartService.get_optimized_cart(cart.id) or cart
        cart_data = CartSerializer(optimized_cart, context={'request': request}).data
        response = Response(cart_data, status=status.HTTP_200_OK)
        return _attach_cart_headers(response, cart)

    def delete(self, request, item_id: int):
        cart = CartService.get_active_cart(request)
        if not cart:
            return Response({'detail': "Active cart not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            CartService.remove_item(cart=cart, item_id=item_id)
        except CartItem.DoesNotExist:
            return Response(
                {'detail': "Cart item not found in current cart."},
                status=status.HTTP_404_NOT_FOUND,
            )

        optimized_cart = CartService.get_optimized_cart(cart.id) or cart
        cart_data = CartSerializer(optimized_cart, context={'request': request}).data
        response = Response(cart_data, status=status.HTTP_200_OK)
        return _attach_cart_headers(response, cart)


# Backward-compatible aliases
UpdateCartItemAPIView = CartItemDetailAPIView
RemoveCartItemAPIView = CartItemDetailAPIView


class ClearCartAPIView(APIView):
    """
    POST /api/v1/cart/clear/ (or DELETE)
    Empties all items from the customer's active cart.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        return self._clear(request)

    def delete(self, request):
        return self._clear(request)

    def _clear(self, request):
        cart = CartService.get_active_cart(request)
        if not cart:
            cart, _, new_key = CartService.get_or_create_cart(request)
            optimized_cart = CartService.get_optimized_cart(cart.id) or cart
            cart_data = CartSerializer(optimized_cart, context={'request': request}).data
            response = Response(cart_data, status=status.HTTP_200_OK)
            return _attach_cart_headers(response, cart, new_key)

        CartService.clear_cart(cart)
        optimized_cart = CartService.get_optimized_cart(cart.id) or cart
        cart_data = CartSerializer(optimized_cart, context={'request': request}).data
        response = Response(cart_data, status=status.HTTP_200_OK)
        return _attach_cart_headers(response, cart)


class MergeCartAPIView(APIView):
    """
    POST /api/v1/cart/merge/
    Merges an anonymous guest session cart into the authenticated user's cart.
    Requires Authorization: Bearer <token>.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MergeCartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        guest_cart_id = serializer.validated_data.get('guest_cart_id')
        guest_session_key = serializer.validated_data.get('guest_session_key')

        try:
            user_cart = CartService.merge_carts(
                user=request.user,
                guest_cart_id=guest_cart_id,
                guest_session_key=guest_session_key,
            )
        except ValidationError as e:
            detail = e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)}
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        optimized_cart = CartService.get_optimized_cart(user_cart.id) or user_cart
        cart_data = CartSerializer(optimized_cart, context={'request': request}).data
        return Response(cart_data, status=status.HTTP_200_OK)
