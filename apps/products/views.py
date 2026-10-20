from decimal import Decimal
from django.db.models import (
    Count,
    Max,
    Min,
    Q,
)
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.filters import ProductFilter, get_category_and_descendants_ids
from apps.products.models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    Product,
    ProductVariant,
)
from apps.products.pagination import StandardResultsSetPagination
from apps.products.serializers import (
    BrandDetailSerializer,
    BrandSerializer,
    CategoryDetailSerializer,
    CategoryTreeSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductVariantSerializer,
)


class CategoryTreeAPIView(APIView):
    """
    GET /api/v1/catalog/categories/
    Returns full hierarchical category tree starting from top-level root categories.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        root_categories = (
            Category.objects.filter(parent__isnull=True, is_active=True)
            .prefetch_related('children__children')
            .order_by('name')
        )
        serializer = CategoryTreeSerializer(root_categories, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CategoryDetailAPIView(APIView):
    """
    GET /api/v1/catalog/categories/<slug>/
    Returns detailed category information, breadcrumbs, direct children, and product count.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        category = get_object_or_404(
            Category.objects.select_related('parent').prefetch_related('children'),
            slug=slug,
            is_active=True,
        )
        serializer = CategoryDetailSerializer(category, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class BrandListAPIView(APIView):
    """
    GET /api/v1/catalog/brands/
    Returns list of all active brands with product counts and optional search filter (?q=...).
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = Brand.objects.filter(is_active=True)
        q = request.query_params.get('q')
        if q:
            queryset = queryset.filter(name__icontains=q.strip())
        queryset = queryset.order_by('name')
        serializer = BrandSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class BrandDetailAPIView(APIView):
    """
    GET /api/v1/catalog/brands/<slug>/
    Returns detailed information about a specific brand.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        brand = get_object_or_404(Brand, slug=slug, is_active=True)
        serializer = BrandDetailSerializer(brand, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductListAPIView(APIView):
    """
    GET /api/v1/catalog/products/
    Returns a paginated list of active products with extensive filtering:
    - category: category slug (hierarchical)
    - brand: brand slug or comma-separated list
    - min_price / max_price: price range
    - in_stock: true / false
    - q: full-text search across name, description, brand, variant SKU
    - attr_<slug>: dynamic attribute filter (e.g. ?attr_color=black&attr_ram=16gb)
    - ordering: -created_at (default), price, -price, name, -name
    - page, page_size: pagination
    """
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        base_queryset = (
            Product.objects.filter(is_active=True)
            .select_related('brand')
            .prefetch_related(
                'product_categories__category',
                'media',
                'variants__inventory',
                'variants__variant_attributes__attribute_value__attribute',
            )
        )

        filter_backend = ProductFilter(request, base_queryset)
        filtered_queryset = filter_backend.filter_queryset()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(filtered_queryset, request)
        if page is not None:
            serializer = ProductListSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(filtered_queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductDetailAPIView(APIView):
    """
    GET /api/v1/catalog/products/<slug>/
    Returns full product detail page data including all variants, media gallery,
    dynamic attributes matrix, breadcrumbs, and default variant.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        product = get_object_or_404(
            Product.objects.filter(is_active=True)
            .select_related('brand')
            .prefetch_related(
                'product_categories__category__parent',
                'media',
                'variants__inventory',
                'variants__media',
                'variants__variant_attributes__attribute_value__attribute',
            ),
            slug=slug,
        )
        serializer = ProductDetailSerializer(product, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductVariantDetailAPIView(APIView):
    """
    GET /api/v1/catalog/products/<slug>/variants/<sku>/
    Returns specific variant details with real-time stock availability and pricing.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug, sku):
        product = get_object_or_404(Product, slug=slug, is_active=True)
        variant = get_object_or_404(
            ProductVariant.objects.filter(product=product, is_active=True)
            .select_related('inventory')
            .prefetch_related(
                'media',
                'variant_attributes__attribute_value__attribute',
            ),
            sku=sku,
        )
        serializer = ProductVariantSerializer(variant, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CatalogFiltersAPIView(APIView):
    """
    GET /api/v1/catalog/filters/
    Returns dynamic filter options (price range, brands, categories, dynamic attributes)
    available within the entire catalog or filtered by category.
    Optional query params: ?category=<slug>
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        category_slug = request.query_params.get('category')
        product_qs = Product.objects.filter(is_active=True)

        selected_category = None
        if category_slug:
            selected_category = Category.objects.filter(slug=category_slug, is_active=True).first()
            if selected_category:
                cat_ids = get_category_and_descendants_ids(category_slug)
                product_qs = product_qs.filter(product_categories__category_id__in=cat_ids)

        product_ids = product_qs.values_list('id', flat=True)

        # 1. Price boundaries across active variants
        variant_prices = ProductVariant.objects.filter(
            product_id__in=product_ids,
            is_active=True,
        ).aggregate(
            min_price=Min('price'),
            max_price=Max('price'),
            min_discount=Min('discount_price'),
        )

        min_val = variant_prices['min_price'] or Decimal('0.00')
        if variant_prices['min_discount'] is not None and variant_prices['min_discount'] < min_val:
            min_val = variant_prices['min_discount']

        max_val = variant_prices['max_price'] or Decimal('0.00')

        # 2. Available Brands
        brands_data = list(
            Brand.objects.filter(products__id__in=product_ids, is_active=True)
            .annotate(product_count=Count('products', distinct=True))
            .values('id', 'name', 'slug', 'product_count')
            .order_by('name')
        )

        # 3. Available Categories
        if selected_category:
            categories_qs = selected_category.children.filter(is_active=True)
        else:
            categories_qs = Category.objects.filter(parent__isnull=True, is_active=True)

        categories_data = list(
            categories_qs.annotate(
                product_count=Count('products', filter=Q(products__is_active=True), distinct=True)
            )
            .values('id', 'name', 'slug', 'product_count')
            .order_by('name')
        )

        # 4. Dynamic Attributes
        attributes = (
            Attribute.objects.filter(
                values__variant_attributes__variant__product_id__in=product_ids,
                values__variant_attributes__variant__is_active=True,
            )
            .distinct()
            .prefetch_related('values')
        )

        attributes_data = []
        for attr in attributes:
            values_data = list(
                attr.values.filter(
                    variant_attributes__variant__product_id__in=product_ids,
                    variant_attributes__variant__is_active=True,
                )
                .annotate(count=Count('variant_attributes__variant', distinct=True))
                .values('id', 'value', 'slug', 'count')
                .order_by('value')
            )
            if values_data:
                attributes_data.append({
                    'id': attr.id,
                    'name': attr.name,
                    'slug': attr.slug,
                    'values': values_data,
                })

        return Response({
            'price_range': {
                'min': str(min_val),
                'max': str(max_val),
            },
            'brands': brands_data,
            'categories': categories_data,
            'attributes': attributes_data,
        }, status=status.HTTP_200_OK)


class SearchSuggestionAPIView(APIView):
    """
    GET /api/v1/catalog/search/suggest/?q=...
    Instant search suggestions endpoint returning top matching products, categories, and brands.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if len(query) < 2:
            return Response({'products': [], 'categories': [], 'brands': []}, status=status.HTTP_200_OK)

        products = (
            Product.objects.filter(is_active=True)
            .filter(
                Q(name__icontains=query) |
                Q(variants__sku__icontains=query) |
                Q(brand__name__icontains=query)
            )
            .distinct()
            .select_related('brand')
            .prefetch_related('media', 'variants')[:5]
        )

        categories = (
            Category.objects.filter(is_active=True, name__icontains=query)[:3]
        )

        brands = (
            Brand.objects.filter(is_active=True, name__icontains=query)[:3]
        )

        product_data = []
        for p in products:
            media_first = p.media.filter(is_main=True).first() or p.media.first()
            img_url = request.build_absolute_uri(media_first.file.url) if (media_first and media_first.file) else None
            default_v = p.variants.filter(is_active=True, is_default=True).first() or p.variants.filter(is_active=True).first()

            product_data.append({
                'id': p.id,
                'name': p.name,
                'slug': p.slug,
                'image': img_url,
                'price': str(default_v.final_price) if default_v else None,
                'brand': p.brand.name if p.brand else None,
            })

        category_data = [
            {'id': c.id, 'name': c.name, 'slug': c.slug}
            for c in categories
        ]

        brand_data = [
            {
                'id': b.id,
                'name': b.name,
                'slug': b.slug,
                'logo': request.build_absolute_uri(b.logo.url) if b.logo else None,
            }
            for b in brands
        ]

        return Response({
            'products': product_data,
            'categories': category_data,
            'brands': brand_data,
        }, status=status.HTTP_200_OK)


class FeaturedProductsAPIView(APIView):
    """
    GET /api/v1/catalog/featured/
    Returns collections of featured products:
    - new_arrivals: 8 most recently added products
    - on_sale: 8 products with active discounts
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        base_qs = (
            Product.objects.filter(is_active=True)
            .select_related('brand')
            .prefetch_related(
                'product_categories__category',
                'media',
                'variants__inventory',
            )
        )

        new_arrivals = base_qs.order_by('-created_at')[:8]

        on_sale = (
            base_qs.filter(variants__discount_price__isnull=False, variants__is_active=True)
            .distinct()
            .order_by('-created_at')[:8]
        )

        return Response({
            'new_arrivals': ProductListSerializer(new_arrivals, many=True, context={'request': request}).data,
            'on_sale': ProductListSerializer(on_sale, many=True, context={'request': request}).data,
        }, status=status.HTTP_200_OK)
