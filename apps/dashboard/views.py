from datetime import datetime
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.models import (
    DailyMetricSnapshot,
    OrderInternalNote,
    StaffActivityLog,
    StockMovementLog,
    SystemAlert,
)
from apps.dashboard.pagination import DashboardPagination
from apps.dashboard.permissions import IsAdminOnly, IsStaffOrAdminUser
from apps.dashboard.serializers import (
    CustomerStatusToggleSerializer,
    DashboardCustomerDetailSerializer,
    DashboardCustomerListSerializer,
    DashboardInventoryListSerializer,
    DashboardOrderDetailSerializer,
    DashboardOrderListSerializer,
    InventoryStatisticsSerializer,
    KPIDashboardSerializer,
    OrderInternalNoteSerializer,
    OrderStatusUpdateSerializer,
    SalesChartPointSerializer,
    StaffActivityLogSerializer,
    StockAdjustmentSerializer,
    StockMovementLogSerializer,
    SystemAlertSerializer,
    TopCustomerSerializer,
    TopProductSerializer,
)
from apps.dashboard.services import (
    adjust_variant_stock,
    get_dashboard_kpis,
    get_inventory_statistics,
    get_sales_chart_series,
    get_top_customers_report,
    get_top_products_report,
    log_staff_activity,
)
from apps.orders.models import Order, OrderStatusHistory
from apps.products.models import Inventory, ProductVariant

User = get_user_model()


# ==============================================================================
# 1. ANALYTICS & METRICS VIEWS
# ==============================================================================

class DashboardOverviewAPIView(APIView):
    """
    GET /api/v1/dashboard/analytics/overview/
    Returns core executive business KPIs and growth rates.
    Optional query params: ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    """
    permission_classes = [IsStaffOrAdminUser]

    def get(self, request):
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')

        date_from = None
        date_to = None

        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': "Noto'g'ri sana formati (date_from: YYYY-MM-DD bo'lishi kerak)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': "Noto'g'ri sana formati (date_to: YYYY-MM-DD bo'lishi kerak)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        data = get_dashboard_kpis(date_from=date_from, date_to=date_to)
        serializer = KPIDashboardSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DashboardSalesChartAPIView(APIView):
    """
    GET /api/v1/dashboard/analytics/sales-chart/
    Returns timeseries daily points for revenue and orders.
    Optional query param: ?days=30
    """
    permission_classes = [IsStaffOrAdminUser]

    def get(self, request):
        try:
            days = int(request.query_params.get('days', 30))
            days = min(max(days, 1), 365)
        except ValueError:
            days = 30

        data = get_sales_chart_series(days=days)
        serializer = SalesChartPointSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DashboardTopProductsAPIView(APIView):
    """
    GET /api/v1/dashboard/analytics/top-products/
    Returns top selling products ranked by quantity sold and revenue.
    Optional query param: ?limit=10
    """
    permission_classes = [IsStaffOrAdminUser]

    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 10))
            limit = min(max(limit, 1), 50)
        except ValueError:
            limit = 10

        data = get_top_products_report(limit=limit)
        serializer = TopProductSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DashboardTopCustomersAPIView(APIView):
    """
    GET /api/v1/dashboard/analytics/top-customers/
    Returns customer accounts with highest lifetime purchase values.
    Optional query param: ?limit=10
    """
    permission_classes = [IsStaffOrAdminUser]

    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 10))
            limit = min(max(limit, 1), 50)
        except ValueError:
            limit = 10

        data = get_top_customers_report(limit=limit)
        serializer = TopCustomerSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==============================================================================
# 2. INVENTORY & STOCK MANAGEMENT VIEWS
# ==============================================================================

class DashboardInventoryListAPIView(generics.ListAPIView):
    """
    GET /api/v1/dashboard/inventory/
    List inventory stocks across all product variants with filtering and search.
    """
    permission_classes = [IsStaffOrAdminUser]
    serializer_class = DashboardInventoryListSerializer
    pagination_class = DashboardPagination

    def get_queryset(self):
        qs = Inventory.objects.select_related('variant', 'variant__product').all()

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(variant__sku__icontains=search)
                | Q(variant__product__name__icontains=search)
            )

        low_stock = self.request.query_params.get('low_stock')
        if low_stock and low_stock.lower() in ['true', '1']:
            qs = qs.filter(quantity__gt=0, quantity__lte=F('low_stock_threshold'))

        out_of_stock = self.request.query_params.get('out_of_stock')
        if out_of_stock and out_of_stock.lower() in ['true', '1']:
            qs = qs.filter(quantity=0)

        return qs.order_by('quantity')


class DashboardLowStockAPIView(generics.ListAPIView):
    """
    GET /api/v1/dashboard/inventory/low-stock/
    Fast endpoint dedicated to products whose inventory is at or below threshold.
    """
    permission_classes = [IsStaffOrAdminUser]
    serializer_class = DashboardInventoryListSerializer
    pagination_class = DashboardPagination

    def get_queryset(self):
        return (
            Inventory.objects.select_related('variant', 'variant__product')
            .filter(quantity__lte=F('low_stock_threshold'))
            .order_by('quantity')
        )


class DashboardStockAdjustmentAPIView(APIView):
    """
    PATCH /api/v1/dashboard/inventory/<int:variant_id>/adjust/
    Safely adjusts variant inventory quantity with audit and movement logs.
    """
    permission_classes = [IsStaffOrAdminUser]

    def patch(self, request, variant_id):
        variant = get_object_or_404(ProductVariant, pk=variant_id)
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quantity_delta = serializer.validated_data['quantity_delta']
        reason = serializer.validated_data['reason']
        movement_type = serializer.validated_data.get(
            'movement_type',
            StockMovementLog.StockMovementType.ADJUSTMENT,
        )

        try:
            inventory, movement_log = adjust_variant_stock(
                variant=variant,
                quantity_delta=quantity_delta,
                reason=reason,
                actor=request.user,
                movement_type=movement_type,
                request=request,
            )
        except DjangoValidationError as exc:
            return Response({'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'detail': "Zaxira muvaffaqiyatli to'g'rilandi.",
                'variant_id': variant.id,
                'sku': variant.sku,
                'previous_quantity': movement_log.previous_quantity,
                'new_quantity': movement_log.new_quantity,
                'quantity_delta': movement_log.quantity_delta,
                'movement_log_id': movement_log.id,
            },
            status=status.HTTP_200_OK,
        )


class DashboardStockMovementLogsAPIView(generics.ListAPIView):
    """
    GET /api/v1/dashboard/inventory/logs/
    Audit list of all inventory movements.
    """
    permission_classes = [IsStaffOrAdminUser]
    serializer_class = StockMovementLogSerializer
    pagination_class = DashboardPagination

    def get_queryset(self):
        qs = StockMovementLog.objects.select_related('variant', 'variant__product', 'actor', 'reference_order').all()

        variant_id = self.request.query_params.get('variant_id')
        if variant_id:
            qs = qs.filter(variant_id=variant_id)

        movement_type = self.request.query_params.get('movement_type')
        if movement_type:
            qs = qs.filter(movement_type=movement_type)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(variant__sku__icontains=search)
                | Q(variant__product__name__icontains=search)
                | Q(reason__icontains=search)
            )

        return qs.order_by('-created_at')


class DashboardInventoryStatsAPIView(APIView):
    """
    GET /api/v1/dashboard/inventory/stats/
    Returns high-level inventory distribution metrics.
    """
    permission_classes = [IsStaffOrAdminUser]

    def get(self, request):
        stats = get_inventory_statistics()
        serializer = InventoryStatisticsSerializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==============================================================================
# 3. ORDER MANAGEMENT & INTERNAL NOTES VIEWS
# ==============================================================================

class DashboardOrderListAPIView(generics.ListAPIView):
    """
    GET /api/v1/dashboard/orders/
    Full administrative order list with search, status filtering, and date range.
    """
    permission_classes = [IsStaffOrAdminUser]
    serializer_class = DashboardOrderListSerializer
    pagination_class = DashboardPagination

    def get_queryset(self):
        qs = Order.objects.select_related('user').prefetch_related('items', 'internal_notes').all()

        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            qs = qs.filter(payment_status=payment_status)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(order_number__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__phone_number__icontains=search)
            )

        date_from = self.request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        return qs.order_by('-created_at')


class DashboardOrderDetailAPIView(generics.RetrieveAPIView):
    """
    GET /api/v1/dashboard/orders/<str:order_number>/
    Detailed single order backoffice view.
    """
    permission_classes = [IsStaffOrAdminUser]
    serializer_class = DashboardOrderDetailSerializer
    lookup_field = 'order_number'
    queryset = Order.objects.select_related('user', 'shipping_address').prefetch_related('items', 'internal_notes')


class DashboardOrderStatusUpdateAPIView(APIView):
    """
    PATCH /api/v1/dashboard/orders/<str:order_number>/status/
    Updates order lifecycle status and tracking number with audit history.
    """
    permission_classes = [IsStaffOrAdminUser]

    def patch(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number)
        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        admin_notes = serializer.validated_data.get('admin_notes', '')
        tracking_number = serializer.validated_data.get('tracking_number')

        old_status = order.status
        now = timezone.now()

        order.status = new_status
        if admin_notes:
            order.admin_notes = admin_notes
        if tracking_number is not None:
            order.tracking_number = tracking_number

        if new_status == Order.OrderStatus.DELIVERED and not order.delivered_at:
            order.delivered_at = now
        elif new_status == Order.OrderStatus.CANCELLED and not order.cancelled_at:
            order.cancelled_at = now

        order.save()

        # Record OrderStatusHistory
        OrderStatusHistory.objects.create(
            order=order,
            old_status=old_status,
            new_status=new_status,
            comment=admin_notes or f"Status changed from {old_status} to {new_status} via Dashboard",
            created_by=request.user,
            is_customer_visible=False,
        )

        # Audit staff activity
        log_staff_activity(
            actor=request.user,
            action=StaffActivityLog.ActivityAction.STATUS_CHANGE,
            module=StaffActivityLog.ActivityModule.ORDERS,
            description=f"Buyurtma #{order.order_number} holati '{old_status}' dan '{new_status}' ga o'zgartirildi.",
            target=order,
            changes={'status': {'old': old_status, 'new': new_status}},
            request=request,
        )

        return Response(
            {
                'detail': "Buyurtma statusi muvaffaqiyatli yangilandi.",
                'order_number': order.order_number,
                'old_status': old_status,
                'new_status': new_status,
            },
            status=status.HTTP_200_OK,
        )


class DashboardOrderNotesListCreateAPIView(APIView):
    """
    GET, POST /api/v1/dashboard/orders/<str:order_number>/notes/
    Read and create internal operator notes on orders.
    """
    permission_classes = [IsStaffOrAdminUser]

    def get(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number)
        notes = order.internal_notes.select_related('author').order_by('-is_pinned', '-created_at')
        serializer = OrderInternalNoteSerializer(notes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number)
        note_text = request.data.get('note', '').strip()
        is_pinned = bool(request.data.get('is_pinned', False))

        if not note_text:
            return Response({'error': "Izoh matni bo'sh bo'lishi mumkin emas."}, status=status.HTTP_400_BAD_REQUEST)

        note_obj = OrderInternalNote.objects.create(
            order=order,
            author=request.user,
            note=note_text,
            is_pinned=is_pinned,
        )

        log_staff_activity(
            actor=request.user,
            action=StaffActivityLog.ActivityAction.CREATE,
            module=StaffActivityLog.ActivityModule.ORDERS,
            description=f"Buyurtma #{order.order_number} ga ichki izoh qo'shildi.",
            target=note_obj,
            request=request,
        )

        serializer = OrderInternalNoteSerializer(note_obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ==============================================================================
# 4. CUSTOMER MANAGEMENT (CRM) VIEWS
# ==============================================================================

class DashboardCustomerListAPIView(generics.ListAPIView):
    """
    GET /api/v1/dashboard/customers/
    Customer registry with lifetime purchasing aggregates and filters.
    """
    permission_classes = [IsStaffOrAdminUser]
    serializer_class = DashboardCustomerListSerializer
    pagination_class = DashboardPagination

    def get_queryset(self):
        qs = User.objects.filter(role='customer').prefetch_related('orders').order_by('-created_at')

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            if is_active.lower() in ['true', '1']:
                qs = qs.filter(is_active=True)
            elif is_active.lower() in ['false', '0']:
                qs = qs.filter(is_active=False)

        return qs


class DashboardCustomerDetailAPIView(generics.RetrieveAPIView):
    """
    GET /api/v1/dashboard/customers/<int:pk>/
    Full customer CRM dossier with order history.
    """
    permission_classes = [IsStaffOrAdminUser]
    serializer_class = DashboardCustomerDetailSerializer
    queryset = User.objects.prefetch_related('orders').all()


class DashboardCustomerToggleStatusAPIView(APIView):
    """
    PATCH /api/v1/dashboard/customers/<int:pk>/toggle-status/
    Activate or deactivate customer account (Admin only).
    """
    permission_classes = [IsAdminOnly]

    def patch(self, request, pk):
        customer = get_object_or_404(User, pk=pk)
        serializer = CustomerStatusToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['is_active']
        reason = serializer.validated_data.get('reason', '')
        old_status = customer.is_active

        customer.is_active = new_status
        customer.save(update_fields=['is_active'])

        action_word = "faollashtirildi" if new_status else "bloklandi"
        log_staff_activity(
            actor=request.user,
            action=StaffActivityLog.ActivityAction.UPDATE,
            module=StaffActivityLog.ActivityModule.USERS,
            description=f"Mijoz ({customer.email}) hisobi {action_word}. Sabab: {reason or 'Ko\'rsatilmadi'}",
            target=customer,
            changes={'is_active': {'old': old_status, 'new': new_status}},
            request=request,
        )

        return Response(
            {
                'detail': f"Mijoz hisobi muvaffaqiyatli {action_word}.",
                'customer_id': customer.id,
                'email': customer.email,
                'is_active': customer.is_active,
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 5. AUDIT TRAIL & SYSTEM ALERTS VIEWS
# ==============================================================================

class DashboardAuditLogsAPIView(generics.ListAPIView):
    """
    GET /api/v1/dashboard/audit-logs/
    Complete immutable audit trail of backoffice activities (Admin only).
    """
    permission_classes = [IsAdminOnly]
    serializer_class = StaffActivityLogSerializer
    pagination_class = DashboardPagination

    def get_queryset(self):
        qs = StaffActivityLog.objects.select_related('actor').all()

        action = self.request.query_params.get('action')
        if action:
            qs = qs.filter(action=action)

        module = self.request.query_params.get('module')
        if module:
            qs = qs.filter(module=module)

        actor_id = self.request.query_params.get('actor_id')
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(description__icontains=search)
                | Q(target_repr__icontains=search)
                | Q(ip_address__icontains=search)
            )

        return qs.order_by('-created_at')


class DashboardSystemAlertsListAPIView(generics.ListAPIView):
    """
    GET /api/v1/dashboard/alerts/
    System operational alerts and warnings.
    """
    permission_classes = [IsStaffOrAdminUser]
    serializer_class = SystemAlertSerializer
    pagination_class = DashboardPagination

    def get_queryset(self):
        qs = SystemAlert.objects.select_related('resolved_by').all()

        is_resolved = self.request.query_params.get('is_resolved')
        if is_resolved is not None:
            if is_resolved.lower() in ['true', '1']:
                qs = qs.filter(is_resolved=True)
            elif is_resolved.lower() in ['false', '0']:
                qs = qs.filter(is_resolved=False)

        severity = self.request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity)

        alert_type = self.request.query_params.get('alert_type')
        if alert_type:
            qs = qs.filter(alert_type=alert_type)

        return qs.order_by('is_resolved', '-created_at')


class DashboardSystemAlertResolveAPIView(APIView):
    """
    PATCH /api/v1/dashboard/alerts/<int:pk>/resolve/
    Marks a system alert as resolved by the requesting staff member.
    """
    permission_classes = [IsStaffOrAdminUser]

    def patch(self, request, pk):
        alert = get_object_or_404(SystemAlert, pk=pk)
        if alert.is_resolved:
            return Response(
                {'detail': "Ushbu ogohlantirish avvalroq bartaraf etilgan."},
                status=status.HTTP_200_OK,
            )

        alert.resolve(request.user)

        log_staff_activity(
            actor=request.user,
            action=StaffActivityLog.ActivityAction.UPDATE,
            module=StaffActivityLog.ActivityModule.SETTINGS,
            description=f"Tizim ogohlantirishi (#{alert.id} - {alert.title}) bartaraf etildi deb belgilandi.",
            target=alert,
            request=request,
        )

        serializer = SystemAlertSerializer(alert)
        return Response(
            {
                'detail': "Ogohlantirish muvaffaqiyatli bartaraf etildi.",
                'alert': serializer.data,
            },
            status=status.HTTP_200_OK,
        )
