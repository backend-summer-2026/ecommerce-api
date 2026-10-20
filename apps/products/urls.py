from django.urls import path
from apps.products.views import (
    BrandDetailAPIView,
    BrandListAPIView,
    CatalogFiltersAPIView,
    CategoryDetailAPIView,
    CategoryTreeAPIView,
    FeaturedProductsAPIView,
    ProductDetailAPIView,
    ProductListAPIView,
    ProductVariantDetailAPIView,
    SearchSuggestionAPIView,
)

app_name = 'catalog'

urlpatterns = [
    # Categories
    path('categories/', CategoryTreeAPIView.as_view(), name='category-tree'),
    path('categories/<slug:slug>/', CategoryDetailAPIView.as_view(), name='category-detail'),

    # Brands
    path('brands/', BrandListAPIView.as_view(), name='brand-list'),
    path('brands/<slug:slug>/', BrandDetailAPIView.as_view(), name='brand-detail'),

    # Products Listing, Filtering & Detail
    path('products/', ProductListAPIView.as_view(), name='product-list'),
    path('products/<slug:slug>/', ProductDetailAPIView.as_view(), name='product-detail'),
    path('products/<slug:slug>/variants/<str:sku>/', ProductVariantDetailAPIView.as_view(), name='product-variant-detail'),

    # Faceted Filters, Suggestions & Featured
    path('filters/', CatalogFiltersAPIView.as_view(), name='catalog-filters'),
    path('search/suggest/', SearchSuggestionAPIView.as_view(), name='search-suggest'),
    path('featured/', FeaturedProductsAPIView.as_view(), name='featured-products'),
]
