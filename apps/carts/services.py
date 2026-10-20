from decimal import Decimal
import uuid
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch

from apps.carts.models import Cart, CartItem
from apps.products.models import ProductVariant

User = get_user_model()


class CartService:
    """
    Centralized service layer handling business logic for Shopping Carts:
    - Session and user cart resolution
    - Adding, updating, removing items with strict inventory validation
    - Real-time stock checks and price change warnings
    - Merging guest carts into authenticated user carts
    - N+1 query optimization
    """

    SESSION_KEY_HEADER = 'X-Session-Key'
    CART_ID_HEADER = 'X-Cart-ID'

    @classmethod
    def get_session_key(cls, request) -> Optional[str]:
        """
        Extracts session key or cart ID from request headers or Django session.
        """
        return (
            request.headers.get(cls.SESSION_KEY_HEADER)
            or request.META.get('HTTP_X_SESSION_KEY')
            or request.headers.get(cls.CART_ID_HEADER)
            or request.META.get('HTTP_X_CART_ID')
            or request.session.session_key
        )

    @classmethod
    def get_or_create_cart(cls, request) -> Tuple[Cart, bool, Optional[str]]:
        """
        Resolves or creates an active OPEN cart for either an authenticated user or guest.
        Returns: (cart, created, newly_generated_session_key)
        """
        if request.user.is_authenticated:
            cart, created = Cart.objects.get_or_create(
                user=request.user,
                status=Cart.CartStatus.OPEN,
            )
            return cart, created, None

        # Guest shopper logic
        client_key = cls.get_session_key(request)
        newly_generated_key = None

        if client_key:
            # 1. Try finding by session_key
            cart = Cart.objects.filter(
                session_key=client_key,
                status=Cart.CartStatus.OPEN,
                user__isnull=True,
            ).first()

            # 2. Try finding by UUID if client_key looks like a UUID
            if not cart:
                try:
                    uuid_val = uuid.UUID(client_key)
                    cart = Cart.objects.filter(
                        id=uuid_val,
                        status=Cart.CartStatus.OPEN,
                        user__isnull=True,
                    ).first()
                except (ValueError, TypeError):
                    cart = None

            if cart:
                return cart, False, None

            # If key provided but no active cart found, create new cart with this key
            cart = Cart.objects.create(
                session_key=client_key,
                status=Cart.CartStatus.OPEN,
            )
            return cart, True, None

        # No key provided, generate a new one
        newly_generated_key = uuid.uuid4().hex
        cart = Cart.objects.create(
            session_key=newly_generated_key,
            status=Cart.CartStatus.OPEN,
        )
        return cart, True, newly_generated_key

    @classmethod
    def get_active_cart(cls, request) -> Optional[Cart]:
        """
        Retrieves the active OPEN cart if it exists, without creating a new one.
        """
        if request.user.is_authenticated:
            return Cart.objects.filter(
                user=request.user,
                status=Cart.CartStatus.OPEN,
            ).first()

        client_key = cls.get_session_key(request)
        if not client_key:
            return None

        cart = Cart.objects.filter(
            session_key=client_key,
            status=Cart.CartStatus.OPEN,
            user__isnull=True,
        ).first()

        if not cart:
            try:
                uuid_val = uuid.UUID(client_key)
                cart = Cart.objects.filter(
                    id=uuid_val,
                    status=Cart.CartStatus.OPEN,
                    user__isnull=True,
                ).first()
            except (ValueError, TypeError):
                cart = None

        return cart

    @classmethod
    def get_optimized_cart(cls, cart_id: uuid.UUID) -> Optional[Cart]:
        """
        Fetches cart with comprehensive prefetching to prevent N+1 SQL queries.
        Loads variants, products, brands, attributes, inventory, and media in minimal queries.
        """
        items_qs = CartItem.objects.select_related(
            'variant',
            'variant__product',
            'variant__product__brand',
            'variant__inventory',
        ).prefetch_related(
            'variant__attributes__attribute',
            'variant__media',
            'variant__product__media',
        ).order_by('-created_at')

        return Cart.objects.filter(id=cart_id).prefetch_related(
            Prefetch('items', queryset=items_qs)
        ).first()

    @classmethod
    @transaction.atomic
    def add_item(cls, cart: Cart, variant_id: int, quantity: int = 1) -> CartItem:
        """
        Adds a product variant to the cart or increments existing quantity.
        Validates variant active status and real-time inventory limits.
        """
        if quantity < 1:
            raise ValidationError({'quantity': "Quantity must be at least 1."})

        try:
            variant = ProductVariant.objects.select_related('product', 'inventory').get(
                id=variant_id,
                is_active=True,
                product__is_active=True,
            )
        except ProductVariant.DoesNotExist:
            raise ValidationError({'variant_id': "Product variant not found or is currently inactive."})

        available_qty = variant.inventory.available_quantity if hasattr(variant, 'inventory') else 0

        # Check existing item in cart
        cart_item = CartItem.objects.filter(cart=cart, variant=variant).first()
        current_qty = cart_item.quantity if cart_item else 0
        target_qty = current_qty + quantity

        if target_qty > available_qty:
            raise ValidationError({
                'quantity': (
                    f"Insufficient stock for '{variant.product.name} ({variant.sku})'. "
                    f"Available in stock: {available_qty}, already in cart: {current_qty}, requested additional: {quantity}."
                ),
                'available_quantity': available_qty,
            })

        if cart_item:
            cart_item.quantity = target_qty
            cart_item.save(update_fields=['quantity', 'updated_at'])
        else:
            cart_item = CartItem.objects.create(
                cart=cart,
                variant=variant,
                quantity=quantity,
                unit_price_at_addition=variant.final_price,
            )

        return cart_item

    @classmethod
    @transaction.atomic
    def update_item_quantity(cls, cart: Cart, item_id: int, quantity: int) -> CartItem:
        """
        Updates the exact quantity of an existing cart item.
        """
        if quantity < 1:
            raise ValidationError({'quantity': "Quantity must be at least 1."})

        try:
            cart_item = CartItem.objects.select_related(
                'variant', 'variant__product', 'variant__inventory'
            ).get(id=item_id, cart=cart)
        except CartItem.DoesNotExist:
            raise CartItem.DoesNotExist("Cart item not found in the current cart.")

        available_qty = cart_item.variant.inventory.available_quantity if hasattr(cart_item.variant, 'inventory') else 0
        if quantity > available_qty:
            raise ValidationError({
                'quantity': (
                    f"Insufficient stock for '{cart_item.variant.product.name} ({cart_item.variant.sku})'. "
                    f"Available in stock: {available_qty}, requested: {quantity}."
                ),
                'available_quantity': available_qty,
            })

        cart_item.quantity = quantity
        cart_item.save(update_fields=['quantity', 'updated_at'])
        return cart_item

    @classmethod
    def remove_item(cls, cart: Cart, item_id: int) -> bool:
        """
        Deletes a specific item from the cart.
        """
        try:
            cart_item = CartItem.objects.get(id=item_id, cart=cart)
            cart_item.delete()
            return True
        except CartItem.DoesNotExist:
            raise CartItem.DoesNotExist("Cart item not found in the current cart.")

    @classmethod
    def clear_cart(cls, cart: Cart) -> None:
        """
        Removes all items from the cart.
        """
        cart.clear()

    @classmethod
    @transaction.atomic
    def merge_carts(
        cls,
        user,
        guest_cart_id: Optional[str] = None,
        guest_session_key: Optional[str] = None,
    ) -> Cart:
        """
        Merges guest cart items into the authenticated user's active cart.
        """
        if not user.is_authenticated:
            raise ValidationError("Authentication required to merge cart.")

        user_cart, _ = Cart.objects.get_or_create(
            user=user,
            status=Cart.CartStatus.OPEN,
        )

        guest_cart = None
        if guest_cart_id:
            try:
                uuid_val = uuid.UUID(str(guest_cart_id))
                guest_cart = Cart.objects.filter(
                    id=uuid_val,
                    status=Cart.CartStatus.OPEN,
                    user__isnull=True,
                ).first()
            except (ValueError, TypeError):
                guest_cart = None

        if not guest_cart and guest_session_key:
            guest_cart = Cart.objects.filter(
                session_key=guest_session_key,
                status=Cart.CartStatus.OPEN,
                user__isnull=True,
            ).first()

        if not guest_cart:
            raise ValidationError({"guest_cart": "Valid open guest cart not found."})

        user_cart.merge_with(guest_cart)
        return user_cart

    @classmethod
    def get_cart_warnings(cls, cart: Cart) -> List[str]:
        """
        Generates dynamic alerts for customer if items have changed in price
        or are no longer available in the requested quantity.
        """
        warnings = []
        for item in cart.items.all():
            variant = item.variant
            # Price change notification
            if item.is_price_changed:
                diff = item.current_unit_price - item.unit_price_at_addition
                if diff > 0:
                    warnings.append(
                        f"Price for '{variant.product.name} ({variant.sku})' increased from "
                        f"{item.unit_price_at_addition:,.2f} UZS to {item.current_unit_price:,.2f} UZS."
                    )
                else:
                    warnings.append(
                        f"Good news! Price for '{variant.product.name} ({variant.sku})' decreased from "
                        f"{item.unit_price_at_addition:,.2f} UZS to {item.current_unit_price:,.2f} UZS."
                    )

            # Stock availability notification
            if hasattr(variant, 'inventory'):
                avail = variant.inventory.available_quantity
                if avail == 0:
                    warnings.append(
                        f"'{variant.product.name} ({variant.sku})' is now out of stock."
                    )
                elif avail < item.quantity:
                    warnings.append(
                        f"Only {avail} unit(s) remaining for '{variant.product.name} ({variant.sku})' "
                        f"(you have {item.quantity} in your cart)."
                    )

            if not variant.is_active or not variant.product.is_active:
                warnings.append(
                    f"'{variant.product.name} ({variant.sku})' is no longer available for purchase."
                )

        return warnings
