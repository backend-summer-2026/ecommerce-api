from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.orders.models import Order, OrderItem
from apps.products.models import Product
from apps.reviews.models import Review, ReviewStatus, ReviewVote
from apps.reviews.serializers.image_serializers import ReviewImageSerializer
from apps.reviews.serializers.reply_serializers import ReviewReplySerializer

User = get_user_model()


class ReviewUserPublicSerializer(serializers.ModelSerializer):
    """
    Publicly safe customer representation on reviews.
    Displays first name or partial initials without exposing sensitive contact details.
    """

    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'display_name']

    def get_display_name(self, obj) -> str:
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name[0]}."
        if obj.first_name:
            return obj.first_name
        email_parts = obj.email.split('@')
        if len(email_parts) == 2 and len(email_parts[0]) > 2:
            return f"{email_parts[0][:2]}***@{email_parts[1]}"
        return "Customer"


class ReviewListSerializer(serializers.ModelSerializer):
    """
    Public listing serializer for approved product reviews.
    Includes user public details, attached photos, official replies, and helpful counts.
    """

    user = ReviewUserPublicSerializer(read_only=True)
    images = ReviewImageSerializer(many=True, read_only=True)
    reply = ReviewReplySerializer(read_only=True)
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'id',
            'product',
            'user',
            'rating',
            'title',
            'comment',
            'pros',
            'cons',
            'is_verified_purchase',
            'likes_count',
            'dislikes_count',
            'images',
            'reply',
            'user_vote',
            'created_at',
        ]

    def get_user_vote(self, obj) -> str | None:
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            vote = obj.votes.filter(user=request.user).first()
            return vote.vote_type if vote else None
        return None


class ReviewDetailSerializer(ReviewListSerializer):
    """
    Comprehensive single-review detail view.
    Exposes moderation status and rejection reason to review author and staff.
    """

    rejection_reason = serializers.SerializerMethodField()

    class Meta(ReviewListSerializer.Meta):
        fields = ReviewListSerializer.Meta.fields + [
            'status',
            'rejection_reason',
            'order_item',
            'updated_at',
        ]

    def get_rejection_reason(self, obj) -> str:
        request = self.context.get('request')
        if request and request.user and (request.user.is_staff or request.user == obj.user):
            return obj.rejection_reason
        return ''


class ReviewCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating customer reviews.
    Automatically identifies verified purchase from order history and
    defaults new or edited reviews to PENDING moderation status.
    """

    class Meta:
        model = Review
        fields = [
            'id',
            'rating',
            'title',
            'comment',
            'pros',
            'cons',
            'status',
            'is_verified_purchase',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'status',
            'is_verified_purchase',
            'created_at',
            'updated_at',
        ]

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating score must be between 1 and 5.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        product = self.context.get('product')

        if not self.instance and product:
            if Review.objects.filter(user=user, product=product).exists():
                raise serializers.ValidationError(
                    {"detail": "You have already submitted a review for this product."}
                )

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data.pop('product', self.context.get('product'))

        purchased_item = OrderItem.objects.filter(
            order__user=user,
            order__status__in=[
                Order.OrderStatus.CONFIRMED,
                Order.OrderStatus.PROCESSING,
                Order.OrderStatus.SHIPPED,
                Order.OrderStatus.DELIVERED,
            ],
            variant__product=product,
        ).first()

        review = Review.objects.create(
            user=user,
            product=product,
            order_item=purchased_item,
            is_verified_purchase=bool(purchased_item),
            status=ReviewStatus.PENDING,
            **validated_data,
        )
        return review

    def update(self, instance, validated_data):
        instance.status = ReviewStatus.PENDING
        instance.rejection_reason = ''
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ReviewModerationSerializer(serializers.Serializer):
    """
    Serializer for admin/staff moderation action (APPROVE or REJECT).
    """

    status = serializers.ChoiceField(
        choices=[ReviewStatus.APPROVED, ReviewStatus.REJECTED],
    )
    rejection_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
    )

    def validate(self, attrs):
        if attrs.get('status') == ReviewStatus.REJECTED and not attrs.get('rejection_reason'):
            raise serializers.ValidationError(
                {"rejection_reason": "Rejection reason is required when rejecting a review."}
            )
        return attrs
