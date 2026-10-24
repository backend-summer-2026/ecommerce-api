from rest_framework import serializers

from apps.reviews.models import ProductRatingSummary


class ProductRatingSummarySerializer(serializers.ModelSerializer):
    """
    Serializer for product rating metrics and star distributions.
    """

    class Meta:
        model = ProductRatingSummary
        fields = [
            'product',
            'average_rating',
            'total_reviews',
            'rating_1_count',
            'rating_2_count',
            'rating_3_count',
            'rating_4_count',
            'rating_5_count',
            'updated_at',
        ]
        read_only_fields = fields
