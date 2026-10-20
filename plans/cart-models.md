# Plan: Shopping Cart Data Models Architecture (`apps/carts`)

## Metadata
- **Title**: Shopping Cart Data Models: Cart, CartItem, Guest/User Sessions, Inventory Validation & Price Tracking
- **Date**: 2026-10-20
- **Status**: COMPLETED
- **Branch**: `feat/carts-models`

---

## 1. Context & Motivation

Mahsulotlar katalogi modellar tizimi (`apps/products/models.py`) to'liq ishlab chiqilgan bo'lib, unda mahsulotlar (`Product`), aniq xarid qilinadigan modifikatsiyalar/SKUlar (`ProductVariant`), dinamik atributlar (`Attribute`, `AttributeValue`), narxlar (`price`, `discount_price`, `final_price`) va real-vaqt ombor zaxiralari (`Inventory`: `quantity`, `reserved_quantity`, `available_quantity`) mavjud.

E-commerce platformasida xarid jarayonining navbatdagi muhim bo'g'ini bu **Shopping Cart (Savat)** tizimidir. Haqiqiy va yuqori yuklamali e-commerce tizimlarida savat arxitekturasi quyidagi qat'iy talablarga javob berishi kerak:

1. **Variant-Darajasidagi Bog'liqlik (`ProductVariant`)**:
   Foydalanuvchi umumiy mahsulotni (`Product`) emas, balki uning aniq variantini (`ProductVariant`: ma'lum rang, o'lcham, xotira hajmiga ega SKU) savatga qo'shadi. Chunki narx, chegirma va ombordagi qoldiq aynan `ProductVariant` darajasida aniqlanadi.

2. **Gibrid Foydalanuvchi Qo'llab-quvvatlovi (Authenticated & Guest Shoppers)**:
   - Ro'yxatdan o'tgan foydalanuvchilar (`User`) o'z akkauntlariga bog'langan doimiy savatga ega bo'lishi kerak.
   - Saytga birinchi marta kirgan mehmonlar (Guest / Anonymous) ham to'g'ridan-to'g'ri mahsulotlarni savatga qo'sha olishi kerak (`session_key` yoki `uuid/token` orqali).
   - Mehmon foydalanuvchi tizimga kirganida (Login / Register), uning mehmon savati avtomatik ravishda uning asosiy foydalanuvchi savatiga birlashtirilishi (**Cart Merge**) kerak.

3. **Savat Hayot Tsikli (Lifecycle & Status Management)**:
   Savatlar holati (`OPEN`, `MERGED`, `CONVERTED`, `ABANDONED`) bo'yicha boshqarilishi, har bir foydalanuvchida bir vaqtning o'zida faqat 1 ta faol (`OPEN`) savat bo'lishi ma'lumotlar bazasi darajasida kafolatlanishi zarur.

4. **Haqiqiy Vaqtdagi Zaxira va Narx Tekshiruvi**:
   Savatdagi mahsulot miqdori ombordagi erkin qoldiqdan (`variant.inventory.available_quantity`) oshib ketmasligi, narxlar real vaqtda `variant.final_price` orqali hisoblanishi, shu bilan birga mahsulot savatga qo'shilgan paytdagi narx (`unit_price_at_addition`) saqlanib, narx o'zgarganda foydalanuvchiga bildirishnoma berish imkoniyati bo'lishi kerak.

---

## 2. Architecture & Technical Design

### 2.1. Entity-Relationship Diagram

```mermaid
erDiagram
    User ||--o{ Cart : "owns (at most 1 active)"
    Cart ||--o{ CartItem : "contains"
    ProductVariant ||--o{ CartItem : "selected variant"
    Product ||--o{ ProductVariant : "has"
    ProductVariant ||--|| Inventory : "stock tracking"

    Cart {
        uuid id PK "UUID"
        fk user FK "nullable"
        string session_key "nullable, indexed"
        string status "OPEN / MERGED / CONVERTED / ABANDONED"
        datetime created_at
        datetime updated_at
    }

    CartItem {
        bigint id PK
        fk cart FK "Cart"
        fk variant FK "ProductVariant"
        int quantity "min 1"
        decimal unit_price_at_addition "Snapshot of final_price"
        datetime created_at
        datetime updated_at
    }
```

---

### 2.2. Models Specification (`apps/carts/models.py`)

#### A. `Cart` Model (`db_table = 'carts'`)

Har bir mijozning (avtorizatsiyadan o'tgan yoki mehmon) savat sessiyasini ifodalaydi.

- **Maydonlar**:
  - `id`: `models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` — xavfsiz, taxmin qilib bo'lmaydigan tashqi identifikator (API va frontend uchun juda qulay).
  - `user`: `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='carts', db_index=True)` — savat egasi.
  - `session_key`: `models.CharField(max_length=255, null=True, blank=True, db_index=True)` — anonim mehmonlar sessiyasi kaliti.
  - `status`: `models.CharField(max_length=20, choices=CartStatus.choices, default=CartStatus.OPEN, db_index=True)`
    - `OPEN`: Faol savat (mahsulot qo'shish, o'chirish, tahrirlash mumkin).
    - `MERGED`: Mehmon savati foydalanuvchi savatiga birlashtirilgan va yopilgan.
    - `CONVERTED`: Savat buyurtmaga (`Order`) aylantirilgan.
    - `ABANDONED`: Belgilangan vaqt ichida xarid qilinmagan va tashlab ketilgan.
  - `created_at`: `models.DateTimeField(auto_now_add=True)`
  - `updated_at`: `models.DateTimeField(auto_now=True)`

- **Cheklovlar va Indekslar (Meta)**:
  - `UniqueConstraint(fields=['user'], condition=Q(status='OPEN'), name='unique_active_user_cart')`: Har bir foydalanuvchida bir vaqtda faqat 1 ta ochiq (`OPEN`) savat bo'lishini kafolatlaydi.
  - Indekslar: `['session_key', 'status']`, `['user', 'status']`.

- **Hisoblanadigan Xususiyatlar (Properties) va Metodlar**:
  - `total_items -> int`: Savatdagi barcha tovarlarning umumiy soni (donalari yig'indisi: `sum(item.quantity)`).
  - `unique_items_count -> int`: Savatdagi alohida SKU qatorlari soni (`self.items.count()`).
  - `subtotal -> Decimal`: Barcha tovarlarning asl (chegirmasiz) narxlari bo'yicha jami summa.
  - `total_price -> Decimal`: Chegirmalar hisobga olingan holda mijoz to'lashi kerak bo'lgan jami summa (`sum(item.total_price)`).
  - `total_discount -> Decimal`: Foydalanuvchi tejab qolgan umumiy summa (`subtotal - total_price`).
  - `is_empty -> bool`: Savat bo'sh yoki bo'sh emasligi (`self.items.exists()`).
  - `has_unavailable_items -> bool`: Savatda omborda yetarli bo'lmagan yoki nofaol qilingan mahsulotlar borligini tekshiradi.
  - `clear()`: Savatdagi barcha tovarlarni tozalash.
  - `merge_with(guest_cart)`: Mehmon savatidagi tovarlarni joriy foydalanuvchi savatiga aqlli birlashtirish (mavjud SKU bo'lsa miqdorini oshirish, zaxira limitini hisobga olish va mehmon savatini `MERGED` holatiga o'tkazish).

---

#### B. `CartItem` Model (`db_table = 'cart_items'`)

Savatdagi alohida mahsulot varianti qatorini ifodalaydi.

- **Maydonlar**:
  - `id`: `models.BigAutoField(primary_key=True)`
  - `cart`: `models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')`
  - `variant`: `models.ForeignKey('products.ProductVariant', on_delete=models.CASCADE, related_name='cart_items')`
  - `quantity`: `models.PositiveIntegerField(default=1)` (Kamida 1 bo'lishi `MinValueValidator(1)` orqali tekshiriladi).
  - `unit_price_at_addition`: `models.DecimalField(max_digits=14, decimal_places=2)` — mahsulot savatga qo'shilgan paytdagi narx snapshot'i (narx o'zgarishlarini taqqoslash va monitoring qilish uchun).
  - `created_at`: `models.DateTimeField(auto_now_add=True)`
  - `updated_at`: `models.DateTimeField(auto_now=True)`

- **Cheklovlar va Indekslar (Meta)**:
  - `UniqueConstraint(fields=['cart', 'variant'], name='unique_cart_variant')`: Bir savatda bir xil variant ikki marta alohida qator bo'lib tushmaydi, balki `quantity` oshiriladi.
  - Tartiblash: `['-created_at']`.

- **Hisoblanadigan Xususiyatlar (Properties) va Metodlar**:
  - `current_unit_price -> Decimal`: `variant.final_price` orqali joriy aktual narxni qaytaradi.
  - `subtotal -> Decimal`: `variant.price * self.quantity` (asl narx bo'yicha).
  - `total_price -> Decimal`: `current_unit_price * self.quantity` (chegirmali aktual narx bo'yicha).
  - `discount_amount -> Decimal`: `self.subtotal - self.total_price` (ushbu tovardan tejalgan summa).
  - `is_price_changed -> bool`: Savatga qo'shilgan paytdagi narx joriy narxdan farq qiladimi (`unit_price_at_addition != current_unit_price`).
  - `is_available -> bool`: Variant faol (`is_active=True`) va omborda yetarli qoldiq mavjudmi (`variant.inventory.available_quantity >= self.quantity`).
  - `clean()`: Miqdor 1 dan kam emasligi va omborda yetarli zaxira borligini tekshiradi (validation).

---

### 2.3. Biznes Mantiq va Chekka Holatlar (Business Logic & Edge Cases)

1. **Ombor Zaxirasini Tekshirish (Inventory Availability Check)**:
   - `Inventory.available_quantity` qiymati real-vaqtda tekshiriladi (`quantity - reserved_quantity`).
   - Agar foydalanuvchi omborda boridan ortiq miqdorda tovar qo'shmoqchi bo'lsa, `ValidationError` qaytariladi.
   - Savatdagi tovarlar omborni band (reserve) **qilmaydi**. Zaxirani band qilish faqat Checkout / Order yaratilish bosqichida (`apps/orders`) amalga oshiriladi.

2. **Anonim va Ro'yxatdan O'tgan Savatlarni Birlashtirish (Cart Merge Strategy)**:
   - Foydalanuvchi tizimga kirmasdan 2 ta tovar tanladi (mehmon savat `session_key` bilan ochildi).
   - Foydalanuvchi tizimga kirdi (Login):
     - Agar foydalanuvchida avvaldan ochiq savat mavjud bo'lsa: Mehmon savatidagi tovarlar foydalanuvchi savatiga ko'chiriladi. Bir xil SKU mavjud bo'lsa, miqdorlar qo'shiladi (ombordagi maksimal miqdordan oshmagan holda).
     - Mehmon savati statusi `MERGED` ga o'zgartiriladi va arxivlanadi.
     - Agar foydalanuvchida avval ochiq savat bo'lmasa: Mehmon savati to'g'ridan-to'g'ri foydalanuvchiga biriktiriladi (`cart.user = user`, `cart.session_key = None`).

3. **Narxlar Dinamikasi va Chegirmalar**:
   - Do'konda aksiya boshlansa yoki tugasa, savatdagi jami summa avtomatik ravishda `variant.final_price` bo'yicha qayta hisoblanadi.
   - `unit_price_at_addition` orqali frontendda "Mahsulot narxi arzonlashdi!" yoki "Mahsulot narxi oshdi!" xabarlarini ko'rsatish mumkin bo'ladi.

4. **N+1 SQL So'rovlarini Oldini Olish**:
   - `Cart.items.all()` chaqirilganda `.select_related('variant__product', 'variant__inventory')` va `.prefetch_related('variant__attributes__attribute', 'variant__attributes__attribute_value', 'variant__media')` qo'llanilishi rejalashtiriladi.

---

## 3. Django Admin Interfeysi Integratsiyasi

`apps/carts/admin.py` quyidagi qulayliklar bilan jihozlanadi:
- `CartItemInline`: Savat sahifasining o'zida ichidagi tovarlar ro'yxatini ko'rish (variant, SKU, miqdor, qo'shilgan paytdagi narx, joriy narx, umumiy summa va ombordagi mavjudlik statusi).
- `CartAdmin`:
  - List display: `id`, `user`, `session_key`, `status`, `total_items`, `total_price`, `created_at`.
  - Filters: `status`, `created_at`.
  - Search: `user__email`, `user__first_name`, `session_key`, `id`.
  - Readonly fields: hisoblangan maydonlar (`total_items`, `total_price`, `subtotal`, `total_discount`, `created_at`, `updated_at`).

---

## 4. Testlash Strategiyasi (`apps/carts/tests.py`)

Quyidagi ssenariylarni to'liq qamrab oluvchi testlar yoziladi:
1. **Model Yaratilishi**: Foydalanuvchi savati va mehmon savatini yaratish.
2. **Tovar Qo'shish & Noyoblik**: Bitta savatga bitta variantni takror qo'shganda `unique_together` / `UniqueConstraint` to'g'ri ishlashi.
3. **Hisob-Kitoblar**: `subtotal`, `total_price`, `total_discount` to'g'ri hisoblanishi (chegirmali va chegirmasiz variantlar bilan).
4. **Zaxira Validatsiyasi**: Ombordagi erkin qoldiqdan ortiq tovar kiritilganda `ValidationError` yuzaga kelishi.
5. **Savatlarni Birlashtirish (`merge_with`)**: Mehmon savatidagi tovarlarni foydalanuvchi savatiga muvaffaqiyatli qo'shish va takroriy tovarlar miqdorini birlashtirish.
6. **Savatni Tozalash (`clear`)**: Barcha tovarlar to'g'ri o'chirilishi.

---

## 5. Execution Checklist

- [x] Step 1: Git branch yaratish (`feat/carts-models`) va `dev` bazasidan yangilash
- [x] Step 2: `apps/carts/models.py` da `Cart` va `CartItem` modellarini yaratish
- [x] Step 3: Modellar uchun `makemigrations` va `migrate` buyruqlarini bajarish
- [x] Step 4: `apps/carts/admin.py` da `CartAdmin` va `CartItemInline` ni sozlash
- [x] Step 5: `apps/carts/tests.py` da barcha biznes mantiq va metodlar uchun unit testlar yozish
- [x] Step 6: Testlarni ishga tushirish va `python manage.py check` orqali to'liq tekshirish
- [x] Step 7: Rejadagi qadamlarni yangilash va o'zgarishlarni git'ga commit qilish
