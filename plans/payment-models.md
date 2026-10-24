# Plan: Payment Data Models Architecture (`apps/payments`)

## Metadata
- **Title**: Payment Data Models Architecture: Payment, PaymentTransaction, Refund, and SavedCard
- **Date**: 2026-10-22
- **Status**: COMPLETED
- **Branch**: `feat/payments-models`
- **Completed**: 2026-10-22
- **Author**: Antigravity

---

## 1. Context & Motivation

Loyiha arxitekturasida foydalanuvchilar (`apps/users`), mahsulotlar katalogi (`apps/products`), savat (`apps/carts`) va buyurtmalar (`apps/orders`) modullari to'liq ishlab chiqildi. `apps/orders` modulida `Order` modeli quyidagi to'lov bilan bog'liq maydonlar va metodlarga ega:
- `payment_status`: `PENDING`, `PAID`, `PARTIALLY_REFUNDED`, `REFUNDED`, `FAILED`
- `payment_method`: `PAYME`, `CLICK`, `UZUM`, `CASH_ON_DELIVERY`, `CARD_ON_DELIVERY`
- `total_price`: Buyurtmaning yakuniy to'lanishi lozim bo'lgan summasi
- `paid_at`: To'lov amalga oshirilgan sana va vaqt
- `mark_as_paid()`: Buyurtma to'lov holatini `PAID` ga o'tkazuvchi va buyurtma holatini `CONFIRMED` ga suruvchi tranzaksiyaviy metod

Ammo yuqori yuklamali va professional e-commerce platformalarida to'lov tizimi buyurtmaning ichidagi oddiy status bilan cheklana olmaydi. Haqiqiy to'lov ekotizimi quyidagi jiddiy moliyaviy, xavfsizlik va operatsion talablarni qondirishi lozim:

1. **Ko'p To'lovli Va Takroriy Urinishlar (Multiple Payment Attempts & Lifecycle)**:
   - Foydalanuvchi buyurtma bergach, Payme orqali to'lovni boshlashi, ammo kartasida mablag' yetmasligi yoki bekor qilishi mumkin. Shundan so'ng u Click yoki Uzum orqali qayta to'lashi mumkin.
   - Har bir to'lov urinishi alohida `Payment` yozuvi sifatida qayd etilishi va o'zining mustaqil hayot sikliga (`PENDING` -> `PROCESSING` -> `SUCCESS` / `FAILED` / `CANCELLED`) ega bo'lishi shart.

2. **O'zbekiston To'lov Provayderlari Bilan Integratsiya Mosligi (Payme, Click, Uzum)**:
   - Payme (JSON-RPC 2.0 protokoli: `CheckPerformTransaction`, `PerformTransaction`, `CancelTransaction`, `CheckTransaction`).
   - Click (Shop API: `Prepare`, `Complete`, xatolik kodlari va tranzaksiya identifikatorlari).
   - Uzum Bank (Uzum Pay / Apelsin merchant protokoli).
   - Naqd va Karta orqali yetkazib berilganda to'lash (`CASH_ON_DELIVERY`, `CARD_ON_DELIVERY`).
   - Har bir provayderning tashqi tranzaksiya IDsi (`provider_transaction_id`), holati (`provider_state`), to'lovga yo'naltiruvchi havola (`checkout_url`) va maxsus ma'lumotlari (`metadata`) to'liq saqlanishi kerak.

3. **Moliyaviy Audit va Tranzaksiyalar Logi (Audit Trail & Idempotency)**:
   - Banklar va to'lov shlyuzlari (Payme/Click) yuboradigan har bir so'rov (webhook), javob, parametrlar va xatoliklar `PaymentTransaction` modelida to'liq qayd etib borilishi kerak.
   - Bu moliyaviy tekshiruvlar (reconciliation), nizolarni hal qilish va to'lov dublikatlarining (idempotency) oldini olish uchun yagona ishonchli manba hisoblanadi.

4. **Pulni Qaytarish Mexanizmi (Refunds Management)**:
   - Buyurtma bekor qilinganda yoki tovar qaytarilganda, to'langan mablag'ni to'liq yoki qisman mijozga qaytarish (`Refund` modeli) zarur.
   - Qaytarish sababi, mas'ul admin/menejer, bank tranzaksiya IDsi va holati aniq yuritilishi kerak.

5. **Tokenlashtirilgan Bank Kartalarini Saqlash (SavedCard - 1-Click Checkout)**:
   - Mijozlarga har safar karta raqamini kiritmasdan xarid qilish imkoniyatini yaratish (Uzcard, Humo, Visa, Mastercard).
   - PCI-DSS talablariga muvofiq, ochiq karta raqami yoki CVV bazada hech qachon saqlanmaydi — faqat shifrlangan provayder tokeni (`card_token`) va niqoblangan raqam (`card_mask`: masalan `8600 12** **** 1234`).

---

## 2. Architecture & Technical Design

### 2.1. Entity-Relationship Diagram

```mermaid
erDiagram
    Order ||--o{ Payment : "has"
    User ||--o{ Payment : "initiates"
    Payment ||--o{ PaymentTransaction : "logs"
    Payment ||--o{ Refund : "refunded via"
    Order ||--o{ Refund : "associated with"
    User ||--o{ SavedCard : "owns"
    User ||--o{ Refund : "processed by"

    Payment {
        bigint id PK
        string payment_number UK "PAY-YYYYMMDD-XXXXXX"
        fk order FK "PROTECT"
        fk user FK "SET_NULL"
        decimal amount "Snapshot of payable amount"
        string currency "UZS"
        string provider "PAYME/CLICK/UZUM/COD/CARD_ON_DELIVERY"
        string status "PENDING/PROCESSING/SUCCESS/FAILED/CANCELLED/REFUNDED/PARTIALLY_REFUNDED"
        string provider_transaction_id "External gateway transaction ID"
        string provider_state "State code from provider"
        decimal fee_amount "Service commission"
        decimal refunded_amount "Total refunded sum"
        string checkout_url "Gateway payment redirect URL"
        json metadata "Arbitrary provider response data"
        text failure_reason "Reason if failed"
        datetime paid_at
        datetime failed_at
        datetime cancelled_at
        datetime created_at
        datetime updated_at
    }

    PaymentTransaction {
        bigint id PK
        fk payment FK "CASCADE"
        string transaction_type "CHECK/CREATE/PERFORM/CANCEL/REFUND/WEBHOOK"
        decimal amount "Operation amount"
        string status "PENDING/SUCCESS/FAILED"
        string idempotency_key "UUID/Unique key"
        string provider_transaction_id "External ID"
        json request_payload "Webhook/API request payload"
        json response_payload "Gateway response payload"
        string error_code "Provider error code"
        text error_message "Provider error text"
        string ip_address "Sender IP address"
        datetime created_at
    }

    Refund {
        bigint id PK
        string refund_number UK "REF-YYYYMMDD-XXXXXX"
        fk payment FK "PROTECT"
        fk order FK "PROTECT"
        decimal amount "Amount to refund"
        string currency "UZS"
        string status "PENDING/COMPLETED/FAILED/CANCELLED"
        text reason "Cancellation/Return reason"
        string provider_refund_id "Gateway refund ID"
        fk created_by FK "Staff user who initiated"
        datetime processed_at
        json metadata "Gateway refund response"
        datetime created_at
        datetime updated_at
    }

    SavedCard {
        bigint id PK
        fk user FK "CASCADE"
        string provider "PAYME/CLICK/UZUM"
        string card_token "Encrypted card token"
        string card_mask "8600 12** **** 1234"
        string card_holder "Cardholder name"
        string card_type "UZCARD/HUMO/VISA/MASTERCARD"
        string expire_month "MM"
        string expire_year "YY"
        boolean is_default "Default card flag"
        boolean is_verified "OTP verification flag"
        datetime created_at
        datetime updated_at
    }
```

---

## 3. Models Detailed Specification (`apps/payments/models.py`)

### 3.1. `Payment` Model (`db_table = 'payments'`)

Tizimdagi to'lov buyrug'i va hisob-kitobning bosh entity modeli.

- **Maydonlar**:
  - `id`: `BigAutoField(primary_key=True)`
  - `payment_number`: `CharField(max_length=32, unique=True, editable=False, db_index=True)` — inson o'qishi oson unikal to'lov kodi (masalan: `PAY-20261022-8F9B2C`).
  - `order`: `ForeignKey('orders.Order', on_delete=models.PROTECT, related_name='payments', db_index=True)` — tegishli buyurtma. Moliyaviy audit xavfsizligi uchun `PROTECT` qo'llaniladi (to'lov mavjud bo'lgan buyurtmani o'chirib bo'lmaydi).
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments', db_index=True)` — to'lovchi mijoz.
  - `amount`: `DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])` — to'lanadigan summa.
  - `currency`: `CharField(max_length=3, default='UZS')` — valyuta kodi.
  - `provider`: `CharField(max_length=25, choices=PaymentProvider.choices)` — to'lov usuli/shlyuz (`PAYME`, `CLICK`, `UZUM`, `CASH_ON_DELIVERY`, `CARD_ON_DELIVERY`).
  - `status`: `CharField(max_length=25, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True)`:
    - `PENDING`: To'lov boshlandi, foydalanuvchi to'lashi kutilmoqda.
    - `PROCESSING`: Tranzaksiya provayderda tekshirilmoqda / hold qilingan.
    - `SUCCESS`: To'lov to'liq muvaffaqiyatli qabul qilindi.
    - `FAILED`: Xatolik, yetarsiz mablag' yoki provayder rad etdi.
    - `CANCELLED`: Foydalanuvchi yoki vaqt tugashi sababli bekor qilindi.
    - `REFUNDED`: To'lov to'liq qaytarilgan.
    - `PARTIALLY_REFUNDED`: Qisman pul qaytarilgan.
  - `provider_transaction_id`: `CharField(max_length=255, blank=True, null=True, db_index=True)` — Payme/Click/Uzum tranzaksiya IDsi.
  - `provider_state`: `CharField(max_length=50, blank=True, null=True)` — provayder ichki holat kodi (masalan Payme state: 1, 2, -1, -2).
  - `fee_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))` — provayder komissiyasi.
  - `refunded_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))` — qaytarilgan umumiy summa.
  - `checkout_url`: `URLField(max_length=1000, blank=True, null=True)` — Payme/Click checkout havolasi.
  - `metadata`: `JSONField(default=dict, blank=True)` — qo'shimcha parametrlar, provayder javoblari snapshotlari.
  - `failure_reason`: `TextField(blank=True, null=True)` — to'lov amalga oshmay qolgan taqdirda xatolik sababi.
  - `paid_at`: `DateTimeField(null=True, blank=True)`
  - `failed_at`: `DateTimeField(null=True, blank=True)`
  - `cancelled_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True, db_index=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`

- **Biznes Metodlar**:
  - `generate_payment_number()`: Unikal `PAY-YYYYMMDD-XXXXXX` formatidagi kod yaratish.
  - `mark_as_success(provider_transaction_id=None, save=True)`: To'lovni muvaffaqiyatli deb belgilaydi, `paid_at` vaqtini qo'yadi hamda bog'liq `Order` modelidagi `mark_as_paid()` metodini avtomatik chaqiradi!
  - `mark_as_failed(reason='', save=True)`: To'lovni muvaffaqiyatsiz deb belgilaydi va `failed_at` vaqtini qo'yadi.
  - `mark_as_cancelled(save=True)`: To'lovni bekor qiladi va `cancelled_at` vaqtini qo'yadi.
  - `can_refund(refund_amount=None)`: Qaytarish imkoniyatini tekshiradi (`status == SUCCESS` va `refunded_amount + refund_amount <= amount`).

---

### 3.2. `PaymentTransaction` Model (`db_table = 'payment_transactions'`)

To'lov shlyuzlari (Payme, Click, Uzum) bilan barcha tarmoq muloqoti, webhooks, callback so'rovlari va javoblarining auditi.

- **Maydonlar**:
  - `id`: `BigAutoField(primary_key=True)`
  - `payment`: `ForeignKey(Payment, on_delete=models.CASCADE, related_name='transactions')`
  - `transaction_type`: `CharField(max_length=30, choices=TransactionType.choices)`:
    - `CHECK`: To'lovdan oldin akkaunt yoki buyurtmani tekshirish (`CheckPerformTransaction` / `Prepare`).
    - `CREATE`: To'lov yaratish so'rovi.
    - `PERFORM`: Mablag'ni yechish / yakunlash (`PerformTransaction` / `Complete`).
    - `CANCEL`: Bekor qilish (`CancelTransaction`).
    - `REFUND`: Pulni qaytarish operatsiyasi.
    - `WEBHOOK`: Provayderdan kelgan umumiy bildirishnoma.
  - `amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`
  - `status`: `CharField(max_length=20, choices=TransactionStatus.choices)` (`PENDING`, `SUCCESS`, `FAILED`)
  - `idempotency_key`: `CharField(max_length=100, blank=True, null=True, db_index=True)` — bir xil so'rov ikki marta bajarilishini oldini olish uchun kalit.
  - `provider_transaction_id`: `CharField(max_length=255, blank=True, null=True)`
  - `request_payload`: `JSONField(default=dict, blank=True)` — yuborilgan yoki qabul qilingan to'liq JSON data.
  - `response_payload`: `JSONField(default=dict, blank=True)` — shlyuz bergan to'liq javob.
  - `error_code`: `CharField(max_length=50, blank=True, null=True)` — provayder xato kodi (masalan Payme: `-31001`, Click: `-1`).
  - `error_message`: `TextField(blank=True, null=True)`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)` — xavfsizlik va fraud-monitoring uchun so'rov kelgan IP.
  - `created_at`: `DateTimeField(auto_now_add=True, db_index=True)`

---

### 3.3. `Refund` Model (`db_table = 'payment_refunds'`)

To'lovlarni to'liq yoki qisman qaytarish operatsiyalarini rasmiylashtirish va monitoring qilish.

- **Maydonlar**:
  - `id`: `BigAutoField(primary_key=True)`
  - `refund_number`: `CharField(max_length=32, unique=True, editable=False, db_index=True)` (`REF-YYYYMMDD-XXXXXX`).
  - `payment`: `ForeignKey(Payment, on_delete=models.PROTECT, related_name='refunds')`
  - `order`: `ForeignKey('orders.Order', on_delete=models.PROTECT, related_name='payment_refunds')`
  - `amount`: `DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])`
  - `currency`: `CharField(max_length=3, default='UZS')`
  - `status`: `CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.PENDING)`:
    - `PENDING`: Qaytarish jarayoni boshlangan.
    - `COMPLETED`: Mablag' muvaffaqiyatli qaytarildi.
    - `FAILED`: Qaytarishda bank rad javobi berdi.
    - `CANCELLED`: Qaytarish bekor qilindi.
  - `reason`: `TextField(blank=True, null=True)` — mijoz talabi, tovar sifatsizligi yoki buyurtma bekor bo'lgani sababi.
  - `provider_refund_id`: `CharField(max_length=255, blank=True, null=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_refunds')` — operatsiyani tasdiqlagan admin yoki operator.
  - `processed_at`: `DateTimeField(null=True, blank=True)`
  - `metadata`: `JSONField(default=dict, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`

- **Biznes Metodlar**:
  - `generate_refund_number()`
  - `mark_as_completed(provider_refund_id=None)`: Refund summasini `Payment.refunded_amount` ga qo'shadi, `Payment.status` ni (`REFUNDED` yoki `PARTIALLY_REFUNDED`) ga yangilaydi, shuningdek `Order.payment_status` ni mos ravishda yangilaydi.

---

### 3.4. `SavedCard` Model (`db_table = 'user_saved_cards'`)

Foydalanuvchilarning qayta ishlatiladigan bank kartalari tokenlari (1-Click checkout).

- **Maydonlar**:
  - `id`: `BigAutoField(primary_key=True)`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_cards')`
  - `provider`: `CharField(max_length=25, choices=PaymentProvider.choices)`
  - `card_token`: `CharField(max_length=255, help_text="Shlyuz tomonidan berilgan qayta ishlatiluvchi maxfiy token")`
  - `card_mask`: `CharField(max_length=30, help_text="Niqoblangan karta raqami (masalan 8600 12** **** 1234)")`
  - `card_holder`: `CharField(max_length=255, blank=True, null=True)`
  - `card_type`: `CharField(max_length=20, choices=CardType.choices)` (`UZCARD`, `HUMO`, `VISA`, `MASTERCARD`, `OTHER`)
  - `expire_month`: `CharField(max_length=2)`
  - `expire_year`: `CharField(max_length=4)`
  - `is_default`: `BooleanField(default=False)`
  - `is_verified`: `BooleanField(default=False, help_text="SMS OTP orqali tasdiqlanganlik holati")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`

- **Xususiyatlar**:
  - `UniqueConstraint`: bitta foydalanuvchida `provider` va `card_token` takrorlanmasligi.
  - `save()` metodida agar karta `is_default=True` qilinsa, foydalanuvchining boshqa kartalari avtomatik `is_default=False` bo'lishini ta'minlash.

---

## 4. `Order` va `Payment` Integratsiyasi & Tranzaksiyaviy Bog'liqlik

`Payment` modeli `Order` bilan to'liq sinxron holatda ishlaydi:
1. Buyurtma yaratilganda uning holati `PENDING` yoki `AWAITING_PAYMENT`, `payment_status` esa `PENDING` bo'ladi.
2. Mijoz to'lov shlyuzini tanlaganda `Payment` obyekti hosil qilinadi (`amount = order.total_price`, `provider = order.payment_method`).
3. To'lov amalga oshirilgach (`mark_as_success`), `Payment` obyekti avtomatik ravishda `order.mark_as_paid()` metodini ishga tushiradi.
4. Natijada `order.payment_status = PAID` va `order.status = CONFIRMED` holatiga o'tadi va bu `OrderStatusHistory` audit jadvalida yoziladi.
5. Agar to'lov muvaffaqiyatsiz bo'lsa (`mark_as_failed`), `order.payment_status = FAILED` holatiga o'tadi, ammo buyurtma bekor qilinmaydi (mijoz boshqa karta yoki tizim orqali qayta urinib ko'rishi mumkin).

---

## 5. Execution Checklist

- [x] Step 1: `apps/payments/models.py` faylida barcha modellarni (`Payment`, `PaymentTransaction`, `Refund`, `SavedCard`) yaratish
- [x] Step 2: `apps/payments/admin.py` faylida admin paneli konfiguratsiyasini tuzish (filtrlar, qidiruv, readonly audit maydonlar, inlines)
- [x] Step 3: `makemigrations` va `migrate` buyruqlarini bajarib, ma'lumotlar bazasida jadvallarni shakllantirish
- [x] Step 4: `apps/payments/tests/` paketida modellar, validatsiyalar, status o'tishlari, metodlar va Order bilan sinxronizatsiyani tekshiruvchi to'liq unit testlar yozish
- [x] Step 5: Testlarni ishga tushirish (`pytest` / `python manage.py test apps.payments`) va tizim yaxlitligini tekshirish (`python manage.py check`)
- [x] Step 6: Git commit va natijalarni foydalanuvchiga taqdim etish

---

## 6. Verification Plan

### Automated Tests
- `python manage.py check`: Django sozlamalari va modellar o'rtasidagi bog'liqlikni tekshirish
- `python manage.py test apps.payments`:
  - `Payment` raqami generatsiyasi va unikalligi
  - `Payment.mark_as_success()` chaqirilganda `Order.mark_as_paid()` sinxronizatsiyasi
  - `Payment.mark_as_failed()` va `mark_as_cancelled()` logikasi
  - `PaymentTransaction` so'rov va javob JSON snapshotlarini to'g'ri saqlashi
  - `Refund` to'liq va qisman pul qaytarish hisob-kitoblari va chegaraviy holatlar
  - `SavedCard` birlamchi karta (`is_default`) logikasi va unikal token cheklovi
- To'liq loyiha testlarini tekshirish: `python manage.py test`
