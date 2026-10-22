from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.pagination import OrderPagination
from apps.orders.serializers import (
    AdminNotesUpdateSerializer,
    AdminStatusUpdateSerializer,
    CheckoutPreviewInputSerializer,
    CheckoutPreviewResponseSerializer,
    CouponDetailSerializer,
    CouponValidateInputSerializer,
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderInvoiceSerializer,
    OrderListSerializer,
    OrderStatusHistorySerializer,
)
from apps.orders.services import OrderService


class CheckoutPreviewView(APIView):
    """
    POST /api/v1/orders/checkout/preview/
    Computes real-time checkout totals, line item breakdown, stock checks,
    and coupon discount estimates prior to final order placement.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CheckoutPreviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            preview_data = OrderService.preview_checkout(
                user=request.user,
                shipping_method=serializer.validated_data.get('shipping_method', Order.ShippingMethod.STANDARD),
                coupon_code=serializer.validated_data.get('coupon_code'),
                region=serializer.validated_data.get('region', ''),
            )
            response_serializer = CheckoutPreviewResponseSerializer(preview_data, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response({'detail': detail[0] if len(detail) == 1 else detail}, status=status.HTTP_400_BAD_REQUEST)


class CouponValidateView(APIView):
    """
    POST /api/v1/orders/coupons/validate/
    Validates a voucher code against customer eligibility and subtotal.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CouponValidateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        coupon, discount_amount, message = OrderService.validate_coupon(
            coupon_code=serializer.validated_data['code'],
            user=request.user,
            subtotal=serializer.validated_data.get('subtotal', Decimal('0.00')),
        )

        return Response(
            {
                'is_valid': coupon is not None,
                'message': message,
                'code': coupon.code if coupon else serializer.validated_data['code'].strip().upper(),
                'discount_amount': discount_amount,
                'coupon': CouponDetailSerializer(coupon).data if coupon else None,
            },
            status=status.HTTP_200_OK,
        )


class OrderListCreateView(APIView):
    """
    GET  /api/v1/orders/ - List orders for the authenticated customer with pagination & filters.
    POST /api/v1/orders/ - Convert customer's active OPEN cart into an Order.
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = OrderPagination

    def get(self, request):
        queryset = (
            Order.objects.filter(user=request.user)
            .select_related('shipping_address')
            .prefetch_related('items')
            .order_by('-created_at')
        )

        order_status = request.query_params.get('status')
        if order_status:
            statuses = [s.strip() for s in order_status.split(',') if s.strip()]
            queryset = queryset.filter(status__in=statuses)

        payment_status = request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(order_number__icontains=search.strip())

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = OrderListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = OrderService.create_order_from_cart(
                user=request.user,
                shipping_address_data=serializer.validated_data['shipping_address'],
                shipping_method=serializer.validated_data.get('shipping_method', Order.ShippingMethod.STANDARD),
                payment_method=serializer.validated_data.get('payment_method', Order.PaymentMethod.CASH_ON_DELIVERY),
                coupon_code=serializer.validated_data.get('coupon_code'),
                customer_notes=serializer.validated_data.get('customer_notes'),
            )
            return Response(
                OrderDetailSerializer(order, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response({'detail': detail[0] if len(detail) == 1 else detail}, status=status.HTTP_400_BAD_REQUEST)


class OrderDetailView(APIView):
    """
    GET /api/v1/orders/<order_number>/
    Retrieves full details of an order. Customers access only their own orders; staff can access any.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_number):
        prefetch_qs = Order.objects.select_related('shipping_address').prefetch_related(
            'items__variant__product__media',
            'items__variant__media',
            'status_history',
        )

        if request.user.is_staff:
            order = get_object_or_404(prefetch_qs, order_number=order_number)
        else:
            order = get_object_or_404(prefetch_qs, order_number=order_number, user=request.user)

        serializer = OrderDetailSerializer(order, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderCancelView(APIView):
    """
    POST /api/v1/orders/<order_number>/cancel/
    Cancels an order, releases reserved stock back to available inventory, and updates timeline.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_number):
        if request.user.is_staff:
            order = get_object_or_404(Order, order_number=order_number)
        else:
            order = get_object_or_404(Order, order_number=order_number, user=request.user)

        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cancelled_order = OrderService.cancel_order(
                order=order,
                user=request.user,
                reason=serializer.validated_data.get('reason', ''),
            )
            return Response(
                {
                    'detail': f"Order {order.order_number} has been cancelled successfully.",
                    'order': OrderDetailSerializer(cancelled_order, context={'request': request}).data,
                },
                status=status.HTTP_200_OK,
            )
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response({'detail': detail[0] if len(detail) == 1 else detail}, status=status.HTTP_400_BAD_REQUEST)


class OrderTrackingView(APIView):
    """
    GET /api/v1/orders/<order_number>/tracking/
    Customer tracking timeline showing chronological status milestones and courier details.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_number):
        prefetch_qs = Order.objects.prefetch_related('status_history__created_by')

        if request.user.is_staff:
            order = get_object_or_404(prefetch_qs, order_number=order_number)
            history = order.status_history.all()
        else:
            order = get_object_or_404(prefetch_qs, order_number=order_number, user=request.user)
            history = order.status_history.filter(is_customer_visible=True)

        return Response(
            {
                'order_number': order.order_number,
                'status': order.status,
                'payment_status': order.payment_status,
                'shipping_method': order.shipping_method,
                'tracking_number': order.tracking_number,
                'created_at': order.created_at,
                'paid_at': order.paid_at,
                'delivered_at': order.delivered_at,
                'timeline': OrderStatusHistorySerializer(history, many=True, context={'request': request}).data,
            },
            status=status.HTTP_200_OK,
        )


class OrderInvoiceView(APIView):
    """
    GET /api/v1/orders/<order_number>/invoice/
    Formatted receipt and invoice summary for billing and printing.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_number):
        prefetch_qs = Order.objects.select_related('shipping_address', 'user').prefetch_related(
            'items__variant__product__media',
            'items__variant__media',
        )

        if request.user.is_staff:
            order = get_object_or_404(prefetch_qs, order_number=order_number)
        else:
            order = get_object_or_404(prefetch_qs, order_number=order_number, user=request.user)

        serializer = OrderInvoiceSerializer(order, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminOrderListView(generics.ListAPIView):
    """
    GET /api/v1/orders/admin/
    Staff administrator view for inspecting, searching, and filtering all platform orders.
    """

    permission_classes = [permissions.IsAdminUser]
    serializer_class = OrderListSerializer
    pagination_class = OrderPagination

    def get_queryset(self):
        queryset = (
            Order.objects.all()
            .select_related('shipping_address', 'user')
            .prefetch_related('items')
            .order_by('-created_at')
        )

        status_param = self.request.query_params.get('status')
        if status_param:
            statuses = [s.strip() for s in status_param.split(',') if s.strip()]
            queryset = queryset.filter(status__in=statuses)

        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        payment_method = self.request.query_params.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        shipping_method = self.request.query_params.get('shipping_method')
        if shipping_method:
            queryset = queryset.filter(shipping_method=shipping_method)

        search = self.request.query_params.get('search')
        if search:
            query = search.strip()
            queryset = queryset.filter(
                Q(order_number__icontains=query)
                | Q(user__email__icontains=query)
                | Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(shipping_address__recipient_name__icontains=query)
                | Q(shipping_address__phone_number__icontains=query)
            )

        return queryset


class AdminOrderStatusUpdateView(APIView):
    """
    PATCH /api/v1/orders/admin/<order_number>/status/
    Staff administrator endpoint to advance order lifecycle state, assign tracking number,
    and log official transition notes.
    """

    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number)
        serializer = AdminStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated_order = OrderService.admin_transition_status(
                order=order,
                new_status=serializer.validated_data['new_status'],
                comment=serializer.validated_data.get('comment', ''),
                user=request.user,
                tracking_number=serializer.validated_data.get('tracking_number'),
                is_customer_visible=serializer.validated_data.get('is_customer_visible', True),
            )
            return Response(
                OrderDetailSerializer(updated_order, context={'request': request}).data,
                status=status.HTTP_200_OK,
            )
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response({'detail': detail[0] if len(detail) == 1 else detail}, status=status.HTTP_400_BAD_REQUEST)


class AdminOrderNotesView(APIView):
    """
    POST /api/v1/orders/admin/<order_number>/notes/
    Staff administrator endpoint to record internal order operational notes.
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number)
        serializer = AdminNotesUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order.admin_notes = serializer.validated_data['admin_notes'].strip()
        order.save(update_fields=['admin_notes', 'updated_at'])

        return Response(
            {
                'detail': "Order admin notes updated successfully.",
                'order_number': order.order_number,
                'admin_notes': order.admin_notes,
            },
            status=status.HTTP_200_OK,
        )
