from django.contrib import admin

from apps.reviews.models import (
    ProductRatingSummary,
    Review,
    ReviewImage,
    ReviewReply,
    ReviewStatus,
    ReviewVote,
)


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 1
    fields = ('image', 'caption', 'created_at')
    readonly_fields = ('created_at',)


class ReviewReplyInline(admin.StackedInline):
    model = ReviewReply
    extra = 0
    fields = ('user', 'comment', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'product',
        'user',
        'rating',
        'status',
        'is_verified_purchase',
        'likes_count',
        'dislikes_count',
        'created_at',
    )
    list_filter = (
        'status',
        'rating',
        'is_verified_purchase',
        'created_at',
    )
    search_fields = (
        'product__name',
        'user__phone_number',
        'user__email',
        'title',
        'comment',
    )
    readonly_fields = (
        'likes_count',
        'dislikes_count',
        'created_at',
        'updated_at',
    )
    inlines = [ReviewImageInline, ReviewReplyInline]
    actions = ['approve_reviews', 'reject_reviews']

    fieldsets = (
        ('Product & Customer', {
            'fields': ('product', 'user', 'order_item', 'is_verified_purchase')
        }),
        ('Review Content', {
            'fields': ('rating', 'title', 'comment', 'pros', 'cons')
        }),
        ('Moderation', {
            'fields': ('status', 'rejection_reason')
        }),
        ('Helpfulness Metrics', {
            'fields': ('likes_count', 'dislikes_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        for review in queryset:
            review.approve()
        self.message_user(request, f"{queryset.count()} reviews approved successfully.")

    @admin.action(description="Reject selected reviews")
    def reject_reviews(self, request, queryset):
        for review in queryset:
            review.reject(reason="Rejected by administrator.")
        self.message_user(request, f"{queryset.count()} reviews rejected.")


@admin.register(ReviewImage)
class ReviewImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'review', 'image', 'caption', 'created_at')
    list_select_related = ('review',)
    readonly_fields = ('created_at',)


@admin.register(ReviewReply)
class ReviewReplyAdmin(admin.ModelAdmin):
    list_display = ('id', 'review', 'user', 'created_at', 'updated_at')
    list_select_related = ('review', 'user')
    search_fields = ('review__product__name', 'user__phone_number', 'comment')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'review', 'user', 'vote_type', 'created_at')
    list_filter = ('vote_type', 'created_at')
    list_select_related = ('review', 'user')
    readonly_fields = ('created_at',)


@admin.register(ProductRatingSummary)
class ProductRatingSummaryAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'average_rating',
        'total_reviews',
        'rating_1_count',
        'rating_2_count',
        'rating_3_count',
        'rating_4_count',
        'rating_5_count',
        'updated_at',
    )
    readonly_fields = (
        'product',
        'average_rating',
        'total_reviews',
        'rating_1_count',
        'rating_2_count',
        'rating_3_count',
        'rating_4_count',
        'rating_5_count',
        'updated_at',
    )
    actions = ['recalculate_summaries']

    @admin.action(description="Recalculate selected product rating summaries")
    def recalculate_summaries(self, request, queryset):
        for summary in queryset:
            summary.recalculate()
        self.message_user(request, f"{queryset.count()} summaries recalculated.")
