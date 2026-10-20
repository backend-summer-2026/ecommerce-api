from decimal import Decimal
from django.db.models import (
    Case,
    DecimalField,
    F,
    Min,
    Max,
    Q,
    QuerySet,
    When,
)
from apps.products.models import Category, Product


def get_category_and_descendants_ids(category_slug: str) -> list[int]:
    """
    Returns the IDs of the category with the given slug and all its recursive children.
    """
    try:
        root_cat = Category.objects.get(slug=category_slug, is_active=True)
    except Category.DoesNotExist:
        return []

    category_ids = [root_cat.id]
    current_ids = [root_cat.id]

    while current_ids:
        children_ids = list(
            Category.objects.filter(parent_id__in=current_ids, is_active=True)
            .values_list('id', flat=True)
        )
        if not children_ids:
            break
        category_ids.extend(children_ids)
        current_ids = children_ids

    return category_ids


class ProductFilter:
    """
    Filter service for the Product catalog queryset.
    Applies category hierarchy, brand, price range, stock, search, dynamic attributes, and sorting.
    """

    def __init__(self, request, queryset: QuerySet[Product]):
        self.request = request
        self.queryset = queryset

    def filter_queryset(self) -> QuerySet[Product]:
        qs = self.queryset
        params = self.request.query_params

        # 1. Category filter (hierarchical)
        category_slug = params.get('category')
        if category_slug:
            cat_ids = get_category_and_descendants_ids(category_slug)
            if cat_ids:
                qs = qs.filter(product_categories__category_id__in=cat_ids)
            else:
                return qs.none()

        # 2. Brand filter (supports comma-separated slugs e.g. ?brand=apple,samsung)
        brand_param = params.get('brand')
        if brand_param:
            brand_slugs = [b.strip() for b in brand_param.split(',') if b.strip()]
            if brand_slugs:
                qs = qs.filter(brand__slug__in=brand_slugs)

        # 3. Text search (?q=...)
        q = params.get('q')
        if q:
            search_query = q.strip()
            qs = qs.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(short_description__icontains=search_query) |
                Q(brand__name__icontains=search_query) |
                Q(variants__sku__icontains=search_query) |
                Q(variants__title__icontains=search_query)
            )

        # 4. In Stock filter (?in_stock=true/false)
        in_stock_param = params.get('in_stock')
        if in_stock_param is not None:
            if in_stock_param.lower() in ('true', '1', 'yes'):
                qs = qs.filter(
                    variants__is_active=True,
                    variants__inventory__quantity__gt=F('variants__inventory__reserved_quantity')
                )
            elif in_stock_param.lower() in ('false', '0', 'no'):
                # Products where no variant has available inventory
                qs = qs.exclude(
                    variants__is_active=True,
                    variants__inventory__quantity__gt=F('variants__inventory__reserved_quantity')
                )

        # 5. Price range filter (?min_price=100 & ?max_price=500)
        # Using effective price (discount_price if present else price)
        min_price = params.get('min_price')
        if min_price:
            try:
                min_p = Decimal(min_price)
                qs = qs.filter(
                    Q(variants__discount_price__isnull=False, variants__discount_price__gte=min_p) |
                    Q(variants__discount_price__isnull=True, variants__price__gte=min_p),
                    variants__is_active=True,
                )
            except (ValueError, TypeError):
                pass

        max_price = params.get('max_price')
        if max_price:
            try:
                max_p = Decimal(max_price)
                qs = qs.filter(
                    Q(variants__discount_price__isnull=False, variants__discount_price__lte=max_p) |
                    Q(variants__discount_price__isnull=True, variants__price__lte=max_p),
                    variants__is_active=True,
                )
            except (ValueError, TypeError):
                pass

        # 6. Dynamic Attributes filter (params starting with `attr_<attribute_slug>=<value_slug>`)
        # Example: ?attr_color=black&attr_ram=16gb
        for param_key, param_value in params.items():
            if param_key.startswith('attr_') and param_value:
                attr_slug = param_key[5:].strip()
                values = [v.strip() for v in param_value.split(',') if v.strip()]
                if attr_slug and values:
                    qs = qs.filter(
                        variants__variant_attributes__attribute_value__attribute__slug=attr_slug,
                        variants__variant_attributes__attribute_value__slug__in=values,
                        variants__is_active=True,
                    )

        # 7. Ordering
        ordering = params.get('ordering', '-created_at')
        valid_orderings = {
            '-created_at': '-created_at',
            'created_at': 'created_at',
            'name': 'name',
            '-name': '-name',
        }

        # Annotate effective price for price sorting
        qs = qs.annotate(
            effective_min_price=Min(
                Case(
                    When(variants__discount_price__isnull=False, then=F('variants__discount_price')),
                    default=F('variants__price'),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
        )

        if ordering == 'price':
            qs = qs.order_by('effective_min_price', 'id')
        elif ordering == '-price':
            qs = qs.order_by('-effective_min_price', 'id')
        elif ordering in valid_orderings:
            qs = qs.order_by(valid_orderings[ordering], 'id')
        else:
            qs = qs.order_by('-created_at', 'id')

        return qs.distinct()
