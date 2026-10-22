from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Avg, Count, Q


class ReviewStatus(models.TextChoices):
    """
    Moderation states for customer reviews.
    """
    PENDING = 'PENDING', 'Pending Moderation'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'


class VoteType(models.TextChoices):
    """
    Voter feedback classification on review helpfulness.
    """
    HELPFUL = 'HELPFUL', 'Helpful'
    UNHELPFUL = 'UNHELPFUL', 'Unhelpful'


class Review(models.Model):
    """
    Product review submitted by authenticated customers.
    Includes numerical rating (1-5), optional verified purchase validation,
    moderation lifecycle, and denormalized helpful vote counters.
    """

    ReviewStatus = ReviewStatus

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="Customer who authored this review.",
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="Product catalog item being evaluated.",
    )
    order_item = models.ForeignKey(
        'orders.OrderItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        help_text="Purchased order item snapshot linking review to confirmed checkout.",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Numerical rating score from 1 (lowest) to 5 (highest).",
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short headline summarizing the reviewer's feedback.",
    )
    comment = models.TextField(
        help_text="Detailed written assessment and experiences with the product.",
    )
    pros = models.CharField(
        max_length=500,
        blank=True,
        help_text="Key advantages and positive features observed by customer.",
    )
    cons = models.CharField(
        max_length=500,
        blank=True,
        help_text="Key drawbacks or potential improvements noted by customer.",
    )
    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
        help_text="Content moderation status.",
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Moderation explanation if review was rejected.",
    )
    is_verified_purchase = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates whether review is validated against confirmed customer order.",
    )
    likes_count = models.PositiveIntegerField(
        default=0,
        help_text="Denormalized count of helpful votes.",
    )
    dislikes_count = models.PositiveIntegerField(
        default=0,
        help_text="Denormalized count of unhelpful votes.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when review was originally submitted.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when review was last edited.",
    )

    class Meta:
        db_table = 'reviews'
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']
        unique_together = ('user', 'product')
        indexes = [
            models.Index(fields=['product', 'status', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['product', 'rating']),
        ]

    def __str__(self) -> str:
        return f"Review by {self.user} on {self.product.name} ({self.rating}★)"

    def clean(self):
        super().clean()
        if self.rating is not None and not (1 <= self.rating <= 5):
            raise ValidationError({'rating': "Rating score must be an integer between 1 and 5."})

    @transaction.atomic
    def approve(self):
        """
        Approves review for public display and updates product rating summary.
        """
        self.status = ReviewStatus.APPROVED
        self.rejection_reason = ''
        self.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        self.refresh_product_summary()

    @transaction.atomic
    def reject(self, reason: str = ''):
        """
        Rejects review with an optional explanatory reason and updates product rating summary.
        """
        self.status = ReviewStatus.REJECTED
        self.rejection_reason = reason
        self.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        self.refresh_product_summary()

    def update_helpful_counts(self):
        """
        Synchronizes likes_count and dislikes_count based on active ReviewVote records.
        """
        counts = self.votes.aggregate(
            likes=Count('id', filter=Q(vote_type=VoteType.HELPFUL)),
            dislikes=Count('id', filter=Q(vote_type=VoteType.UNHELPFUL)),
        )
        self.likes_count = counts['likes'] or 0
        self.dislikes_count = counts['dislikes'] or 0
        self.save(update_fields=['likes_count', 'dislikes_count'])

    def refresh_product_summary(self):
        """
        Recalculates or creates rating summary for the associated product.
        """
        summary, _ = ProductRatingSummary.objects.get_or_create(product=self.product)
        summary.recalculate()


class ReviewImage(models.Model):
    """
    Photographic evidence or unboxing pictures attached to customer review.
    """

    id = models.BigAutoField(primary_key=True)
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='images',
        help_text="Parent review receiving this photo attachment.",
    )
    image = models.ImageField(
        upload_to='reviews/%Y/%m/',
        help_text="Uploaded product photograph.",
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional caption description for this photo.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when picture was uploaded.",
    )

    class Meta:
        db_table = 'review_images'
        verbose_name = 'Review Image'
        verbose_name_plural = 'Review Images'
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"Image for Review #{self.review_id}"


class ReviewReply(models.Model):
    """
    Official merchant / vendor or administrative response to customer review.
    Enforces a strict 1:1 relationship with parent Review.
    """

    id = models.BigAutoField(primary_key=True)
    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name='reply',
        help_text="Parent review receiving this official response.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_replies',
        help_text="Merchant, support staff, or admin issuing the official response.",
    )
    comment = models.TextField(
        help_text="Official message or explanation from the seller/store.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when reply was published.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when reply was modified.",
    )

    class Meta:
        db_table = 'review_replies'
        verbose_name = 'Review Reply'
        verbose_name_plural = 'Review Replies'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Reply to Review #{self.review_id} by {self.user}"


class ReviewVote(models.Model):
    """
    Individual helpful / unhelpful reaction cast on a review by authenticated user.
    Enforces uniqueness per user-review pair.
    """

    VoteType = VoteType

    id = models.BigAutoField(primary_key=True)
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='votes',
        help_text="Review receiving the helpfulness vote.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_votes',
        help_text="Customer casting the vote.",
    )
    vote_type = models.CharField(
        max_length=15,
        choices=VoteType.choices,
        help_text="Whether voter found the review helpful or unhelpful.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when vote was recorded.",
    )

    class Meta:
        db_table = 'review_votes'
        verbose_name = 'Review Vote'
        verbose_name_plural = 'Review Votes'
        unique_together = ('review', 'user')

    def __str__(self) -> str:
        return f"{self.user} voted {self.vote_type} on Review #{self.review_id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.review.update_helpful_counts()

    def delete(self, *args, **kwargs):
        review = self.review
        super().delete(*args, **kwargs)
        review.update_helpful_counts()


class ProductRatingSummary(models.Model):
    """
    Denormalized rating aggregates cached per product to ensure ultra-fast
    catalog listing queries and product detail page rendering.
    """

    product = models.OneToOneField(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='rating_summary',
        primary_key=True,
        help_text="Product catalog item this summary caches.",
    )
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Calculated arithmetic mean score of all approved reviews.",
    )
    total_reviews = models.PositiveIntegerField(
        default=0,
        help_text="Total count of approved reviews.",
    )
    rating_1_count = models.PositiveIntegerField(
        default=0,
        help_text="Total approved reviews with 1 star.",
    )
    rating_2_count = models.PositiveIntegerField(
        default=0,
        help_text="Total approved reviews with 2 stars.",
    )
    rating_3_count = models.PositiveIntegerField(
        default=0,
        help_text="Total approved reviews with 3 stars.",
    )
    rating_4_count = models.PositiveIntegerField(
        default=0,
        help_text="Total approved reviews with 4 stars.",
    )
    rating_5_count = models.PositiveIntegerField(
        default=0,
        help_text="Total approved reviews with 5 stars.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when summary was last refreshed.",
    )

    class Meta:
        db_table = 'product_rating_summaries'
        verbose_name = 'Product Rating Summary'
        verbose_name_plural = 'Product Rating Summaries'

    def __str__(self) -> str:
        return f"RatingSummary for {self.product.name}: {self.average_rating}★ ({self.total_reviews} reviews)"

    def recalculate(self):
        """
        Recalculates average rating and star counts from approved reviews.
        """
        approved_reviews = Review.objects.filter(
            product=self.product,
            status=ReviewStatus.APPROVED,
        )

        aggregates = approved_reviews.aggregate(
            avg_rating=Avg('rating'),
            total=Count('id'),
            r1=Count('id', filter=Q(rating=1)),
            r2=Count('id', filter=Q(rating=2)),
            r3=Count('id', filter=Q(rating=3)),
            r4=Count('id', filter=Q(rating=4)),
            r5=Count('id', filter=Q(rating=5)),
        )

        avg_val = aggregates['avg_rating']
        self.average_rating = Decimal(str(round(avg_val, 2))) if avg_val is not None else Decimal('0.00')
        self.total_reviews = aggregates['total'] or 0
        self.rating_1_count = aggregates['r1'] or 0
        self.rating_2_count = aggregates['r2'] or 0
        self.rating_3_count = aggregates['r3'] or 0
        self.rating_4_count = aggregates['r4'] or 0
        self.rating_5_count = aggregates['r5'] or 0
        self.save()
