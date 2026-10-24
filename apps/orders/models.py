import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


class Coupon(models.Model):
    """
    Promotional discounts and coupon vouchers management.
    Supports percentage-based and fixed-amount discounts with usage limits,
    expiration intervals, and minimum order amount constraints.
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'PERCENTAGE', 'Percentage'
        FIXED_AMOUNT = 'FIXED_AMOUNT', 'Fixed Amount'

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique promo code voucher string (case-insensitive).",
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )
    discount_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Percentage value (e.g. 15.00 for 15%) or fixed sum in UZS.",
    )
    min_order_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Minimum subtotal required to apply this coupon.",
    )
    max_discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Maximum discount cap for percentage discounts.",
    )
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total usage limit across all shoppers. Null indicates unlimited usage.",
    )
    usage_limit_per_user = models.PositiveIntegerField(
        default=1,
        help_text="Maximum times a single customer can redeem this coupon.",
    )
    used_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Total number of times this coupon has been successfully applied.",
    )
    valid_from = models.DateTimeField(
        help_text="Start timestamp when coupon becomes redeemable.",
    )
    valid_until = models.DateTimeField(
        help_text="End timestamp after which coupon expires.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this coupon is active and usable.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'coupons'
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']

    def __str__(self) -> str:
        discount_display = (
            f"{self.discount_value}%"
            if self.discount_type == self.DiscountType.PERCENTAGE
            else f"{self.discount_value:,.2f} UZS"
        )
        return f"{self.code} ({discount_display})"

    def clean(self):
        super().clean()
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError({'valid_until': "Expiration date must be later than start date."})

        if self.discount_type == self.DiscountType.PERCENTAGE:
            if self.discount_value > Decimal('100.00'):
                raise ValidationError({'discount_value': "Percentage discount cannot exceed 100%."})

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def is_valid(self, user=None, subtotal: Decimal = None) -> tuple[bool, str]:
        """
        Validates coupon against current time, active status, system usage limits,
        user usage limits, and minimum order subtotal.
        Returns a tuple of (is_valid: bool, message: str).
        """
        now = timezone.now()

        if not self.is_active:
            return False, "This coupon is no longer active."

        if now < self.valid_from:
            return False, "This coupon is not valid yet."

        if now > self.valid_until:
            return False, "This coupon has expired."

        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False, "This coupon has reached its maximum usage limit."

        if subtotal is not None and subtotal < self.min_order_amount:
            return False, f"Minimum order amount to apply this coupon is {self.min_order_amount:,.2f} UZS."

        if user and user.is_authenticated:
            user_usage_count = self.usages.filter(user=user).count()
            if user_usage_count >= self.usage_limit_per_user:
                return False, "You have already redeemed this coupon the maximum allowed times."

        return True, "Coupon is valid."

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """
        Calculates the exact discount amount for a given order subtotal.
        """
        if subtotal <= Decimal('0.00'):
            return Decimal('0.00')

        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = (subtotal * self.discount_value) / Decimal('100.00')
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        else:
            discount = min(self.discount_value, subtotal)

        return discount.quantize(Decimal('0.01'))


class Order(models.Model):
    """
    Central Order entity managing customer orders, lifecycle statuses,
    payment and shipping integrations, and immutable financial totals.
    """

    class OrderStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        AWAITING_PAYMENT = 'AWAITING_PAYMENT', 'Awaiting Payment'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        PROCESSING = 'PROCESSING', 'Processing'
        SHIPPED = 'SHIPPED', 'Shipped'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'
        REFUNDED = 'REFUNDED', 'Refunded'

    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'
        PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED', 'Partially Refunded'
        REFUNDED = 'REFUNDED', 'Refunded'
        FAILED = 'FAILED', 'Failed'

    class PaymentMethod(models.TextChoices):
        PAYME = 'PAYME', 'Payme'
        CLICK = 'CLICK', 'Click'
        UZUM = 'UZUM', 'Uzum Bank'
        CASH_ON_DELIVERY = 'CASH_ON_DELIVERY', 'Cash on Delivery'
        CARD_ON_DELIVERY = 'CARD_ON_DELIVERY', 'Card on Delivery'

    class ShippingMethod(models.TextChoices):
        STANDARD = 'STANDARD', 'Standard Delivery'
        EXPRESS = 'EXPRESS', 'Express Delivery'
        PICKUP = 'PICKUP', 'Pickup'

    id = models.BigAutoField(primary_key=True)
    order_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Human-readable unique tracking identifier (e.g. ORD-20261022-A8F2K1).",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        db_index=True,
        help_text="Customer who placed the order. SET_NULL preserves legal audit records if account is removed.",
    )
    cart = models.ForeignKey(
        'carts.Cart',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        help_text="Reference to the converted shopping cart.",
    )
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        help_text="Applied discount promo voucher, if any.",
    )

    status = models.CharField(
        max_length=25,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=25,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=25,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH_ON_DELIVERY,
    )
    shipping_method = models.CharField(
        max_length=25,
        choices=ShippingMethod.choices,
        default=ShippingMethod.STANDARD,
    )

    # Financial snapshots
    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Sum of line items at the time of purchase.",
    )
    shipping_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cost charged for delivery.",
    )
    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total savings applied via coupon or discounts.",
    )
    total_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Final payable amount: subtotal + shipping_fee - discount_amount.",
    )
    currency = models.CharField(
        max_length=3,
        default='UZS',
        help_text="ISO 4217 currency code.",
    )

    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Courier or logistics service consignment tracking number.",
    )
    customer_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Instructions or special requests from the customer.",
    )
    cancellation_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason recorded if the order is cancelled.",
    )
    admin_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Internal notes accessible only by staff members.",
    )

    paid_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self) -> str:
        return f"{self.order_number} [{self.get_status_display()}] - {self.total_price:,.2f} {self.currency}"

    @classmethod
    def generate_order_number(cls) -> str:
        """
        Generates a unique, non-sequential, customer-friendly order identifier.
        Format: ORD-YYYYMMDD-XXXXXX (e.g. ORD-20261022-A8F2K1)
        """
        date_str = timezone.now().strftime('%Y%m%d')
        while True:
            random_suffix = secrets.token_hex(3).upper()
            candidate = f"ORD-{date_str}-{random_suffix}"
            if not cls.objects.filter(order_number=candidate).exists():
                return candidate

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)

    @property
    def total_items(self) -> int:
        """
        Total quantity of all items in this order.
        """
        if hasattr(self, '_prefetched_objects_cache') and 'items' in self._prefetched_objects_cache:
            return sum(item.quantity for item in self.items.all())
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def can_cancel(self) -> bool:
        """
        Determines whether the order can be cancelled by the user or system.
        Orders that are already shipped, delivered, or cancelled cannot be cancelled.
        """
        return self.status in [
            self.OrderStatus.PENDING,
            self.OrderStatus.AWAITING_PAYMENT,
            self.OrderStatus.CONFIRMED,
        ]

    def recalculate_totals(self, save: bool = True):
        """
        Recalculates order subtotal from order items and recomputes total_price.
        """
        items_subtotal = sum((item.total_price for item in self.items.all()), Decimal('0.00'))
        self.subtotal = items_subtotal.quantize(Decimal('0.01'))

        computed_total = max(Decimal('0.00'), self.subtotal + self.shipping_fee - self.discount_amount)
        self.total_price = computed_total.quantize(Decimal('0.01'))

        if save:
            self.save(update_fields=['subtotal', 'total_price', 'updated_at'])

    @transaction.atomic
    def transition_status(
        self,
        new_status: str,
        comment: str = '',
        user=None,
        is_customer_visible: bool = True,
    ):
        """
        Transitions the order to a new status and logs the event in OrderStatusHistory.
        """
        old_status = self.status
        if old_status == new_status:
            return

        self.status = new_status
        now = timezone.now()

        if new_status == self.OrderStatus.DELIVERED and not self.delivered_at:
            self.delivered_at = now
        elif new_status == self.OrderStatus.CANCELLED and not self.cancelled_at:
            self.cancelled_at = now

        update_fields = ['status', 'delivered_at', 'cancelled_at', 'updated_at']
        if self.cancellation_reason:
            update_fields.append('cancellation_reason')

        self.save(update_fields=update_fields)

        OrderStatusHistory.objects.create(
            order=self,
            old_status=old_status,
            new_status=new_status,
            comment=comment,
            created_by=user,
            is_customer_visible=is_customer_visible,
        )

    @transaction.atomic
    def mark_as_paid(self, user=None, comment: str = "Payment confirmed successfully"):
        """
        Marks the order payment status as PAID, sets paid_at, and progresses status.
        """
        self.payment_status = self.PaymentStatus.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=['payment_status', 'paid_at', 'updated_at'])

        if self.status in [self.OrderStatus.PENDING, self.OrderStatus.AWAITING_PAYMENT]:
            self.transition_status(
                new_status=self.OrderStatus.CONFIRMED,
                comment=comment,
                user=user,
                is_customer_visible=True,
            )

    @transaction.atomic
    def cancel(self, reason: str = '', user=None):
        """
        Cancels the order, logs the reason, and safely returns reserved inventory stock.
        """
        if not self.can_cancel:
            raise ValidationError(
                f"Order {self.order_number} cannot be cancelled in its current state [{self.status}]."
            )

        self.cancellation_reason = reason
        self.transition_status(
            new_status=self.OrderStatus.CANCELLED,
            comment=f"Order cancelled: {reason}" if reason else "Order cancelled.",
            user=user,
            is_customer_visible=True,
        )

        # Release reserved inventory
        for item in self.items.select_related('variant__inventory').all():
            if item.variant and hasattr(item.variant, 'inventory') and item.variant.inventory:
                inventory = item.variant.inventory
                # If payment was already made, restore full quantity; if pending, restore reserved quantity
                if self.payment_status == self.PaymentStatus.PAID:
                    inventory.quantity += item.quantity
                else:
                    inventory.reserved_quantity = max(0, inventory.reserved_quantity - item.quantity)
                inventory.save(update_fields=['quantity', 'reserved_quantity', 'updated_at'])


class OrderAddress(models.Model):
    """
    Immutable shipping address snapshot attached to an individual Order.
    Protects order shipping history from subsequent profile address updates or deletions.
    """

    id = models.BigAutoField(primary_key=True)
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='shipping_address',
        help_text="Order associated with this shipping destination.",
    )
    recipient_name = models.CharField(
        max_length=255,
        help_text="Full legal name of the person receiving the parcel.",
    )
    phone_number = models.CharField(
        max_length=20,
        help_text="Primary contact telephone number for delivery courier.",
    )
    alternative_phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Secondary backup telephone number.",
    )
    region = models.CharField(
        max_length=100,
        help_text="Province or autonomous region (e.g. Tashkent, Samarkand).",
    )
    district = models.CharField(
        max_length=100,
        help_text="District or city (e.g. Mirabad, Yunusabad).",
    )
    street_address = models.CharField(
        max_length=255,
        help_text="Street name, house/building number.",
    )
    apartment_office = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Apartment, entrance, floor, or suite details.",
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Postal zip code.",
    )
    landmark = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Nearby recognizable landmark to guide courier.",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS latitude coordinate.",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS longitude coordinate.",
    )
    delivery_instructions = models.TextField(
        blank=True,
        null=True,
        help_text="Driver instructions (e.g. Intercom code, leave at reception).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_addresses'
        verbose_name = 'Order Shipping Address'
        verbose_name_plural = 'Order Shipping Addresses'

    def __str__(self) -> str:
        return f"{self.recipient_name} - {self.full_address}"

    @property
    def full_address(self) -> str:
        """
        Returns a cleanly formatted multi-segment address string.
        """
        parts = [self.region, self.district, self.street_address]
        if self.apartment_office:
            parts.append(f"Apt/Office: {self.apartment_office}")
        if self.postal_code:
            parts.append(f"Postal Code: {self.postal_code}")
        return ", ".join(filter(None, parts))


class OrderItem(models.Model):
    """
    Individual SKU line item snapshot belonging to an Order.
    Stores fixed prices, SKU, attributes, and product names as they existed
    at the time the order was placed.
    """

    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
        help_text="Reference to product variant SKU. SET_NULL prevents record deletion if catalog item is removed.",
    )
    product_name = models.CharField(
        max_length=255,
        help_text="Snapshot of the base product title at checkout.",
    )
    variant_sku = models.CharField(
        max_length=100,
        help_text="Snapshot of the variant SKU identifier.",
    )
    variant_attributes_display = models.CharField(
        max_length=255,
        blank=True,
        help_text="Readable attribute combination snapshot (e.g. 'Color: Space Grey | Storage: 256GB').",
    )
    attributes_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured JSON snapshot of variant attributes at the moment of checkout.",
    )
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Snapshot of unit selling price at purchase time.",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    total_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Line total: unit_price * quantity.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'order_items'
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        ordering = ['id']

    def __str__(self) -> str:
        return f"{self.product_name} ({self.variant_sku}) x {self.quantity}"

    def save(self, *args, **kwargs):
        self.total_price = (self.unit_price * self.quantity).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    """
    Audit log and customer tracking timeline recording every state transition
    throughout the lifecycle of an Order.
    """

    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history',
    )
    old_status = models.CharField(
        max_length=25,
        choices=Order.OrderStatus.choices,
        blank=True,
        null=True,
    )
    new_status = models.CharField(
        max_length=25,
        choices=Order.OrderStatus.choices,
    )
    comment = models.CharField(
        max_length=255,
        blank=True,
        help_text="Explanatory comment or reason for this status change.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_status_changes',
        help_text="User or staff administrator who initiated status change. Null represents automated system event.",
    )
    is_customer_visible = models.BooleanField(
        default=True,
        help_text="Whether this transition is displayed on the public customer tracking timeline.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_status_history'
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"{self.order.order_number}: {self.old_status or 'START'} -> {self.new_status} at {self.created_at:%Y-%m-%d %H:%M}"


class CouponUsage(models.Model):
    """
    Record of individual coupon voucher redemption per customer and per order.
    Enforces per-user redemption limits and maintains coupon analytics.
    """

    id = models.BigAutoField(primary_key=True)
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name='usages',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coupon_usages',
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='coupon_usages',
    )
    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Actual monetary discount granted for this redemption.",
    )
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'coupon_usages'
        verbose_name = 'Coupon Usage'
        verbose_name_plural = 'Coupon Usages'
        ordering = ['-used_at']
        constraints = [
            models.UniqueConstraint(
                fields=['coupon', 'order'],
                name='unique_coupon_per_order',
            ),
        ]

    def __str__(self) -> str:
        return f"Coupon {self.coupon.code} redeemed on Order {self.order.order_number} by {self.user.email}"
