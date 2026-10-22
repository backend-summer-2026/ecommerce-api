from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.carts.models import Cart, CartItem
from apps.orders.models import (
    Coupon,
    CouponUsage,
    Order,
    OrderAddress,
    OrderItem,
    OrderStatusHistory,
)
from apps.products.models import Inventory

User = get_user_model()


class OrderService:
    """
    Centralized service layer encapsulating business logic for Orders:
    - Checkout preview with real-time inventory checks and fee computations
    - Coupon validation and discount calculations
    - High-concurrency ACID order placement with pessimistic stock locking (select_for_update)
    - Order cancellation with inventory stock release
    - Admin status transitions with tracking and audit trail logging
    """

    # Standard delivery pricing rules (UZS)
    SHIPPING_FEES = {
        Order.ShippingMethod.PICKUP: {
            'default': Decimal('0.00'),
        },
        Order.ShippingMethod.STANDARD: {
            'tashkent': Decimal('25000.00'),
            'other': Decimal('40000.00'),
        },
        Order.ShippingMethod.EXPRESS: {
            'tashkent': Decimal('45000.00'),
            'other': Decimal('70000.00'),
        },
    }

    @classmethod
    def calculate_shipping_fee(cls, shipping_method: str, region: str = '') -> Decimal:
        """
        Calculates shipping fee based on delivery method and delivery destination region.
        """
        if shipping_method == Order.ShippingMethod.PICKUP:
            return Decimal('0.00')

        method_rules = cls.SHIPPING_FEES.get(shipping_method, cls.SHIPPING_FEES[Order.ShippingMethod.STANDARD])
        region_clean = (region or '').strip().lower()

        is_tashkent = 'tashkent' in region_clean or 'toshkent' in region_clean or region_clean == ''
        if is_tashkent:
            return method_rules['tashkent']
        return method_rules['other']

    @classmethod
    def validate_coupon(
        cls,
        coupon_code: Optional[str],
        user,
        subtotal: Decimal,
    ) -> Tuple[Optional[Coupon], Decimal, str]:
        """
        Validates a promotional coupon code against user criteria, usage limits,
        expiration date, and minimum subtotal.
        Returns: (coupon_instance, discount_amount, message)
        """
        if not coupon_code:
            return None, Decimal('0.00'), ''

        code_cleaned = coupon_code.strip().upper()
        coupon = Coupon.objects.filter(code=code_cleaned).first()
        if not coupon:
            return None, Decimal('0.00'), f"Coupon voucher '{code_cleaned}' not found."

        is_valid, reason = coupon.is_valid(user=user, subtotal=subtotal)
        if not is_valid:
            return None, Decimal('0.00'), reason

        discount_amount = coupon.calculate_discount(subtotal)
        return coupon, discount_amount, "Coupon applied successfully."

    @classmethod
    def preview_checkout(
        cls,
        user,
        shipping_method: str = Order.ShippingMethod.STANDARD,
        coupon_code: Optional[str] = None,
        region: str = '',
    ) -> Dict[str, Any]:
        """
        Precomputes checkout totals, checks stock availability for all cart items,
        calculates delivery fees and discounts, and generates real-time warnings.
        """
        cart = (
            Cart.objects.filter(user=user, status=Cart.CartStatus.OPEN)
            .prefetch_related(
                'items__variant__inventory',
                'items__variant__product__media',
                'items__variant__media',
                'items__variant__attributes__attribute',
            )
            .first()
        )

        if not cart or cart.items.count() == 0:
            raise ValidationError("Your shopping cart is empty.")

        # Items subtotal at current selling prices
        subtotal = cart.total_price
        shipping_fee = cls.calculate_shipping_fee(shipping_method, region)
        coupon, discount_amount, coupon_message = cls.validate_coupon(coupon_code, user, subtotal)

        total_price = max(Decimal('0.00'), subtotal + shipping_fee - discount_amount).quantize(Decimal('0.01'))

        warnings: List[str] = []
        has_stock_issues = False
        items_preview: List[Dict[str, Any]] = []

        for item in cart.items.all():
            variant = item.variant
            available_qty = (
                variant.inventory.available_quantity
                if hasattr(variant, 'inventory') and variant.inventory
                else 0
            )
            is_available = available_qty >= item.quantity

            if not is_available:
                has_stock_issues = True
                warnings.append(
                    f"Insufficient inventory for {variant.product.name} ({variant.sku}). Available: {available_qty}, requested: {item.quantity}."
                )

            if item.is_price_changed:
                warnings.append(
                    f"Price for {variant.product.name} changed from {item.unit_price_at_addition} to {item.current_unit_price} UZS."
                )

            # Resolve image URL if available
            variant_media = list(variant.media.all())
            main_media = next((m for m in variant_media if m.is_main), None) or (
                variant_media[0] if variant_media else None
            )
            if not main_media and hasattr(variant, 'product'):
                prod_media = list(variant.product.media.all())
                main_media = next((m for m in prod_media if m.is_main), None) or (
                    prod_media[0] if prod_media else None
                )

            image_url = main_media.file.url if (main_media and main_media.file) else None

            # Variant attributes display
            attr_map = {av.attribute.name: av.value for av in variant.attributes.all()}
            attr_display = " | ".join(f"{k}: {v}" for k, v in attr_map.items())

            items_preview.append({
                'item_id': item.id,
                'variant_id': variant.id,
                'product_name': variant.product.name,
                'variant_sku': variant.sku,
                'variant_title': variant.title,
                'variant_attributes_display': attr_display,
                'image_url': image_url,
                'quantity': item.quantity,
                'unit_price': item.current_unit_price,
                'subtotal': item.subtotal,
                'total_price': item.total_price,
                'available_quantity': available_qty,
                'is_available': is_available,
                'is_price_changed': item.is_price_changed,
            })

        return {
            'cart_id': cart.id,
            'total_items': cart.total_items,
            'subtotal': subtotal,
            'shipping_method': shipping_method,
            'shipping_fee': shipping_fee,
            'coupon_code': coupon.code if coupon else None,
            'coupon_message': coupon_message if coupon_code else None,
            'discount_amount': discount_amount,
            'total_price': total_price,
            'currency': 'UZS',
            'has_stock_issues': has_stock_issues,
            'warnings': warnings,
            'items': items_preview,
        }

    @classmethod
    @transaction.atomic
    def create_order_from_cart(
        cls,
        user,
        shipping_address_data: Dict[str, Any],
        shipping_method: str = Order.ShippingMethod.STANDARD,
        payment_method: str = Order.PaymentMethod.CASH_ON_DELIVERY,
        coupon_code: Optional[str] = None,
        customer_notes: Optional[str] = None,
    ) -> Order:
        """
        Executes order checkout atomically with pessimistic row-level locking (select_for_update)
        on Inventory to prevent overselling, reserves inventory, creates Order, OrderAddress,
        OrderItems, records CouponUsage, converts Cart, and logs initial status history.
        """
        cart = (
            Cart.objects.filter(user=user, status=Cart.CartStatus.OPEN)
            .prefetch_related(
                'items__variant__product',
                'items__variant__attributes__attribute',
            )
            .first()
        )

        if not cart or cart.items.count() == 0:
            raise ValidationError("Your shopping cart is empty.")

        cart_items = list(cart.items.all())
        variant_ids = [item.variant_id for item in cart_items]

        # Pessimistic concurrency control: lock inventory rows for update
        locked_inventories = {
            inv.variant_id: inv
            for inv in Inventory.objects.select_for_update().filter(variant_id__in=variant_ids)
        }

        # Verify stock sufficiency for all variants
        for item in cart_items:
            inv = locked_inventories.get(item.variant_id)
            if not inv or inv.available_quantity < item.quantity:
                avail = inv.available_quantity if inv else 0
                raise ValidationError(
                    f"Insufficient stock for '{item.variant.product.name}' ({item.variant.sku}). "
                    f"Available: {avail}, requested: {item.quantity}."
                )

        # Financial totals (sum of line items at current selling prices)
        subtotal = cart.total_price
        shipping_fee = cls.calculate_shipping_fee(
            shipping_method,
            region=shipping_address_data.get('region', ''),
        )

        coupon = None
        discount_amount = Decimal('0.00')
        if coupon_code:
            coupon, discount_amount, message = cls.validate_coupon(coupon_code, user, subtotal)
            if not coupon:
                raise ValidationError(f"Invalid coupon: {message}")

        total_price = max(Decimal('0.00'), subtotal + shipping_fee - discount_amount).quantize(Decimal('0.01'))

        # Set appropriate initial status
        if payment_method in [
            Order.PaymentMethod.PAYME,
            Order.PaymentMethod.CLICK,
            Order.PaymentMethod.UZUM,
        ]:
            initial_status = Order.OrderStatus.AWAITING_PAYMENT
        else:
            initial_status = Order.OrderStatus.PENDING

        # Create master Order record
        order = Order.objects.create(
            user=user,
            cart=cart,
            coupon=coupon,
            status=initial_status,
            payment_status=Order.PaymentStatus.PENDING,
            payment_method=payment_method,
            shipping_method=shipping_method,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            discount_amount=discount_amount,
            total_price=total_price,
            currency='UZS',
            customer_notes=customer_notes or '',
        )

        # Create immutable OrderAddress snapshot
        OrderAddress.objects.create(
            order=order,
            recipient_name=shipping_address_data['recipient_name'],
            phone_number=shipping_address_data['phone_number'],
            alternative_phone_number=shipping_address_data.get('alternative_phone_number') or '',
            region=shipping_address_data['region'],
            district=shipping_address_data['district'],
            street_address=shipping_address_data['street_address'],
            apartment_office=shipping_address_data.get('apartment_office') or '',
            postal_code=shipping_address_data.get('postal_code') or '',
            landmark=shipping_address_data.get('landmark') or '',
            latitude=shipping_address_data.get('latitude'),
            longitude=shipping_address_data.get('longitude'),
            delivery_instructions=shipping_address_data.get('delivery_instructions') or '',
        )

        # Create immutable OrderItem snapshots and reserve inventory
        for item in cart_items:
            inv = locked_inventories[item.variant_id]
            inv.reserved_quantity += item.quantity
            inv.save(update_fields=['reserved_quantity', 'updated_at'])

            attr_dict = {av.attribute.name: av.value for av in item.variant.attributes.all()}
            attr_display = " | ".join(f"{k}: {v}" for k, v in attr_dict.items())

            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                product_name=item.variant.product.name,
                variant_sku=item.variant.sku,
                variant_attributes_display=attr_display,
                attributes_snapshot=attr_dict,
                unit_price=item.current_unit_price,
                quantity=item.quantity,
                total_price=(item.current_unit_price * item.quantity).quantize(Decimal('0.01')),
            )

        # Record CouponUsage and increment count
        if coupon:
            CouponUsage.objects.create(
                coupon=coupon,
                user=user,
                order=order,
                discount_amount=discount_amount,
            )
            coupon.used_count += 1
            coupon.save(update_fields=['used_count', 'updated_at'])

        # Mark user cart as CONVERTED
        cart.status = Cart.CartStatus.CONVERTED
        cart.save(update_fields=['status', 'updated_at'])

        # Create initial order status history log
        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status=order.status,
            comment="Order placed and submitted successfully.",
            created_by=user,
            is_customer_visible=True,
        )

        return order

    @classmethod
    @transaction.atomic
    def cancel_order(cls, order: Order, user, reason: str = '') -> Order:
        """
        Cancels an order, releases reserved inventory stock, and logs history.
        """
        # Authorization check: only order owner or staff can cancel
        if not (user.is_staff or order.user_id == user.id):
            raise ValidationError("You do not have permission to cancel this order.")

        if not order.can_cancel:
            raise ValidationError(
                f"Order {order.order_number} cannot be cancelled in its current state [{order.status}]."
            )

        order.cancel(reason=reason, user=user)
        return order

    @classmethod
    @transaction.atomic
    def admin_transition_status(
        cls,
        order: Order,
        new_status: str,
        comment: str = '',
        user=None,
        tracking_number: Optional[str] = None,
        is_customer_visible: bool = True,
    ) -> Order:
        """
        Allows staff to advance order status, update tracking number, and append audit comment.
        """
        if new_status not in Order.OrderStatus.values:
            raise ValidationError(f"Invalid order status: '{new_status}'.")

        if tracking_number is not None:
            order.tracking_number = tracking_number.strip()
            order.save(update_fields=['tracking_number', 'updated_at'])

        order.transition_status(
            new_status=new_status,
            comment=comment,
            user=user,
            is_customer_visible=is_customer_visible,
        )
        return order
