import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


class Payment(models.Model):
    """
    Central payment entity representing an invoice/payment attempt for an Order.
    Coordinates between customer orders, payment gateways (Payme, Click, Uzum),
    and offline payment methods (Cash/Card on delivery).
    """

    class PaymentProvider(models.TextChoices):
        PAYME = 'PAYME', 'Payme'
        CLICK = 'CLICK', 'Click'
        UZUM = 'UZUM', 'Uzum Bank'
        CASH_ON_DELIVERY = 'CASH_ON_DELIVERY', 'Cash on Delivery'
        CARD_ON_DELIVERY = 'CARD_ON_DELIVERY', 'Card on Delivery'

    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        REFUNDED = 'REFUNDED', 'Refunded'
        PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED', 'Partially Refunded'

    id = models.BigAutoField(primary_key=True)
    payment_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Human-readable unique payment identifier (e.g. PAY-20261022-8F9B2C).",
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='payments',
        db_index=True,
        help_text="Order associated with this payment transaction. PROTECT prevents accidental deletion of financial records.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        db_index=True,
        help_text="Payer customer account. SET_NULL preserves historical financial records if user is deleted.",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Payable amount in specified currency.",
    )
    currency = models.CharField(
        max_length=3,
        default='UZS',
        help_text="ISO 4217 currency code.",
    )
    provider = models.CharField(
        max_length=25,
        choices=PaymentProvider.choices,
        help_text="Selected payment gateway or method.",
    )
    status = models.CharField(
        max_length=25,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
        help_text="Lifecycle state of this payment transaction.",
    )
    provider_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="External gateway transaction ID (e.g. Payme id, Click trans_id).",
    )
    provider_state = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Gateway internal state code or status flag.",
    )
    fee_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Gateway fee or transaction service charge.",
    )
    refunded_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total accumulated refunded amount for this payment.",
    )
    checkout_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        help_text="Gateway checkout redirect URL or mobile deep-link.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary snapshot data, receipts, and gateway specific payload.",
    )
    failure_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Detailed error description or reason if payment failed or was cancelled.",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_number']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['provider', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['provider_transaction_id']),
        ]

    def __str__(self) -> str:
        return f"{self.payment_number} [{self.get_status_display()}] - {self.amount:,.2f} {self.currency}"

    @classmethod
    def generate_payment_number(cls) -> str:
        """
        Generates a unique, non-sequential, customer-friendly payment identifier.
        Format: PAY-YYYYMMDD-XXXXXX (e.g. PAY-20261022-8F9B2C)
        """
        date_str = timezone.now().strftime('%Y%m%d')
        while True:
            random_suffix = secrets.token_hex(3).upper()
            candidate = f"PAY-{date_str}-{random_suffix}"
            if not cls.objects.filter(payment_number=candidate).exists():
                return candidate

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = self.generate_payment_number()
        super().save(*args, **kwargs)

    def can_refund(self, refund_amount: Decimal = None) -> bool:
        """
        Checks whether this payment can be refunded for a specified amount.
        """
        if self.status not in [self.PaymentStatus.SUCCESS, self.PaymentStatus.PARTIALLY_REFUNDED]:
            return False

        available_to_refund = self.amount - self.refunded_amount
        if available_to_refund <= Decimal('0.00'):
            return False

        if refund_amount is not None:
            if refund_amount <= Decimal('0.00') or refund_amount > available_to_refund:
                return False

        return True

    @transaction.atomic
    def mark_as_success(
        self,
        provider_transaction_id: str = None,
        save: bool = True,
        user=None,
    ):
        """
        Marks payment as SUCCESS, records paid_at timestamp, and automatically
        synchronizes with the related Order by invoking order.mark_as_paid().
        """
        self.status = self.PaymentStatus.SUCCESS
        self.paid_at = timezone.now()
        if provider_transaction_id:
            self.provider_transaction_id = provider_transaction_id

        if save:
            update_fields = ['status', 'paid_at', 'updated_at']
            if provider_transaction_id:
                update_fields.append('provider_transaction_id')
            self.save(update_fields=update_fields)

        # Synchronize linked Order state
        if self.order:
            self.order.mark_as_paid(
                user=user,
                comment=f"Payment confirmed via {self.get_provider_display()} ({self.payment_number})",
            )

    @transaction.atomic
    def mark_as_failed(self, reason: str = '', save: bool = True):
        """
        Marks payment as FAILED and records timestamp and reason.
        Does not cancel the Order, allowing user to retry payment.
        """
        self.status = self.PaymentStatus.FAILED
        self.failure_reason = reason
        self.failed_at = timezone.now()

        if save:
            self.save(update_fields=['status', 'failure_reason', 'failed_at', 'updated_at'])

        from apps.orders.models import Order
        if self.order and self.order.payment_status != Order.PaymentStatus.PAID:
            self.order.payment_status = Order.PaymentStatus.FAILED
            self.order.save(update_fields=['payment_status', 'updated_at'])

    @transaction.atomic
    def mark_as_cancelled(self, reason: str = '', save: bool = True):
        """
        Marks payment as CANCELLED by customer or gateway timeout.
        """
        self.status = self.PaymentStatus.CANCELLED
        self.failure_reason = reason or "Payment cancelled"
        self.cancelled_at = timezone.now()

        if save:
            self.save(update_fields=['status', 'failure_reason', 'cancelled_at', 'updated_at'])


class PaymentTransaction(models.Model):
    """
    Gateway communication audit log capturing raw requests, responses,
    webhooks, and state transitions for financial reconciliation and debugging.
    """

    class TransactionType(models.TextChoices):
        CHECK = 'CHECK', 'Check / Verify'
        CREATE = 'CREATE', 'Create Transaction'
        PERFORM = 'PERFORM', 'Perform / Charge'
        CANCEL = 'CANCEL', 'Cancel / Reverse'
        REFUND = 'REFUND', 'Refund'
        WEBHOOK = 'WEBHOOK', 'Webhook Notification'

    class TransactionStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'

    id = models.BigAutoField(primary_key=True)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text="Parent payment record.",
    )
    transaction_type = models.CharField(
        max_length=30,
        choices=TransactionType.choices,
        help_text="Type of operation performed with the payment gateway.",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Operation monetary amount.",
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING,
        help_text="Outcome status of this specific gateway call.",
    )
    idempotency_key = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Unique request key to guarantee idempotent execution.",
    )
    provider_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="External transaction or interaction identifier.",
    )
    request_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw payload sent to or received from payment gateway.",
    )
    response_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw response returned by payment gateway.",
    )
    error_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Gateway-specific error identifier or code.",
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Gateway error message or stack trace description.",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the caller/webhook sender for fraud monitoring.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'payment_transactions'
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment', 'transaction_type']),
            models.Index(fields=['idempotency_key']),
        ]

    def __str__(self) -> str:
        return f"Tx {self.id} [{self.get_transaction_type_display()} - {self.get_status_display()}] for {self.payment.payment_number}"


class Refund(models.Model):
    """
    Formal record of monetary refund issued back to customer.
    Maintains financial audit trail, authorized manager, and gateway refund details.
    """

    class RefundStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.BigAutoField(primary_key=True)
    refund_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Human-readable unique refund identifier (e.g. REF-20261022-8F9B2C).",
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name='refunds',
        help_text="Original payment record being refunded.",
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='payment_refunds',
        help_text="Associated order for this refund.",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Refund amount in specified currency.",
    )
    currency = models.CharField(
        max_length=3,
        default='UZS',
        help_text="ISO 4217 currency code.",
    )
    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
        db_index=True,
        help_text="Processing status of the refund.",
    )
    reason = models.TextField(
        blank=True,
        null=True,
        help_text="Explanation or customer complaint reason for refund.",
    )
    provider_refund_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Gateway refund reference identifier.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds',
        help_text="Staff administrator or manager who authorized this refund.",
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when refund was successfully processed by gateway.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Gateway refund confirmation payload.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_refunds'
        verbose_name = 'Payment Refund'
        verbose_name_plural = 'Payment Refunds'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.refund_number} [{self.get_status_display()}] - {self.amount:,.2f} {self.currency}"

    @classmethod
    def generate_refund_number(cls) -> str:
        """
        Generates a unique refund identifier.
        Format: REF-YYYYMMDD-XXXXXX (e.g. REF-20261022-8F9B2C)
        """
        date_str = timezone.now().strftime('%Y%m%d')
        while True:
            random_suffix = secrets.token_hex(3).upper()
            candidate = f"REF-{date_str}-{random_suffix}"
            if not cls.objects.filter(refund_number=candidate).exists():
                return candidate

    def clean(self):
        super().clean()
        if self.payment_id:
            available_to_refund = self.payment.amount - self.payment.refunded_amount
            # If creating a new refund or increasing amount, validate against payment amount
            if self.amount and self.amount > available_to_refund and self.status == self.RefundStatus.PENDING:
                raise ValidationError({
                    'amount': f"Refund amount ({self.amount:,.2f}) exceeds available payment balance ({available_to_refund:,.2f})."
                })

    def save(self, *args, **kwargs):
        if not self.refund_number:
            self.refund_number = self.generate_refund_number()
        if self.payment_id and not self.order_id:
            self.order = self.payment.order
        super().save(*args, **kwargs)

    @transaction.atomic
    def mark_as_completed(self, provider_refund_id: str = None, save: bool = True):
        """
        Marks refund as COMPLETED, increments payment.refunded_amount, updates
        payment.status (REFUNDED or PARTIALLY_REFUNDED), and synchronizes order.payment_status.
        """
        self.status = self.RefundStatus.COMPLETED
        self.processed_at = timezone.now()
        if provider_refund_id:
            self.provider_refund_id = provider_refund_id

        if save:
            update_fields = ['status', 'processed_at', 'updated_at']
            if provider_refund_id:
                update_fields.append('provider_refund_id')
            self.save(update_fields=update_fields)

        # Update payment
        payment = self.payment
        payment.refunded_amount = (payment.refunded_amount + self.amount).quantize(Decimal('0.01'))
        if payment.refunded_amount >= payment.amount:
            payment.status = Payment.PaymentStatus.REFUNDED
        else:
            payment.status = Payment.PaymentStatus.PARTIALLY_REFUNDED
        payment.save(update_fields=['refunded_amount', 'status', 'updated_at'])

        # Update order
        from apps.orders.models import Order
        order = self.order
        if order:
            if payment.status == Payment.PaymentStatus.REFUNDED:
                order.payment_status = Order.PaymentStatus.REFUNDED
            else:
                order.payment_status = Order.PaymentStatus.PARTIALLY_REFUNDED
            order.save(update_fields=['payment_status', 'updated_at'])


class SavedCard(models.Model):
    """
    Tokenized customer bank cards for secure 1-click checkout.
    PCI-DSS compliant: NEVER stores full PAN (card numbers) or CVV codes,
    only storing encrypted provider tokens and display masks.
    """

    class CardType(models.TextChoices):
        UZCARD = 'UZCARD', 'Uzcard'
        HUMO = 'HUMO', 'Humo'
        VISA = 'VISA', 'Visa'
        MASTERCARD = 'MASTERCARD', 'Mastercard'
        OTHER = 'OTHER', 'Other'

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_cards',
        help_text="Card owner customer account.",
    )
    provider = models.CharField(
        max_length=25,
        choices=Payment.PaymentProvider.choices,
        help_text="Payment gateway that issued the token (Payme, Click, Uzum).",
    )
    card_token = models.CharField(
        max_length=255,
        help_text="Opaque gateway token used to charge card without asking for credentials.",
    )
    card_mask = models.CharField(
        max_length=30,
        help_text="Display-safe masked card identifier (e.g. 8600 12** **** 1234).",
    )
    card_holder = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Embossed cardholder name if returned by gateway.",
    )
    card_type = models.CharField(
        max_length=20,
        choices=CardType.choices,
        default=CardType.OTHER,
        help_text="Payment card brand or network.",
    )
    expire_month = models.CharField(
        max_length=2,
        help_text="Card expiration two-digit month (e.g. 05).",
    )
    expire_year = models.CharField(
        max_length=4,
        help_text="Card expiration year (e.g. 2028).",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Designates this card as primary payment method.",
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Designates whether the card token was validated via SMS OTP.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_saved_cards'
        verbose_name = 'Saved Card'
        verbose_name_plural = 'Saved Cards'
        ordering = ['-is_default', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'provider', 'card_token'],
                name='unique_user_provider_card_token',
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_card_type_display()} {self.card_mask} ({self.get_provider_display()})"

    def save(self, *args, **kwargs):
        if self.is_default:
            SavedCard.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
