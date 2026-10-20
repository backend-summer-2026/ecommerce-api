# Plan: Product Catalog REST API Implementation

## Metadata
- **Title**: Product Catalog REST API: Categories, Brands, Products, Variants, Dynamic Filters & Search
- **Date**: 2026-10-20
- **Status**: IN_PROGRESS
- **Branch**: `feat/catalog-api`

---

## 1. Context & Motivation

Mahsulotlar katalogi modellar arxitekturasi (`Category`, `Brand`, `Product`, `ProductCategory`, `ProductVariant`, `ProductMedia`, `Attribute`, `AttributeValue`, `ProductVariantAttributeValue`, `Inventory`) to'liq ishlab chiqildi va ma'lumotlar bazasiga migratsiya qilindi. 

Endi ushbu modellar asosida frontend (Next.js/React), mobil ilovalar (iOS/Android) va boshqa mijozlar uchun yuqori unumdorlikka ega, to'liq optimallashgan (N+1 muammosisiz) va xavfsiz **Mahsulotlar Katalogi REST API (`/api/v1/catalog/`)** tizimini qurish zarur.

---

## 2. API Endpoints Specification (`/api/v1/catalog/`)

Katalog moduli quyidagi 10 ta asosiy endpointni o'z ichiga oladi:

| # | Metod | URL | Ruxsat | Tavsif |
|---|:---|:---|:---|:---|
| 1 | `GET` | `/api/v1/catalog/categories/` | Public | Kategoriyalarning to'liq ierarxik (rekursiv daraxt) ro'yxati |
| 2 | `GET` | `/api/v1/catalog/categories/<slug>/` | Public | Kategoriya tafsilotlari, bolalari va breadcrumb yo'li |
| 3 | `GET` | `/api/v1/catalog/brands/` | Public | Faol brendlar ro'yxati (alfavit, qidiruv bilan) |
| 4 | `GET` | `/api/v1/catalog/brands/<slug>/` | Public | Brend tafsilotlari |
| 5 | `GET` | `/api/v1/catalog/products/` | Public | Mahsulotlar listingi (filtrlash, qidiruv, saralash, sahifalash) |
| 6 | `GET` | `/api/v1/catalog/products/<slug>/` | Public | Mahsulot to'liq sahifasi (variantlar, media, atributlar, zaxira) |
| 7 | `GET` | `/api/v1/catalog/products/<slug>/variants/<sku>/` | Public | Aniq bir variant (SKU) narxi va real-vaqt zaxirasi |
| 8 | `GET` | `/api/v1/catalog/filters/` | Public | Berilgan kategoriya/katalog bo'yicha dinamik filtr variantlari |
| 9 | `GET` | `/api/v1/catalog/search/suggest/` | Public | Tezkor qidiruv takliflari (autocomplete: mahsulot, kategoriya, brend) |
| 10 | `GET` | `/api/v1/catalog/featured/` | Public | Tanlangan, ommabop va yangi mahsulotlar to'plamlari |

---

## 3. Architecture & Technical Design

### 3.1. Serializers Architecture (`apps/products/serializers/`)
Kodning tozaligi va modulliligi uchun serializerlar alohida fayllarga ajratiladi:
- `category_serializers.py`:
  - `CategorySimpleSerializer`: Kategoriya haqida qisqa ma'lumot (id, name, slug, icon).
  - `CategoryTreeSerializer`: Rekursiv daraxt strukturasi (`children = CategoryTreeSerializer(many=True)`).
  - `CategoryDetailSerializer`: Ota-ona (parents breadcrumbs), bolalar va mahsulotlar soni.
- `brand_serializers.py`:
  - `BrandSerializer`: id, name, slug, logo, description, website.
- `media_serializers.py`:
  - `ProductMediaSerializer`: id, file, alt_text, media_type, is_main, order.
- `attribute_serializers.py`:
  - `AttributeSerializer` va `AttributeValueSerializer`: Dinamik xususiyatlar (nomi va qiymati).
- `variant_serializers.py`:
  - `ProductVariantSerializer`: SKU, title, price, discount_price, final_price, is_on_sale, is_default, attributes, inventory availability (`is_in_stock`, `available_quantity`).
- `product_serializers.py`:
  - `ProductListSerializer`: Mahsulot ro'yxati kartochkalari uchun yengil va optimallashgan serializer (id, name, slug, brand, primary_category, main_image, price_range, has_variants, is_in_stock).
  - `ProductDetailSerializer`: To'liq mahsulot sahifasi uchun (barcha media fayllar, barcha variantlar, dinamik atributlar matritsasi, to'liq tavsif, breadcrumbs).
  - `CatalogFilterSerializer`: Dinamik filtrlash imkoniyatlari (min/max price, brendlar, mavjud ranglar/o'lchamlar va atributlar).
  - `SearchSuggestionSerializer`: Qidiruv takliflari natijalari.

### 3.2. Query Optimization (N+1 Prevention)
Mahsulotlar katalogida yuzaga kelishi mumkin bo'lgan jiddiy N+1 SQL so'rovlari muammosini oldini olish uchun:
- `Product.objects.filter(is_active=True)` uchun doimo:
  - `.select_related('brand')`
  - `.prefetch_related('product_categories__category', 'media', 'variants__attributes__attribute', 'variants__inventory')`
- Hisoblangan maydonlar (masalan, narxlar diapazoni `min_price`, `max_price`) uchun Django ORM agregatsiyalari (`Min('variants__price')`, `Min('variants__discount_price')`) qo'llaniladi.

### 3.3. Advanced Filtering & Search (`apps/products/filters.py`)
Quyidagi filter parametrlari qo'llab-quvvatlanadi:
- `category`: Kategoriya slug'i (agar kategoriya tanlansa, uning barcha ichki bolalariga tegishli mahsulotlar ham olinadi).
- `brand`: Brend slug'i yoki bir nechta brendlar (`brand=apple,samsung`).
- `min_price` va `max_price`: Narx oralig'i.
- `in_stock`: `true/false` (faqat sotuvda mavjud mahsulotlar).
- `q`: Mahsulot nomi, tavsifi, brendi yoki varianti SKU si bo'yicha qidirish (`icontains` yoki `SearchVector`).
- `ordering`: `-created_at` (yangi), `price` (arzondan qimmatga), `-price` (qimmatdan arzonga), `name`.
- Dinamik atributlar: `attr_<slug>=value` (masalan, `attr_color=black&attr_ram=16gb`).

### 3.4. Pagination (`apps/products/pagination.py`)
- `StandardResultsSetPagination`:
  - `page_size = 20`
  - `page_size_query_param = 'page_size'`
  - `max_page_size = 100`

### 3.5. URL Routing (`apps/products/urls.py` & `config/urls.py`)
- `config/urls.py`: `path('api/v1/catalog/', include('apps.products.urls', namespace='catalog'))`
- `apps/products/urls.py`:
  - `categories/` -> `CategoryTreeAPIView`
  - `categories/<slug>/` -> `CategoryDetailAPIView`
  - `brands/` -> `BrandListAPIView`
  - `brands/<slug>/` -> `BrandDetailAPIView`
  - `products/` -> `ProductListAPIView`
  - `products/<slug>/` -> `ProductDetailAPIView`
  - `products/<slug>/variants/<sku>/` -> `ProductVariantDetailAPIView`
  - `filters/` -> `CatalogFiltersAPIView`
  - `search/suggest/` -> `SearchSuggestionAPIView`
  - `featured/` -> `FeaturedProductsAPIView`

---

## 4. Execution Checklist

- [ ] Step 1: Merge `feat/products-models` into `dev` and create dedicated task branch `feat/catalog-api`
- [ ] Step 2: Implement pagination class in `apps/products/pagination.py`
- [ ] Step 3: Implement modular serializers in `apps/products/serializers/` (`categories`, `brands`, `media`, `variants`, `products`)
- [ ] Step 4: Implement filtering logic in `apps/products/filters.py` with dynamic attribute and category tree support
- [ ] Step 5: Implement API Views in `apps/products/views.py` with eager loading and N+1 query optimization
- [ ] Step 6: Configure URL routes in `apps/products/urls.py` and register in `config/urls.py` under `/api/v1/catalog/`
- [ ] Step 7: Write comprehensive API unit and integration tests in `apps/products/tests/test_catalog_api.py`
- [ ] Step 8: Run Django checks and verify test suite passes (`python manage.py test apps.products`)
- [ ] Step 9: Update master Postman collection in `postman/ecommerce_api_collection.json` with all catalog endpoints, parameters, and sample responses
- [ ] Step 10: Final verification, update plan status to `COMPLETED`, and prepare git commit according to guidelines
