from django.urls import path

from apps.reviews.views import (
    AdminReviewModerateView,
    AdminReviewModerationListView,
    ProductRatingSummaryView,
    ProductReviewListCreateView,
    ReviewDetailView,
    ReviewImageDeleteView,
    ReviewImageUploadView,
    ReviewReplyView,
    ReviewVoteView,
)

app_name = 'reviews'

urlpatterns = [
    # Public & Customer endpoints
    path(
        'products/<int:product_id>/summary/',
        ProductRatingSummaryView.as_view(),
        name='product-rating-summary',
    ),
    path(
        'products/<int:product_id>/',
        ProductReviewListCreateView.as_view(),
        name='product-reviews-list-create',
    ),
    path(
        '<int:id>/',
        ReviewDetailView.as_view(),
        name='review-detail',
    ),
    path(
        '<int:id>/images/',
        ReviewImageUploadView.as_view(),
        name='review-image-upload',
    ),
    path(
        'images/<int:image_id>/',
        ReviewImageDeleteView.as_view(),
        name='review-image-delete',
    ),
    path(
        '<int:id>/vote/',
        ReviewVoteView.as_view(),
        name='review-vote',
    ),
    path(
        '<int:id>/reply/',
        ReviewReplyView.as_view(),
        name='review-reply',
    ),

    # Staff / Admin moderation endpoints
    path(
        'admin/moderation/',
        AdminReviewModerationListView.as_view(),
        name='admin-review-moderation-list',
    ),
    path(
        'admin/<int:id>/moderate/',
        AdminReviewModerateView.as_view(),
        name='admin-review-moderate',
    ),
]
