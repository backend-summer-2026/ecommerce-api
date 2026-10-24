from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.models import Product
from apps.reviews.models import (
    ProductRatingSummary,
    Review,
    ReviewImage,
    ReviewReply,
    ReviewStatus,
    ReviewVote,
    VoteType,
)
from apps.reviews.pagination import ReviewPagination
from apps.reviews.permissions import IsAdminOrStaffUser, IsReviewOwnerOrReadOnly
from apps.reviews.serializers import (
    ProductRatingSummarySerializer,
    ReviewCreateUpdateSerializer,
    ReviewDetailSerializer,
    ReviewImageSerializer,
    ReviewListSerializer,
    ReviewModerationSerializer,
    ReviewReplySerializer,
    ReviewVoteSerializer,
)


class ProductRatingSummaryView(generics.RetrieveAPIView):
    """
    GET /api/v1/reviews/products/<product_id>/summary/
    Retrieves aggregated rating summary and star breakdown for a product.
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = ProductRatingSummarySerializer

    def get_object(self):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, id=product_id)
        summary, _ = ProductRatingSummary.objects.get_or_create(product=product)
        return summary


class ProductReviewListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/reviews/products/<product_id>/
    Lists approved reviews for a given product with filters, sorting, and pagination.

    POST /api/v1/reviews/products/<product_id>/
    Submits a new customer review for the product.
    """

    pagination_class = ReviewPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ReviewCreateUpdateSerializer
        return ReviewListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        product_id = self.kwargs.get('product_id')
        context['product'] = get_object_or_404(Product, id=product_id)
        return context

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        get_object_or_404(Product, id=product_id)

        queryset = (
            Review.objects.filter(product_id=product_id, status=ReviewStatus.APPROVED)
            .select_related('user', 'product', 'reply', 'reply__user')
            .prefetch_related('images', 'votes')
        )

        rating_param = self.request.query_params.get('rating')
        if rating_param and rating_param.isdigit():
            queryset = queryset.filter(rating=int(rating_param))

        verified_param = self.request.query_params.get('verified_only')
        if verified_param and verified_param.lower() in ('true', '1'):
            queryset = queryset.filter(is_verified_purchase=True)

        photos_param = self.request.query_params.get('has_images')
        if photos_param and photos_param.lower() in ('true', '1'):
            queryset = queryset.filter(images__isnull=False).distinct()

        ordering = self.request.query_params.get('ordering', '-created_at')
        allowed_orderings = {
            '-created_at': '-created_at',
            'created_at': 'created_at',
            '-likes_count': '-likes_count',
            '-rating': '-rating',
            'rating': 'rating',
        }
        queryset = queryset.order_by(allowed_orderings.get(ordering, '-created_at'))
        return queryset

    def perform_create(self, serializer):
        serializer.save()


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET /api/v1/reviews/<id>/
    Retrieves full details of a specific review.

    PATCH / PUT /api/v1/reviews/<id>/
    Updates an authored review. Sets status back to PENDING for re-moderation.

    DELETE /api/v1/reviews/<id>/
    Deletes the review. Accessible only to author or administrative staff.
    """

    permission_classes = [IsReviewOwnerOrReadOnly]
    lookup_field = 'id'
    queryset = (
        Review.objects.select_related('user', 'product', 'reply', 'reply__user')
        .prefetch_related('images', 'votes')
        .all()
    )

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ReviewCreateUpdateSerializer
        return ReviewDetailSerializer


class ReviewImageUploadView(APIView):
    """
    POST /api/v1/reviews/<id>/images/
    Uploads a photograph attachment to an existing review.
    Accessible only to the review author or staff.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, id):
        review = get_object_or_404(Review, id=id)

        if not (request.user.is_staff or review.user == request.user):
            raise PermissionDenied("You can only upload images to your own reviews.")

        if 'image' not in request.FILES:
            raise ValidationError({'image': 'Image file is required.'})

        image_file = request.FILES['image']
        caption = request.data.get('caption', '')

        image_obj = ReviewImage.objects.create(
            review=review,
            image=image_file,
            caption=caption,
        )

        serializer = ReviewImageSerializer(image_obj, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ReviewImageDeleteView(generics.DestroyAPIView):
    """
    DELETE /api/v1/reviews/images/<image_id>/
    Deletes an uploaded photo attachment. Accessible to review owner or staff.
    """

    permission_classes = [permissions.IsAuthenticated]
    queryset = ReviewImage.objects.select_related('review').all()
    lookup_field = 'id'
    lookup_url_kwarg = 'image_id'

    def perform_destroy(self, instance):
        if not (self.request.user.is_staff or instance.review.user == self.request.user):
            raise PermissionDenied("You can only delete images from your own reviews.")
        instance.delete()


class ReviewVoteView(APIView):
    """
    POST /api/v1/reviews/<id>/vote/
    Casts a HELPFUL or UNHELPFUL vote on a review.
    Toggles/removes the vote if the user clicks the same vote type again.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        review = get_object_or_404(Review, id=id)

        serializer = ReviewVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vote_type = serializer.validated_data['vote_type']

        existing_vote = ReviewVote.objects.filter(review=review, user=request.user).first()

        if existing_vote:
            if existing_vote.vote_type == vote_type:
                existing_vote.delete()
                current_vote = None
                action = 'removed'
            else:
                existing_vote.vote_type = vote_type
                existing_vote.save()
                current_vote = vote_type
                action = 'updated'
        else:
            ReviewVote.objects.create(
                review=review,
                user=request.user,
                vote_type=vote_type,
            )
            current_vote = vote_type
            action = 'created'

        review.refresh_from_db()
        return Response(
            {
                'action': action,
                'vote_type': current_vote,
                'likes_count': review.likes_count,
                'dislikes_count': review.dislikes_count,
            },
            status=status.HTTP_200_OK,
        )


class ReviewReplyView(APIView):
    """
    POST /api/v1/reviews/<id>/reply/
    Allows seller/staff to publish or update an official response to a review.
    """

    permission_classes = [IsAdminOrStaffUser]

    def post(self, request, id):
        review = get_object_or_404(Review, id=id)

        comment = request.data.get('comment', '').strip()
        if not comment:
            raise ValidationError({'comment': 'Official reply comment cannot be empty.'})

        reply, _ = ReviewReply.objects.update_or_create(
            review=review,
            defaults={
                'user': request.user,
                'comment': comment,
            },
        )

        serializer = ReviewReplySerializer(reply, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminReviewModerationListView(generics.ListAPIView):
    """
    GET /api/v1/reviews/admin/moderation/
    Lists reviews pending moderation or filtered by status for staff review.
    """

    permission_classes = [IsAdminOrStaffUser]
    pagination_class = ReviewPagination
    serializer_class = ReviewDetailSerializer

    def get_queryset(self):
        queryset = (
            Review.objects.select_related('user', 'product', 'reply', 'reply__user')
            .prefetch_related('images', 'votes')
            .order_by('-created_at')
        )

        status_param = self.request.query_params.get('status', ReviewStatus.PENDING)
        if status_param in ReviewStatus.values:
            queryset = queryset.filter(status=status_param)

        return queryset


class AdminReviewModerateView(APIView):
    """
    POST /api/v1/reviews/admin/<id>/moderate/
    Moderation action to APPROVE or REJECT a review.
    """

    permission_classes = [IsAdminOrStaffUser]

    def post(self, request, id):
        review = get_object_or_404(Review, id=id)

        serializer = ReviewModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        rejection_reason = serializer.validated_data.get('rejection_reason', '')

        if new_status == ReviewStatus.APPROVED:
            review.approve()
        else:
            review.reject(reason=rejection_reason)

        detail_serializer = ReviewDetailSerializer(review, context={'request': request})
        return Response(detail_serializer.data, status=status.HTTP_200_OK)
