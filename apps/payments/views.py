from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.payments.models import Payment, PaymentTransaction, Refund, SavedCard
from apps.payments.pagination import (
    PaymentPagination,
    RefundPagination,
    TransactionPagination,
)
from apps.payments.permissions import IsOwnerOrStaff, IsStaffUser
from apps.payments.serializers import (
    ClickWebhookSerializer,
    PaymeRpcSerializer,
    PayWithSavedCardInputSerializer,
    PaymentCancelSerializer,
    PaymentDetailSerializer,
    PaymentInitializeInputSerializer,
    PaymentListSerializer,
    PaymentTransactionSerializer,
    RefundCreateInputSerializer,
    RefundDetailSerializer,
    RefundListSerializer,
    SavedCardCreateInputSerializer,
    SavedCardSerializer,
    SavedCardVerifyInputSerializer,
    UzumWebhookSerializer,
)
from apps.payments.services import (
    ClickGateway,
    PaymeError,
    PaymeGateway,
    PaymentService,
    RefundService,
    SavedCardService,
    UzumGateway,
)


def get_client_ip(request):
    """Utility to extract remote IP address from HTTP request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ============================================================================
# 1. CUSTOMER PAYMENT & SAVED CARDS VIEWS
# ============================================================================

class PaymentInitializeView(APIView):
    """
    POST /api/v1/payments/initialize/
    Initiates payment for an order. Generates gateway checkout redirect link or initiates transaction.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PaymentInitializeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_number = serializer.validated_data['order_number']
        provider = serializer.validated_data['provider']
        return_url = serializer.validated_data.get('return_url')

        order_qs = Order.objects.filter(order_number=order_number)
        if not request.user.is_staff:
            order_qs = order_qs.filter(user=request.user)

        order = order_qs.first()
        if not order:
            return Response(
                {'detail': f"Order '{order_number}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment = PaymentService.initialize_payment(
                order=order,
                provider=provider,
                user=request.user,
                return_url=return_url,
                ip_address=get_client_ip(request),
            )
            return Response(
                PaymentDetailSerializer(payment, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response(
                {'detail': detail[0] if len(detail) == 1 else detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PaymentListView(APIView):
    """
    GET /api/v1/payments/
    Lists payments belonging to the authenticated customer with filters & pagination.
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PaymentPagination

    def get(self, request):
        queryset = (
            Payment.objects.filter(user=request.user)
            .select_related('order')
            .order_by('-created_at')
        )

        status_param = request.query_params.get('status')
        if status_param:
            statuses = [s.strip() for s in status_param.split(',') if s.strip()]
            queryset = queryset.filter(status__in=statuses)

        provider_param = request.query_params.get('provider')
        if provider_param:
            queryset = queryset.filter(provider=provider_param)

        search = request.query_params.get('search')
        if search:
            clean_search = search.strip()
            queryset = queryset.filter(
                Q(payment_number__icontains=clean_search)
                | Q(order__order_number__icontains=clean_search)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = PaymentListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class PaymentDetailView(APIView):
    """
    GET /api/v1/payments/<payment_number>/
    Retrieves detailed info for a single payment. Customer can only access their own.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payment_number):
        queryset = Payment.objects.select_related('order')
        if request.user.is_staff:
            payment = get_object_or_404(queryset, payment_number=payment_number)
        else:
            payment = get_object_or_404(queryset, payment_number=payment_number, user=request.user)

        serializer = PaymentDetailSerializer(payment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class PaymentCancelView(APIView):
    """
    POST /api/v1/payments/<payment_number>/cancel/
    Allows customer to cancel a pending payment attempt.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, payment_number):
        queryset = Payment.objects.select_related('order')
        if request.user.is_staff:
            payment = get_object_or_404(queryset, payment_number=payment_number)
        else:
            payment = get_object_or_404(queryset, payment_number=payment_number, user=request.user)

        if payment.status != Payment.PaymentStatus.PENDING:
            return Response(
                {'detail': f"Cannot cancel payment with status '{payment.get_status_display()}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaymentCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason', 'Cancelled by customer')

        PaymentService.process_cancellation(
            payment=payment,
            reason=reason,
            ip_address=get_client_ip(request),
        )

        return Response(
            {
                'detail': f"Payment {payment.payment_number} cancelled successfully.",
                'payment': PaymentDetailSerializer(payment, context={'request': request}).data,
            },
            status=status.HTTP_200_OK,
        )


class SavedCardListCreateView(APIView):
    """
    GET  /api/v1/payments/cards/ - List user's verified and pending saved cards.
    POST /api/v1/payments/cards/ - Register new card and send SMS OTP for verification.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cards = SavedCard.objects.filter(user=request.user).order_by('-is_default', '-created_at')
        serializer = SavedCardSerializer(cards, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = SavedCardCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            card, otp_code = SavedCardService.add_card(
                user=request.user,
                card_number=serializer.validated_data['card_number'],
                expire_month=serializer.validated_data['expire_month'],
                expire_year=serializer.validated_data['expire_year'],
                card_holder=serializer.validated_data.get('card_holder'),
                provider=serializer.validated_data.get('provider', Payment.PaymentProvider.PAYME),
            )
            return Response(
                {
                    'detail': "Card registered. Please enter the OTP code sent via SMS to verify.",
                    'card': SavedCardSerializer(card, context={'request': request}).data,
                    'otp_code': otp_code,
                },
                status=status.HTTP_201_CREATED,
            )
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response(
                {'detail': detail[0] if len(detail) == 1 else detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


class SavedCardVerifyView(APIView):
    """
    POST /api/v1/payments/cards/<int:pk>/verify/
    Verifies SMS OTP code and activates saved card token for 1-click checkout.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        serializer = SavedCardVerifyInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            card = SavedCardService.verify_card(
                user=request.user,
                card_id=pk,
                otp_code=serializer.validated_data['otp_code'],
            )
            return Response(
                {
                    'detail': "Card verified successfully and activated for 1-click checkout.",
                    'card': SavedCardSerializer(card, context={'request': request}).data,
                },
                status=status.HTTP_200_OK,
            )
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response(
                {'detail': detail[0] if len(detail) == 1 else detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


class SavedCardDeleteView(APIView):
    """
    DELETE /api/v1/payments/cards/<int:pk>/
    Deletes customer saved card.
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        try:
            SavedCardService.delete_card(user=request.user, card_id=pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response(
                {'detail': detail[0] if len(detail) == 1 else detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


class SavedCardDefaultView(APIView):
    """
    POST /api/v1/payments/cards/<int:pk>/default/
    Sets a verified card as primary/default payment method.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            card = SavedCardService.set_default_card(user=request.user, card_id=pk)
            return Response(
                {
                    'detail': f"Card {card.card_mask} is now your default payment method.",
                    'card': SavedCardSerializer(card, context={'request': request}).data,
                },
                status=status.HTTP_200_OK,
            )
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response(
                {'detail': detail[0] if len(detail) == 1 else detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PayWithSavedCardView(APIView):
    """
    POST /api/v1/payments/pay-with-card/
    Executes instant 1-click payment for an order using a verified saved card.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PayWithSavedCardInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_number = serializer.validated_data['order_number']
        card_id = serializer.validated_data['card_id']

        order_qs = Order.objects.filter(order_number=order_number)
        if not request.user.is_staff:
            order_qs = order_qs.filter(user=request.user)

        order = order_qs.first()
        if not order:
            return Response(
                {'detail': f"Order '{order_number}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment = SavedCardService.charge_saved_card(
                user=request.user,
                card_id=card_id,
                order=order,
                ip_address=get_client_ip(request),
            )
            return Response(
                {
                    'detail': f"Order {order.order_number} paid successfully.",
                    'payment': PaymentDetailSerializer(payment, context={'request': request}).data,
                },
                status=status.HTTP_200_OK,
            )
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response(
                {'detail': detail[0] if len(detail) == 1 else detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ============================================================================
# 2. PAYMENT GATEWAY WEBHOOKS (SERVER-TO-SERVER)
# ============================================================================

class PaymeWebhookView(APIView):
    """
    POST /api/v1/payments/webhooks/payme/
    Payme JSON-RPC 2.0 Merchant API protocol endpoint.
    Handles CheckPerformTransaction, CreateTransaction, PerformTransaction, CancelTransaction, CheckTransaction.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not PaymeGateway.validate_auth(auth_header):
            return Response(
                {
                    'id': request.data.get('id'),
                    'error': {
                        'code': PaymeError.AUTH_ERROR,
                        'message': {'ru': 'Authorization failed', 'uz': 'Avtorizatsiyadan o\'tmadi', 'en': 'Auth error'},
                    },
                },
                status=status.HTTP_200_OK,
            )

        serializer = PaymeRpcSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'id': request.data.get('id'),
                    'error': {
                        'code': PaymeError.METHOD_NOT_FOUND,
                        'message': {'ru': 'Invalid RPC payload', 'uz': 'Noto\'g\'ri so\'rov formati', 'en': 'Invalid RPC payload'},
                    },
                },
                status=status.HTTP_200_OK,
            )

        response_data = PaymeGateway.process_rpc(
            data=serializer.validated_data,
            ip_address=get_client_ip(request),
        )
        return Response(response_data, status=status.HTTP_200_OK)


class ClickWebhookView(APIView):
    """
    POST /api/v1/payments/webhooks/click/
    Click Shop API endpoint (Prepare and Complete actions).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ClickWebhookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': -8,
                    'error_note': 'Error in request from click',
                },
                status=status.HTTP_200_OK,
            )

        response_data = ClickGateway.process_request(
            data=request.data,
            ip_address=get_client_ip(request),
        )
        return Response(response_data, status=status.HTTP_200_OK)


class UzumWebhookView(APIView):
    """
    POST /api/v1/payments/webhooks/uzum/
    Uzum Bank / Uzum Pay callback notification endpoint.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UzumWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        signature_header = request.META.get('HTTP_X_UZUM_SIGNATURE')
        if signature_header:
            if not UzumGateway.validate_signature(request.body, signature_header):
                return Response({'error': 'Invalid signature'}, status=status.HTTP_403_FORBIDDEN)

        response_data = UzumGateway.process_webhook(
            data=serializer.validated_data,
            ip_address=get_client_ip(request),
        )
        return Response(response_data, status=status.HTTP_200_OK)


# ============================================================================
# 3. ADMIN & STAFF CONTROLS (PAYMENTS, REFUNDS, TRANSACTIONS)
# ============================================================================

class AdminPaymentListView(APIView):
    """
    GET /api/v1/payments/admin/
    Comprehensive payment transactions monitoring for staff administrators.
    """

    permission_classes = [IsStaffUser]
    pagination_class = PaymentPagination

    def get(self, request):
        queryset = Payment.objects.select_related('order', 'user').order_by('-created_at')

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        provider_param = request.query_params.get('provider')
        if provider_param:
            queryset = queryset.filter(provider=provider_param)

        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        search = request.query_params.get('search')
        if search:
            clean = search.strip()
            queryset = queryset.filter(
                Q(payment_number__icontains=clean)
                | Q(order__order_number__icontains=clean)
                | Q(provider_transaction_id__icontains=clean)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = PaymentListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AdminPaymentDetailView(APIView):
    """
    GET /api/v1/payments/admin/<payment_number>/
    Detailed payment view including nested gateway audit transaction logs.
    """

    permission_classes = [IsStaffUser]

    def get(self, request, payment_number):
        payment = get_object_or_404(
            Payment.objects.select_related('order', 'user').prefetch_related('transactions', 'refunds'),
            payment_number=payment_number,
        )

        data = PaymentDetailSerializer(payment, context={'request': request}).data
        data['transactions'] = PaymentTransactionSerializer(
            payment.transactions.all(), many=True, context={'request': request}
        ).data
        data['refunds'] = RefundListSerializer(
            payment.refunds.all(), many=True, context={'request': request}
        ).data

        return Response(data, status=status.HTTP_200_OK)


class AdminRefundCreateView(APIView):
    """
    POST /api/v1/payments/admin/<payment_number>/refund/
    Processes full or partial refund for a successful payment.
    """

    permission_classes = [IsStaffUser]

    def post(self, request, payment_number):
        payment = get_object_or_404(
            Payment.objects.select_related('order'),
            payment_number=payment_number,
        )

        serializer = RefundCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        reason = serializer.validated_data.get('reason', '')
        provider_refund_id = serializer.validated_data.get('provider_refund_id', '')

        try:
            refund = RefundService.process_refund(
                payment=payment,
                amount=amount,
                reason=reason,
                admin_user=request.user,
                provider_refund_id=provider_refund_id,
                ip_address=get_client_ip(request),
            )
            return Response(
                RefundDetailSerializer(refund, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        except DjangoValidationError as exc:
            detail = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return Response(
                {'detail': detail[0] if len(detail) == 1 else detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


class AdminRefundListView(APIView):
    """
    GET /api/v1/payments/admin/refunds/
    Lists processed monetary refunds with filters and pagination.
    """

    permission_classes = [IsStaffUser]
    pagination_class = RefundPagination

    def get(self, request):
        queryset = Refund.objects.select_related('payment', 'order', 'created_by').order_by('-created_at')

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        search = request.query_params.get('search')
        if search:
            clean = search.strip()
            queryset = queryset.filter(
                Q(refund_number__icontains=clean)
                | Q(payment__payment_number__icontains=clean)
                | Q(order__order_number__icontains=clean)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = RefundListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AdminRefundDetailView(APIView):
    """
    GET /api/v1/payments/admin/refunds/<refund_number>/
    Detailed view of a single refund operation.
    """

    permission_classes = [IsStaffUser]

    def get(self, request, refund_number):
        refund = get_object_or_404(
            Refund.objects.select_related('payment', 'order', 'created_by'),
            refund_number=refund_number,
        )
        serializer = RefundDetailSerializer(refund, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminTransactionListView(APIView):
    """
    GET /api/v1/payments/admin/transactions/
    Gateway audit logs inspection for financial reconciliation and troubleshooting.
    """

    permission_classes = [IsStaffUser]
    pagination_class = TransactionPagination

    def get(self, request):
        queryset = PaymentTransaction.objects.select_related('payment').order_by('-created_at')

        tx_type = request.query_params.get('transaction_type')
        if tx_type:
            queryset = queryset.filter(transaction_type=tx_type)

        tx_status = request.query_params.get('status')
        if tx_status:
            queryset = queryset.filter(status=tx_status)

        payment_number = request.query_params.get('payment_number')
        if payment_number:
            queryset = queryset.filter(payment__payment_number=payment_number.strip())

        search = request.query_params.get('search')
        if search:
            clean = search.strip()
            queryset = queryset.filter(
                Q(idempotency_key__icontains=clean)
                | Q(provider_transaction_id__icontains=clean)
                | Q(payment__payment_number__icontains=clean)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = PaymentTransactionSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)
