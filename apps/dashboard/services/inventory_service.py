from typing import Any, Dict, Optional, Tuple
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum

from apps.products.models import Inventory, ProductVariant
from apps.dashboard.models import StaffActivityLog, StockMovementLog, SystemAlert
from apps.dashboard.services.audit_service import log_staff_activity


def adjust_variant_stock(
    variant: ProductVariant,
    quantity_delta: int,
    reason: str,
    actor: Any = None,
    movement_type: str = StockMovementLog.StockMovementType.ADJUSTMENT,
    reference_order: Any = None,
    request: Any = None,
) -> Tuple[Inventory, StockMovementLog]:
    """
    Safely adjusts the stock of a product variant within an atomic transaction.
    Records a StockMovementLog, an immutable StaffActivityLog, and raises
    a SystemAlert if stock drops below the low_stock_threshold.
    """
    if quantity_delta == 0:
        raise ValidationError("Miqdor o'zgarishi (quantity_delta) 0 dan farqli bo'lishi shart.")

    with transaction.atomic():
        inventory, _ = Inventory.objects.select_for_update().get_or_create(
            variant=variant,
            defaults={'quantity': 0, 'reserved_quantity': 0, 'low_stock_threshold': 5},
        )

        previous_quantity = inventory.quantity
        new_quantity = previous_quantity + quantity_delta

        if new_quantity < 0:
            raise ValidationError(
                f"Omborda yetarli qoldiq mavjud emas! Joriy qoldiq: {previous_quantity}, talab qilingan o'zgarish: {quantity_delta}"
            )

        inventory.quantity = new_quantity
        inventory.save(update_fields=['quantity', 'updated_at'])

        # Record movement log
        movement_log = StockMovementLog.objects.create(
            variant=variant,
            actor=actor,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            previous_quantity=previous_quantity,
            new_quantity=new_quantity,
            reference_order=reference_order,
            reason=reason or "Qo'lda kiritilgan tuzatish",
        )

        # Audit staff activity
        log_staff_activity(
            actor=actor,
            action=StaffActivityLog.ActivityAction.STOCK_ADJUSTMENT,
            module=StaffActivityLog.ActivityModule.INVENTORY,
            description=f"Variant {variant.sku} ombor qoldig'i {quantity_delta:+d} ga o'zgartirildi ({previous_quantity} -> {new_quantity}). Sabab: {reason}",
            target=variant,
            changes={
                'quantity': {'old': previous_quantity, 'new': new_quantity},
                'delta': quantity_delta,
            },
            request=request,
        )

        # Low stock / Out of stock trigger
        if new_quantity <= inventory.low_stock_threshold:
            severity = (
                SystemAlert.AlertSeverity.CRITICAL
                if new_quantity == 0
                else SystemAlert.AlertSeverity.WARNING
            )
            title = (
                f"Tugagan zaxira (Out of Stock): {variant.sku}"
                if new_quantity == 0
                else f"Kam qolgan zaxira (Low Stock): {variant.sku}"
            )
            SystemAlert.objects.create(
                alert_type=SystemAlert.AlertType.LOW_STOCK,
                severity=severity,
                title=title,
                message=f"Mahsulot '{variant.product.name}' (SKU: {variant.sku}) bo'yicha joriy qoldiq: {new_quantity} ta (chegara: {inventory.low_stock_threshold}).",
            )

        return inventory, movement_log


def get_inventory_statistics() -> Dict[str, Any]:
    """
    Returns high-level inventory distribution statistics across all variants.
    """
    inventories = Inventory.objects.select_related('variant', 'variant__product').all()

    total_skus = inventories.count()
    out_of_stock_count = inventories.filter(quantity=0).count()
    low_stock_count = inventories.filter(
        quantity__gt=0,
        quantity__lte=F('low_stock_threshold'),
    ).count()
    healthy_stock_count = inventories.filter(quantity__gt=F('low_stock_threshold')).count()

    total_units_sum = inventories.aggregate(total_units=Sum('quantity'))['total_units'] or 0
    total_reserved_sum = inventories.aggregate(total_res=Sum('reserved_quantity'))['total_res'] or 0

    return {
        'total_skus': total_skus,
        'healthy_stock_count': healthy_stock_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'total_units_in_stock': total_units_sum,
        'total_reserved_units': total_reserved_sum,
    }
