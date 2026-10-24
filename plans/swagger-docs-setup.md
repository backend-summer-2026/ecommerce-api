# Plan: OpenAPI 3.0 & Swagger UI Documentation Integration (`drf-spectacular`)

## Metadata
- **Title**: OpenAPI 3.0 & Swagger UI / Redoc Interactive API Documentation Setup
- **Date**: 2026-10-24
- **Status**: COMPLETED
- **Completed**: 2026-10-24
- **Branch**: `feat/swagger-docs`
- **Author**: Antigravity

---

## 1. Context & Motivation

Ushbu ecommerce loyihasi keng ko'lamli REST API tizimiga ega bo'lib, quyidagi modullarni o'z ichiga oladi:
- `apps.users` (`/api/v1/auth/`): Foydalanuvchilar, ro'yxatdan o'tish, telefon orqali OTP tasdiqlash, JWT token olish va yangilash, profil boshqaruvi;
- `apps.products` (`/api/v1/catalog/`): Mahsulotlar katalogi, kategoriyalar, brendlar, xususiyatlar, variantlar va media;
- `apps.carts` (`/api/v1/cart/`): Savatcha yaratish, mahsulot qo'shish, miqdorini o'zgartirish va tozalash;
- `apps.orders` (`/api/v1/orders/`): Buyurtma berish, kuponlar, manzil kiritish, buyurtma statuslari tarixi;
- `apps.payments` (`/api/v1/payments/`): Payme, Click, Uzum to'lov tizimlari, to'lov yaratish, qaytarishlar (refunds) va webhooklar;
- `apps.notifications` (`/api/v1/notifications/`): Foydalanuvchi bildirishnomalari, email xabarlari va sozlamalari;
- `apps.reviews` (`/api/v1/reviews/`): Mahsulot sharhlari, reytinglar, rasm yuklash, foydali deb ovoz berish, sotuvchi javoblari va admin moderatsiyasi;
- `apps.dashboard` (`/api/v1/dashboard/`): Administratorlar va menejerlar uchun KPI metrikalari, audit jurnali, ogohlantirishlar va analitika.

Frontend dasturchilar, mobil ilova yaratuvchilari hamda tashqi integratsiyalar uchun barcha endpointlar, parametrlar, so'rov va javob formatlarini qulay ko'rinishda taqdim etuvchi interaktiv hujjatlashtirish tizimi (Swagger / OpenAPI 3.0) talab etiladi.

### Nega `drf-spectacular` tanlandi?
1. **OpenAPI 3.0 / 3.1 standarti**: Zamonaviy spetsifikatsiya bo'lib, eski `drf-yasg` (Swagger 2.0) ga qaraganda boyroq imkoniyatlarga ega.
2. **Django 5 va DRF bilan to'liq mos**: `drf-yasg` Django 5 da eskirgan xatoliklarga ega bo'lsa, `drf-spectacular` hozirgi kunda DRF rasmiy tavsiyasidir.
3. **JWT Autentifikatsiya integratsiyasi**: Swagger UI oynasida "Authorize" tugmasi orqali `Bearer <token>` kiritib, barcha himoyalangan API-larni brauzer orqali sinab ko'rish (Try it out) imkonini beradi.
4. **Ikkala vizualizatsiyani qo'llab-quvvatlaydi**: Swagger UI (interaktiv test qilish uchun) va Redoc (toza va o'qishga qulay hujjat ko'rinishi).

---

## 2. Architecture & Technical Design

### 2.1. Paketlar
- `drf-spectacular` kutubxonasini `uv add drf-spectacular` orqali `pyproject.toml` ga qo'shish.

### 2.2. Sozlamalar (`config/settings.py`)
1. `INSTALLED_APPS` ro'yxatiga `'drf_spectacular'` ni qo'shish.
2. `REST_FRAMEWORK` lug'atiga `'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema'` parametrini kiritish.
3. `SPECTACULAR_SETTINGS` konfiguratsiyasini belgilash:
   - Sarlavha: `Ecommerce Platform REST API`
   - Versiya: `1.0.0`
   - Tavsif: Do'kon katalogi, savatcha, buyurtmalar, to'lovlar, sharhlar, bildirishnomalar va boshqaruv paneli API hujjatlari.
   - Autentifikatsiya sxemasi: `BearerAuth` (`type: http`, `scheme: bearer`, `bearerFormat: JWT`).
   - Teglar (Tags) va guruhlash: `Auth`, `Catalog`, `Cart`, `Orders`, `Payments`, `Notifications`, `Reviews`, `Dashboard`.

### 2.3. URL Marshrutlari (`config/urls.py`)
- `/api/schema/` -> `SpectacularAPIView` (OpenAPI 3.0 sxemasi, JSON yoki YAML)
- `/api/docs/swagger/` -> `SpectacularSwaggerView` (Swagger UI interaktiv oynasi)
- `/api/docs/redoc/` -> `SpectacularRedocView` (Redoc toza dokumentatsiya interfeysi)

### 2.4. Avtomatlashtirilgan Testlar
- Sxema generatsiyasini tekshirish: `python manage.py spectacular --file /dev/null --validate`
- View-lar uchun test suite: `config/tests/test_swagger_docs.py` (yoki `tests/test_swagger.py`), unda:
  - `/api/schema/` status kodi 200 va OpenAPI versiyasi 3.0.x ekanligi;
  - `/api/docs/swagger/` status kodi 200 va Swagger UI yuklanishi;
  - `/api/docs/redoc/` status kodi 200 va Redoc UI yuklanishi tekshiriladi.

### 2.5. Postman Master To'plami Integratsiyasi
- `postman/ecommerce_api_collection.json` ichidagi yangi "API Documentation" papkasiga ushbu endpointlar (Schema, Swagger UI, Redoc) kiritiladi.

---

## 3. Detailed Checklist

- [x] Step 1: `feat/swagger-docs` branchini yaratish va holatni tekshirish
- [x] Step 2: `uv add drf-spectacular` orqali kutubxonani o'rnatish va `pyproject.toml` ga kiritish
- [x] Step 3: `config/settings.py` da `INSTALLED_APPS`, `REST_FRAMEWORK`, va `SPECTACULAR_SETTINGS` ni sozlash
- [x] Step 4: `config/urls.py` ga `/api/schema/`, `/api/docs/swagger/`, `/api/docs/redoc/` marshrutlarini ulash
- [x] Step 5: `python manage.py spectacular --validate` buyrug'i orqali sxemani generatsiya qilish va validatsiyadan o'tkazish
- [x] Step 6: Swagger hujjatlashtirish uchun avtomatlashtirilgan test yozish (`config/tests/test_swagger.py`)
- [x] Step 7: Barcha unit va integratsion testlarni ishga tushirish (`python manage.py test`)
- [x] Step 8: `postman/ecommerce_api_collection.json` master to'plamiga API Documentation endpointlarini qo'shish
- [x] Step 9: Reja faylidagi barcha bosqichlarni `[x]` qilib belgilash va o'zgarishlarni commit qilish
