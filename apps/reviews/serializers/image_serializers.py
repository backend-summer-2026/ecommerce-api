from rest_framework import serializers

from apps.reviews.models import ReviewImage


class ReviewImageSerializer(serializers.ModelSerializer):
    """
    Serializer for uploading and displaying photographic evidence attached to reviews.
    """

    class Meta:
        model = ReviewImage
        fields = [
            'id',
            'review',
            'image',
            'caption',
            'created_at',
        ]
        read_only_fields = ['id', 'review', 'created_at']
