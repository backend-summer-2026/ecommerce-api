import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q


class Cart(models.Model):
    """
    Shopping cart model representing a customer's active or historic cart session.
    Supports both authenticated users and anonymous (guest) shoppers.
    """

    class CartStatus(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        MERGED = 'MERGED', 'Merged'
        CONVERTED = 'CONVERTED', 'Converted'
        ABANDONED = 'ABANDONED', 'Abandoned'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='carts',
        db_index=True,
    )
    session_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=CartStatus.choices,
        default=CartStatus.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'carts'
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(status='OPEN'),
                name='unique_active_user_cart',
            ),
        ]
        indexes = [
            models.Index(fields=['session_key', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self) -> str:
        owner = self.user.email if self.user else f"Guest ({self.session_key or str(self.id)[:8]})"
        return f"Cart {str(self.id)[:8]} - {owner} [{self.status}]"

    def clean(self):
        super().clean()
        if not self.user and not self.session_key:
            raise ValidationError("Cart must be associated with either an authenticated user or a session key.")

    @property
    def total_items(self) -> int:
        """
        Total quantity of all items in the cart.
        """
        return sum(item.quantity for item in self.items.all())

    @property
    def unique_items_count(self) -> int:
        """
        Number of distinct variant lines in the cart.
        """
        if hasattr(self, '_prefetched_objects_cache') and 'items' in self._prefetched_objects_cache:
            return len(self.items.all())
        return self.items.count()

    @property
    def subtotal(self) -> Decimal:
        """
        Subtotal before discounts (using regular variant prices).
        """
        total = sum((item.subtotal for item in self.items.all()), Decimal('0.00'))
        return total.quantize(Decimal('0.01'))

    @property
    def total_price(self) -> Decimal:
        """
        Total final price customer has to pay (using discounted variant prices).
        """
        total = sum((item.total_price for item in self.items.all()), Decimal('0.00'))
        return total.quantize(Decimal('0.01'))

    @property
    def total_discount(self) -> Decimal:
        """
        Total discount amount saved by customer across all cart items.
        """
        discount = self.subtotal - self.total_price
        return max(Decimal('0.00'), discount).quantize(Decimal('0.01'))

    @property
    def is_empty(self) -> bool:
        """
        Returns True if cart has no items.
        """
        if hasattr(self, '_prefetched_objects_cache') and 'items' in self._prefetched_objects_cache:
            return len(self.items.all()) == 0
        return not self.items.exists()

    @property
    def has_unavailable_items(self) -> bool:
        """
        Returns True if any item in the cart is inactive or out of stock.
        """
        return any(not item.is_available for item in self.items.all())

    def clear(self):
        """
        Removes all items from the cart.
        """
        self.items.all().delete()

    @transaction.atomic
    def merge_with(self, guest_cart: 'Cart'):
        """
        Merges an anonymous/guest cart's items into this authenticated user's cart.
        If a variant already exists, increments the quantity (capping at available inventory).
        Marks the guest cart as MERGED.
        """
        if not guest_cart or guest_cart.id == self.id:
            return

        for guest_item in guest_cart.items.select_related('variant__inventory').all():
            try:
                user_item = self.items.get(variant=guest_item.variant)
                new_quantity = user_item.quantity + guest_item.quantity
                if hasattr(guest_item.variant, 'inventory'):
                    available = guest_item.variant.inventory.available_quantity
                    new_quantity = min(new_quantity, available) if available > 0 else new_quantity
                user_item.quantity = max(1, new_quantity)
                user_item.save(update_fields=['quantity', 'updated_at'])
            except CartItem.DoesNotExist:
                guest_item.cart = self
                guest_item.save(update_fields=['cart', 'updated_at'])

        guest_cart.status = Cart.CartStatus.MERGED
        guest_cart.save(update_fields=['status', 'updated_at'])


class CartItem(models.Model):
    """
    Individual item line in a shopping cart, bound directly to a ProductVariant.
    """

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        related_name='cart_items',
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    unit_price_at_addition = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Snapshot of the variant's final price when the item was added.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cart_items'
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'variant'],
                name='unique_cart_variant',
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity}x {self.variant} in Cart {str(self.cart.id)[:8]}"

    def clean(self):
        super().clean()
        if self.quantity < 1:
            raise ValidationError({'quantity': "Quantity must be at least 1."})

        if hasattr(self.variant, 'inventory'):
            available = self.variant.inventory.available_quantity
            if available < self.quantity:
                raise ValidationError({
                    'quantity': (
                        f"Insufficient stock for variant '{self.variant.sku}'. "
                        f"Available quantity is {available}, requested {self.quantity}."
                    )
                })

    def save(self, *args, **kwargs):
        if self.unit_price_at_addition is None and self.variant_id:
            self.unit_price_at_addition = self.variant.final_price
        super().save(*args, **kwargs)

    @property
    def current_unit_price(self) -> Decimal:
        """
        Current real-time unit price taking discounts into account.
        """
        return self.variant.final_price

    @property
    def subtotal(self) -> Decimal:
        """
        Total price before discount (regular price * quantity).
        """
        return (self.variant.price * self.quantity).quantize(Decimal('0.01'))

    @property
    def total_price(self) -> Decimal:
        """
        Total final price (discounted price * quantity).
        """
        return (self.current_unit_price * self.quantity).quantize(Decimal('0.01'))

    @property
    def discount_amount(self) -> Decimal:
        """
        Discount amount saved on this line item.
        """
        discount = self.subtotal - self.total_price
        return max(Decimal('0.00'), discount).quantize(Decimal('0.01'))

    @property
    def is_price_changed(self) -> bool:
        """
        Checks whether the unit price changed since the item was added to the cart.
        """
        if self.unit_price_at_addition is None:
            return False
        return self.unit_price_at_addition != self.current_unit_price

    @property
    def is_available(self) -> bool:
        """
        Checks if the variant is active and has sufficient stock.
        """
        if not self.variant.is_active or not self.variant.product.is_active:
            return False
        if hasattr(self.variant, 'inventory'):
            return self.variant.inventory.available_quantity >= self.quantity
        return True
