from rest_framework import serializers
from apps.products.models import Category


class CategorySimpleSerializer(serializers.ModelSerializer):
    """
    Lightweight representation of a Category.
    """
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'image']


class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Recursive category tree serializer showing active parent and children hierarchy.
    """
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'image', 'children']

    def get_children(self, obj):
        active_children = obj.children.filter(is_active=True).order_by('name')
        return CategoryTreeSerializer(active_children, many=True, context=self.context).data


class CategoryBreadcrumbSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class CategoryDetailSerializer(serializers.ModelSerializer):
    """
    Detailed category representation including breadcrumb chain and direct active subcategories.
    """
    parent = CategoryBreadcrumbSerializer(read_only=True)
    breadcrumbs = serializers.SerializerMethodField()
    children = CategorySimpleSerializer(many=True, read_only=True)
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'icon',
            'image',
            'description',
            'parent',
            'breadcrumbs',
            'children',
            'products_count',
        ]

    def get_breadcrumbs(self, obj):
        breadcrumbs = []
        current = obj.parent
        while current is not None:
            breadcrumbs.append({
                'id': current.id,
                'name': current.name,
                'slug': current.slug,
            })
            current = current.parent
        breadcrumbs.reverse()
        return breadcrumbs

    def get_products_count(self, obj):
        # Count all active products directly or indirectly associated with this category
        return obj.products.filter(is_active=True).distinct().count()
