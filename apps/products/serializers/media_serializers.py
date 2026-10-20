from rest_framework import serializers
from apps.products.models import ProductMedia


class ProductMediaSerializer(serializers.ModelSerializer):
    """
    Serializer for product and variant images/videos.
    """
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductMedia
        fields = [
            'id',
            'file',
            'file_url',
            'alt_text',
            'media_type',
            'is_main',
            'order',
            'variant',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request is not None:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
