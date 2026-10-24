# Plan: Order Data Models Architecture (`apps/orders`)

## Metadata
- **Title**: Order & Checkout Data Models Architecture: Order, OrderItem, OrderAddress, OrderStatusHistory, Coupon & CouponUsage
- **Date**: 2026-10-22
- **Status**: COMPLETED
- **Branch**: `feat/orders-models`
- **Completed**: 2026-10-22
- **Author**: Antigravity

---

## 1. Context & Motivation

Loyihamizda foydalanuvchilar (`apps/users`), mahsulotlar katalogi (`apps/products`) va savat tizimi (`apps/carts`) to'liq ishlab chiqilgan va sinovdan o'tgan. Endi e-commerce tizimining eng muhim va markaziy yuragi hisoblangan **Orders (Buyurtmalar)** ilovasi ma'lumotlar bazasi modellarini yaratish navbati keldi.

Professional va yuqori yuklamali e-commerce platformalarida buyurtmalar tizimi oddiy jadval emas, balki qat'iy talablarga ega murakkab moliyaviy va operatsion ekotizimdir:

1. **O'zgarmas Tarixiy Snapshotlar (Immutability & Audit Trail)**:
   - Mahsulot narxi, nomi, atributlari yoki chegirmasi kelajakda o'zgarsa (yoki mahsulot butunlay o'chirib yuborilsa ham), buyurtma qilingan paytdagi tarixiy narx va holat o'zgarmasligi shart.
   - Foydalanuvchi o'z profilidagi manzilini o'zgartirsa yoki yangilasa, ilgari berilgan buyurtmalarning yetkazib berish manzili buzilmasligi uchun har bir buyurtma o'zining mustaqil manzil snapshotiga (`OrderAddress`) ega bo'lishi kerak.

2. **Ko'p Bosqichli Hayot Tsikli (Order Lifecycle & Tracking)**:
   - Buyurtma yaratilishidan tortib to mijoz qo'liga yetib borguniga qadar aniq bosqichlardan (`PENDING` -> `PAID` -> `PROCESSING` -> `SHIPPED` -> `DELIVERED` yoki `CANCELLED`) o'tadi.
   - Har bir holat o'zgarishi vaqt, sabab va mas'ul shaxs (admin, kuryer, to'lov webhooki) bilan birga `OrderStatusHistory` modelida qayd etib borilishi, mijoz esa o'z profilida "Kuzatuv (Timeline)" ko'rinishida ko'rishi zarur.

3. **To'lov va Yetkazib Berish Tizimlari Bilan Integratsiyaga Moslik**:
   - O'zbekiston bozoridagi ommabop to'lov tizimlari (Payme, Click, Uzum) hamda naqd/karta orqali qabul qilish (Cash on Delivery) usullarini qo'llab-quvvatlash.
   - To'lov holati (`payment_status`) va buyurtma holati (`status`) mustaqil boshqarilishi.

4. **Kupon va Promokodlar Tizimi (Coupons & Discounts)**:
   - Foizli yoki qat'iy summadagi chegirmalar, minimal xarid talabi, umumiy va bitta foydalanuvchi uchun cheklovlar (`usage_limit_per_user`), amal qilish muddatlarini tekshirish va chegirma hisob-kitoblarini avtomatlashtirish.

5. **Ombor Zaxirasini Band Qilish (Inventory Reservation Integrity)**:
   - Buyurtma rasmiylashtirilganda `apps.products.models.Inventory` dagi `reserved_quantity` oshirilishi, to'langanda qoldiqdan ayirilishi, bekor qilinganda esa zaxira darhol omborga qaytarilishi (rollback) kerak.

---

## 2. Architecture & Technical Design

### 2.1. Entity-Relationship Diagram

```mermaid
erDiagram
    User ||--o{ Order : "places"
    Order ||--|{ OrderItem : "contains"
    Order ||--|| OrderAddress : "ships to"
    Order ||--o{ OrderStatusHistory : "tracked by"
    Coupon ||--o{ Order : "applied to"
    Coupon ||--o{ CouponUsage : "tracks"
    User ||--o{ CouponUsage : "redeemed by"
    ProductVariant ||--o{ OrderItem : "variant snapshot"
    Cart ||--o| Order : "converted from"

    Order {
        bigint id PK
        string order_number UK "ORD-YYYYMMDD-XXXX"
        fk user FK "nullable"
        string status "PENDING/PAID/PROCESSING/SHIPPED/DELIVERED/CANCELLED"
        string payment_status "PENDING/PAID/FAILED/REFUNDED"
        string payment_method "PAYME/CLICK/UZUM/COD"
        string shipping_method "STANDARD/EXPRESS/PICKUP"
        decimal subtotal "Snapshot of items subtotal"
        decimal shipping_fee "Delivery cost"
        decimal discount_amount "Coupon discount"
        decimal total_price "subtotal + shipping - discount"
        string tracking_number "Courier tracking code"
        datetime created_at
        datetime updated_at
    }

    OrderItem {
        bigint id PK
        fk order FK "Order"
        fk variant FK "ProductVariant (SET_NULL)"
        string product_name "Snapshot of Product title"
        string variant_sku "Snapshot of SKU"
        string variant_attributes_display "Color: Black | Size: XL"
        json attributes_snapshot "Structured attributes"
        decimal unit_price "Price per unit at purchase"
        int quantity "min 1"
        decimal total_price "unit_price * quantity"
    }

    OrderAddress {
        bigint id PK
        fk order FK "OneToOne with Order"
        string recipient_name
        string phone_number
        string region "Province / City"
        string district
        string street_address
        string apartment_office
        string postal_code
        string landmark
        decimal latitude
        decimal longitude
        text delivery_instructions
    }

    OrderStatusHistory {
        bigint id PK
        fk order FK "Order"
        string old_status
        string new_status
        string comment
        fk created_by FK "User/Admin (nullable)"
        boolean is_customer_visible
        datetime created_at
    }

    Coupon {
        bigint id PK
        string code UK "SUMMER2026"
        string discount_type "PERCENTAGE / FIXED_AMOUNT"
        decimal discount_value
        decimal min_order_amount
        decimal max_discount_amount
        int usage_limit
        int usage_limit_per_user
        int used_count
        datetime valid_from
        datetime valid_until
        boolean is_active
    }

    CouponUsage {
        bigint id PK
        fk coupon FK
        fk user FK
        fk order FK
        decimal discount_amount
        datetime used_at
    }
```

---

## 3. Models Detailed Specification (`apps/orders/models.py`)

### 3.1. `Order` Model (`db_table = 'orders'`)

Buyurtmaning markaziy modeli. Moliyaviy yakuniy hisob-kitoblar, mijoz ma'lumotlari, to'lov va buyurtma holatlarini birlashtiradi.

- **Maydonlar**:
  - `id`: `models.BigAutoField(primary_key=True)`
  - `order_number`: `models.CharField(max_length=32, unique=True, editable=False, db_index=True)` — foydalanuvchilar va ma'muriyat uchun xavfsiz, o'qilishi oson identifikator (masalan: `ORD-20261022-A8F2K1`).
  - `user`: `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', db_index=True)` — buyurtma egasi. `SET_NULL` orqali akkaunt o'chirilgan taqdirda ham soliq va buxgalteriya hisoboti uchun buyurtma bazada saqlanadi.
  - `cart`: `models.ForeignKey('carts.Cart', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')` — buyurtmaga aylantirilgan savatga havola.
  - `coupon`: `models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')` — qo'llanilgan promokod/kupon.
  - `status`: `models.CharField(max_length=25, choices=OrderStatus.choices, default=OrderStatus.PENDING, db_index=True)`:
    - `PENDING`: Buyurtma yaratildi, to'lov yoki mijoz tasdig'i kutilmoqda.
    - `AWAITING_PAYMENT`: To'lov tizimiga yo'naltirildi.
    - `CONFIRMED`: Buyurtma tasdiqlandi (to'lov amalga oshdi yoki menejer tasdiqladi).
    - `PROCESSING`: Ombor tomonidan yig'ilmoqda va qadoqlanmoqda.
    - `SHIPPED`: Kuryerga yoki yetkazib berish xizmatiga topshirildi.
    - `DELIVERED`: Mijoz tovarlarni qabul qilib oldi.
    - `CANCELLED`: Buyurtma bekor qilindi (zaxira omborga qaytarilgan).
    - `REFUNDED`: To'lov mijozga qaytarildi.
  - `payment_status`: `models.CharField(max_length=25, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True)`:
    - `PENDING`: To'lov kutilmoqda
    - `PAID`: Muvaffaqiyatli to'landi
    - `PARTIALLY_REFUNDED`: Qisman qaytarildi
    - `REFUNDED`: To'liq qaytarildi
    - `FAILED`: To'lov xatolik bilan yakunlandi
  - `payment_method`: `models.CharField(max_length=25, choices=PaymentMethod.choices, default=PaymentMethod.CASH_ON_DELIVERY)`:
    - `PAYME`, `CLICK`, `UZUM`, `CASH_ON_DELIVERY`, `CARD_ON_DELIVERY`
  - `shipping_method`: `models.CharField(max_length=25, choices=ShippingMethod.choices, default=ShippingMethod.STANDARD)`:
    - `STANDARD`: Standart yetkazib berish
    - `EXPRESS`: Tezkor (bir necha soat ichida)
    - `PICKUP`: Do'kondan olib ketish
  - `subtotal`: `models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))` — tovarlarning jami sof narxi snapshot'i.
  - `shipping_fee`: `models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))` — yetkazib berish haqi.
  - `discount_amount`: `models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))` — kupon/aksiyalar bo'yicha tejalgan summa.
  - `total_price`: `models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))` — yakuniy to'lov miqdori (`subtotal + shipping_fee - discount_amount`).
  - `currency`: `models.CharField(max_length=3, default='UZS')`
  - `tracking_number`: `models.CharField(max_length=100, blank=True, null=True, db_index=True)`
  - `customer_notes`: `models.TextField(blank=True, null=True)`
  - `cancellation_reason`: `models.TextField(blank=True, null=True)`
  - `admin_notes`: `models.TextField(blank=True, null=True)`
  - `paid_at`: `models.DateTimeField(null=True, blank=True)`
  - `delivered_at`: `models.DateTimeField(null=True, blank=True)`
  - `cancelled_at`: `models.DateTimeField(null=True, blank=True)`
  - `created_at`: `models.DateTimeField(auto_now_add=True, db_index=True)`
  - `updated_at`: `models.DateTimeField(auto_now=True)`

- **Cheklovlar va Indekslar (Meta)**:
  - Indekslar: `['order_number']`, `['user', 'status']`, `['status', 'created_at']`, `['payment_status']`.
  - Ordering: `['-created_at']`.

- **Asosiy Metodlar va Xususiyatlar**:
  - `save()`: `order_number` mavjud bo'lmasa, unikal formatda avtomatik generatsiya qilish (`ORD-YYYYMMDD-XXXXXX`).
  - `total_items -> int`: Buyurtmadagi umumiy mahsulot donalari soni.
  - `can_cancel -> bool`: Buyurtmani bekor qilish mumkinmi (`status in [PENDING, AWAITING_PAYMENT, CONFIRMED]`).
  - `recalculate_totals()`: Subtotal, chegirma va shipping_fee asosida total_price ni qayta hisoblash va yaxlitlash.
  - `mark_as_paid()`: To'lov muvaffaqiyatli bo'lganda chaqiriladi (`payment_status=PAID`, `paid_at=now`, holat o'zgarish tarixi yoziladi).
  - `cancel(reason, user)`: Buyurtmani bekor qilish, holatini `CANCELLED` ga o'tkazish, zaxiralarni omborga qaytarish.

---

### 3.2. `OrderAddress` Model (`db_table = 'order_addresses'`)

Buyurtmaning o'zgarmas yetkazib berish manzili snapshot'i.

- **Maydonlar**:
  - `id`: `models.BigAutoField(primary_key=True)`
  - `order`: `models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipping_address')`
  - `recipient_name`: `models.CharField(max_length=255)` (qabul qilib oluvchi F.I.Sh)
  - `phone_number`: `models.CharField(max_length=20)` (bog'lanish telefoni)
  - `alternative_phone_number`: `models.CharField(max_length=20, blank=True, null=True)`
  - `region`: `models.CharField(max_length=100)` (viloyat yoki shahar, masalan: Toshkent sh.)
  - `district`: `models.CharField(max_length=100)` (tuman, masalan: Mirobod tumani)
  - `street_address`: `models.CharField(max_length=255)` (ko'cha, uy raqami)
  - `apartment_office`: `models.CharField(max_length=50, blank=True, null=True)` (xonadon, qavat)
  - `postal_code`: `models.CharField(max_length=20, blank=True, null=True)` (pochta indeksi)
  - `landmark`: `models.CharField(max_length=255, blank=True, null=True)` (mo'ljal)
  - `latitude`: `models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `longitude`: `models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `delivery_instructions`: `models.TextField(blank=True, null=True)` (kuryerga ko'rsatma)
  - `created_at`: `models.DateTimeField(auto_now_add=True)`

- **Metodlar**:
  - `full_address -> str`: Formatlangan to'liq manzil matni.

---

### 3.3. `OrderItem` Model (`db_table = 'order_items'`)

Buyurtmadagi alohida SKU tovar qatori va uning xarid onidagi to'liq snapshot'i.

- **Maydonlar**:
  - `id`: `models.BigAutoField(primary_key=True)`
  - `order`: `models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')`
  - `variant`: `models.ForeignKey('products.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')`
  - `product_name`: `models.CharField(max_length=255)` — mahsulotning xarid paytidagi nomi.
  - `variant_sku`: `models.CharField(max_length=100)` — xarid paytidagi SKU kodi.
  - `variant_attributes_display`: `models.CharField(max_length=255, blank=True)` — "Rang: Moviy | O'lcham: 256GB" ko'rinishidagi qator.
  - `attributes_snapshot`: `models.JSONField(default=dict, blank=True)` — atributlarning JSON ko'rinishidagi to'liq ma'lumoti.
  - `unit_price`: `models.DecimalField(max_digits=14, decimal_places=2)` — 1 dona mahsulotning sotilgan paytdagi narxi (`variant.final_price`).
  - `quantity`: `models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])`
  - `total_price`: `models.DecimalField(max_digits=14, decimal_places=2)` — qator bo'yicha jami summa (`unit_price * quantity`).
  - `created_at`: `models.DateTimeField(auto_now_add=True)`
  - `updated_at`: `models.DateTimeField(auto_now=True)`

- **Metodlar**:
  - `save()`: `total_price` ni `unit_price * quantity` qilib avtomatik hisoblash.

---

### 3.4. `OrderStatusHistory` Model (`db_table = 'order_status_history'`)

Buyurtma hayotiy tsiklini to'liq kuzatish, audit qilish va mijoz sahifasida progress-bar/timeline sifatida ko'rsatish modeli.

- **Maydonlar**:
  - `id`: `models.BigAutoField(primary_key=True)`
  - `order`: `models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')`
  - `old_status`: `models.CharField(max_length=25, choices=Order.OrderStatus.choices, blank=True, null=True)`
  - `new_status`: `models.CharField(max_length=25, choices=Order.OrderStatus.choices)`
  - `comment`: `models.CharField(max_length=255, blank=True)`
  - `created_by`: `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)` — statusni kim o'zgartirdi (admin yoki mijoz). Agar tizim (webhook, cron) o'zgartirsa `null`.
  - `is_customer_visible`: `models.BooleanField(default=True)` — mijozga ko'rsatilishi kerakmi yoki faqat admin uchun ichki eslatmami.
  - `created_at`: `models.DateTimeField(auto_now_add=True)`

- **Meta**:
  - Ordering: `['created_at']`.

---

### 3.5. `Coupon` Model (`db_table = 'coupons'`)

Promokodlar va chegirma tizimi.

- **Maydonlar**:
  - `id`: `models.BigAutoField(primary_key=True)`
  - `code`: `models.CharField(max_length=50, unique=True, db_index=True)` (uppercase formatda, masalan: `SUPER2026`).
  - `discount_type`: `models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)`:
    - `PERCENTAGE`: Foizli chegirma (masalan: 10%)
    - `FIXED_AMOUNT`: Aniq belgilangan so'mdagi chegirma (masalan: 50,000 UZS)
  - `discount_value`: `models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])`
  - `min_order_amount`: `models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))` — chegirma ishlashi uchun zarur eng kam tovar summasi.
  - `max_discount_amount`: `models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` — foizli chegirmalar uchun maksimal ruxsat etilgan chegirma chegarasi (shift).
  - `usage_limit`: `models.PositiveIntegerField(null=True, blank=True)` — kuponning butun tizim bo'yicha jami foydalanish limiti.
  - `usage_limit_per_user`: `models.PositiveIntegerField(default=1)` — bitta xaridor ko'pi bilan necha marta foydalana olishi.
  - `used_count`: `models.PositiveIntegerField(default=0)` — necha marta ishlatilganligi hisoblagichi.
  - `valid_from`: `models.DateTimeField()`
  - `valid_until`: `models.DateTimeField()`
  - `is_active`: `models.BooleanField(default=True, db_index=True)`
  - `created_at`: `models.DateTimeField(auto_now_add=True)`
  - `updated_at`: `models.DateTimeField(auto_now=True)`

- **Metodlar**:
  - `is_valid(user=None, subtotal=None) -> tuple[bool, str]`: Muddat, status, limitlar va minimal summani tekshirish.
  - `calculate_discount(subtotal: Decimal) -> Decimal`: Chegirma summasini to'g'ri hisoblash (foiz, qat'iy summa, maksimal chegirma limitini inobatga olgan holda).

---

### 3.6. `CouponUsage` Model (`db_table = 'coupon_usages'`)

Har bir kuponning qaysi foydalanuvchi va qaysi buyurtmada qo'llanilganligini qayd etish.

- **Maydonlar**:
  - `id`: `models.BigAutoField(primary_key=True)`
  - `coupon`: `models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')`
  - `user`: `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coupon_usages')`
  - `order`: `models.ForeignKey(Order, on_delete=models.CASCADE, related_name='coupon_usages')`
  - `discount_amount`: `models.DecimalField(max_digits=14, decimal_places=2)`
  - `used_at`: `models.DateTimeField(auto_now_add=True)`

- **Meta**:
  - Constraints: `models.UniqueConstraint(fields=['coupon', 'order'], name='unique_coupon_per_order')`

---

## 4. Ombor Zaxirasi va Tranzaksiyalar Bilan Integratsiya

1. **Zaxirani Band Qilish (Order Creation -> Reserve)**:
   - Buyurtma yaratilayotganda `select_for_update()` yordamida barcha SKU lar bloklanadi.
   - Har bir `OrderItem` uchun:
     `variant.inventory.reserved_quantity += item.quantity`
     `variant.inventory.save()`
2. **To'lov Tasdiqlanganda (Payment Confirmation -> Deduct)**:
   - `variant.inventory.quantity -= item.quantity`
   - `variant.inventory.reserved_quantity -= item.quantity`
   - `variant.inventory.save()`
3. **Bekor Qilinganda (Cancellation -> Release)**:
   - Agar buyurtma hali to'lanmagan yoki jo'natilmagan bo'lsa:
     `variant.inventory.reserved_quantity -= item.quantity`
   - Agar to'langan bo'lsa va qaytarilsa:
     `variant.inventory.quantity += item.quantity`

---

## 5. Execution Checklist

- [x] Step 1: `apps/orders/models.py` da barcha modellarni (`Order`, `OrderItem`, `OrderAddress`, `OrderStatusHistory`, `Coupon`, `CouponUsage`) to'liq e'lon qilish.
- [x] Step 2: Modellar uchun to'liq helper metodlar, propertylar, string representations va validation tekshiruvlarini yozish.
- [x] Step 3: `python manage.py makemigrations orders` va `python manage.py migrate` orqali bazaga migratsiyalarni yaratish va muvaffaqiyatli tatbiq etish.
- [x] Step 4: `apps/orders/admin.py` da modellar uchun qulay Django Admin interfeysini sozlash (`OrderAdmin`, inlines: `OrderItemInline`, `OrderAddressInline`, `OrderStatusHistoryInline`, `CouponAdmin`).
- [x] Step 5: `apps/orders/tests/` paketida modellar, hisob-kitoblar, signallar va cheklovlar uchun keng qamrovli test to'plamini (Unit & Integration tests) yozish.
- [x] Step 6: Testlarni ishga tushirish (`python manage.py test apps.orders`) va butun loyiha bo'yicha regressiya yo'qligini tekshirish (`python manage.py test`).
- [x] Step 7: Bajarilgan ishlarni ko'zdan kechirib, reja statusini `COMPLETED` ga o'tkazish va o'zgarishlarni `feat/orders-models` tarmog'iga commit qilish.
