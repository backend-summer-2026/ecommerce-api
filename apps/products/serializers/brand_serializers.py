from rest_framework import serializers
from apps.products.models import Brand


class BrandSerializer(serializers.ModelSerializer):
    """
    Serializer for Brand listing and embedded references.
    """
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = [
            'id',
            'name',
            'slug',
            'logo',
            'description',
            'website',
            'products_count',
        ]

    def get_products_count(self, obj):
        return obj.products.filter(is_active=True).count()


class BrandDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for a single Brand.
    """
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = [
            'id',
            'name',
            'slug',
            'logo',
            'description',
            'website',
            'products_count',
            'created_at',
            'updated_at',
        ]

    def get_products_count(self, obj):
        return obj.products.filter(is_active=True).count()
