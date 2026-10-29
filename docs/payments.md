# Payments — Texnik Dokumentatsiya

## Umumiy ma'lumot

Payment moduli quyidagi funksiyalarni qamrab oladi:

| Modul | Tavsif |
|-------|--------|
| **Payment** | To'lov sessiyasi yaratish, holat kuzatuvi |
| **PaymentTransaction** | Gateway bilan har bir muloqotning audit logi |
| **Refund** | To'liq yoki qisman pul qaytarish |
| **SavedCard** | Tokenlashtirilgan bank kartalar (1-click checkout) |
| **Webhooks** | Payme, Click, Uzum gateway callback'lari |

---

## Modellar

### `Payment` — To'lov

```
payment_number  : PAY-YYYYMMDD-XXXXXX   (auto-generated, unique)
order           : ForeignKey → Order     (PROTECT)
user            : ForeignKey → User      (SET_NULL)
amount          : Decimal                (to'lov summasi)
currency        : "UZS"
provider        : PAYME | CLICK | UZUM | CASH_ON_DELIVERY | CARD_ON_DELIVERY
status          : PENDING → PROCESSING → SUCCESS | FAILED | CANCELLED | REFUNDED
checkout_url    : gateway redirect URL
paid_at         : to'lov qilingan vaqt
```

**Payment statuslari:**

```
PENDING
   │
   ├─── (online gateway) ──► PROCESSING ──► SUCCESS ✅
   │                                    └──► FAILED ❌
   │
   ├─── (mijoz tomonidan) ──► CANCELLED 🚫
   │
   └─── (to'lovdan keyin refund) ──► PARTIALLY_REFUNDED | REFUNDED 💸
```

---

### `PaymentTransaction` — Gateway Audit Log

Har bir gateway muloqoti uchun yoziladi (CHECK, CREATE, PERFORM, CANCEL, REFUND, WEBHOOK).

```
payment         : ForeignKey → Payment
transaction_type: CHECK | CREATE | PERFORM | CANCEL | REFUND | WEBHOOK
amount          : Decimal
status          : PENDING | SUCCESS | FAILED
idempotency_key : takroriy so'rovlardan himoya
request_payload : gateway ga yuborilgan raw JSON
response_payload: gateway dan kelgan raw JSON
error_code      : xato kodi (agar FAILED bo'lsa)
ip_address      : so'rov yuboruvchi IP
```

---

### `Refund` — Pul qaytarish

```
refund_number   : REF-YYYYMMDD-XXXXXX   (auto-generated, unique)
payment         : ForeignKey → Payment   (PROTECT)
order           : ForeignKey → Order     (PROTECT)
amount          : Decimal                (qaytarilayotgan summa)
status          : PENDING → COMPLETED | FAILED | CANCELLED
reason          : qaytarish sababi
created_by      : admin user (SET_NULL)
processed_at    : qaytarish amalga oshirilgan vaqt
```

---

### `SavedCard` — Saqlangan karta

```
user        : ForeignKey → User
provider    : PAYME | CLICK | UZUM
card_token  : gateway token (karta raqami SAQLANMAYDI - PCI-DSS)
card_mask   : "8600 12** **** 1234"
card_type   : UZCARD | HUMO | VISA | MASTERCARD | OTHER
expire_month: "08"
expire_year : "2028"
is_default  : birlamchi karta
is_verified : SMS OTP orqali tasdiqlangan
```

---

## Arxitektura — To'lov oqimi

```
Mijoz ──► POST /payments/initialize/ ──► PaymentService.initialize_payment()
                                              │
                                    ┌─────────┴──────────┐
                              checkout_url                Payment(PENDING)
                                    │                          │
                              Mijoz gateway ga yo'naltiriladi  │
                                    │                          │
                    Gateway to'lovni amalga oshiradi           │
                                    │                          │
                    Webhook (Payme/Click/Uzum) ◄───────────────┘
                                    │
                     PaymentService.process_success()
                                    │
                    ┌───────────────┼───────────────┐
              payment.mark_as_success()    PaymentTransaction(PERFORM)
                    │
              order.mark_as_paid()
                    │
              order.status: CONFIRMED
              order.paid_at: <now>
                    │
              Notification (In-App + Email)
```

---

## Endpoints

### Mijoz endpointlari

| Metod | URL | Tavsif |
|-------|-----|--------|
| `POST` | `/api/v1/payments/initialize/` | To'lov sessiyasi yaratish |
| `GET` | `/api/v1/payments/` | O'z to'lovlar ro'yxati |
| `GET` | `/api/v1/payments/<payment_number>/` | To'lov tafsiloti |
| `POST` | `/api/v1/payments/<payment_number>/cancel/` | To'lovni bekor qilish |
| `POST` | `/api/v1/payments/pay-with-card/` | Saqlangan karta bilan 1-click to'lov |
| `GET` | `/api/v1/payments/cards/` | Saqlangan kartalar ro'yxati |
| `POST` | `/api/v1/payments/cards/` | Yangi karta qo'shish (OTP yuboriladi) |
| `POST` | `/api/v1/payments/cards/<pk>/verify/` | Kartani OTP orqali tasdiqlash |
| `POST` | `/api/v1/payments/cards/<pk>/default/` | Kartani asosiy qilib belgilash |
| `DELETE` | `/api/v1/payments/cards/<pk>/` | Kartani o'chirish |

### Gateway Webhook endpointlari (server-to-server)

| Metod | URL | Gateway |
|-------|-----|---------|
| `POST` | `/api/v1/payments/webhooks/payme/` | Payme JSON-RPC 2.0 |
| `POST` | `/api/v1/payments/webhooks/click/` | Click Prepare & Complete |
| `POST` | `/api/v1/payments/webhooks/uzum/` | Uzum Bank callback |

### Admin endpointlari

| Metod | URL | Tavsif |
|-------|-----|--------|
| `GET` | `/api/v1/payments/admin/` | Barcha to'lovlar (filter, pagination) |
| `GET` | `/api/v1/payments/admin/<payment_number>/` | To'lov + transactions + refunds |
| `POST` | `/api/v1/payments/admin/<payment_number>/refund/` | Refund yaratish |
| `GET` | `/api/v1/payments/admin/refunds/` | Barcha refundlar ro'yxati |
| `GET` | `/api/v1/payments/admin/refunds/<refund_number>/` | Refund tafsiloti |
| `GET` | `/api/v1/payments/admin/transactions/` | Gateway audit loglari |

---

## 1. To'lovni Ishga Tushirish

### `POST /api/v1/payments/initialize/`

**Ruxsatlar:** Faqat autentifikatsiyalangan foydalanuvchi.

**Request:**
```http
POST /api/v1/payments/initialize/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "order_number": "ORD-20261029-A8F2K1",
  "provider": "PAYME",
  "return_url": "https://myapp.uz/payment/callback"
}
```

**Request maydonlari:**

| Maydon | Turi | Majburiy | Tavsif |
|--------|------|----------|--------|
| `order_number` | `string` | ✅ | To'lanadigan order raqami |
| `provider` | `string` | ✅ | `PAYME`, `CLICK`, `UZUM`, `CASH_ON_DELIVERY`, `CARD_ON_DELIVERY` |
| `return_url` | `url` | ❌ | To'lovdan keyin redirect URL |

**Response `201 Created`:**
```json
{
  "id": 42,
  "payment_number": "PAY-20261029-8F9B2C",
  "order_number": "ORD-20261029-A8F2K1",
  "order": {
    "order_number": "ORD-20261029-A8F2K1",
    "status": "AWAITING_PAYMENT",
    "payment_status": "PENDING",
    "total_price": "15325000.00",
    "currency": "UZS"
  },
  "amount": "15325000.00",
  "currency": "UZS",
  "provider": "PAYME",
  "provider_display": "Payme",
  "status": "PENDING",
  "status_display": "Pending",
  "checkout_url": "https://checkout.paycom.uz/base64encodedstring",
  "provider_transaction_id": null,
  "provider_state": null,
  "fee_amount": "0.00",
  "refunded_amount": "0.00",
  "metadata": {},
  "failure_reason": null,
  "paid_at": null,
  "failed_at": null,
  "cancelled_at": null,
  "created_at": "2026-10-29T15:10:00Z",
  "updated_at": "2026-10-29T15:10:00Z"
}
```

> **`checkout_url`** — mijoz shu havolaga o'tib to'lovni amalga oshiradi (Payme/Click/Uzum sahifasi).

---

## 2. To'lovlar Ro'yxati

### `GET /api/v1/payments/`

**Query parametrlar:**

| Parametr | Turi | Tavsif |
|----------|------|--------|
| `status` | `string` | `PENDING`, `SUCCESS`, `FAILED`, `CANCELLED`, `REFUNDED` |
| `provider` | `string` | `PAYME`, `CLICK`, `UZUM` va boshqalar |
| `search` | `string` | `payment_number` yoki `order_number` bo'yicha qidiruv |

**Response `200 OK`:**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 42,
      "payment_number": "PAY-20261029-8F9B2C",
      "order_number": "ORD-20261029-A8F2K1",
      "amount": "15325000.00",
      "currency": "UZS",
      "provider": "PAYME",
      "provider_display": "Payme",
      "status": "SUCCESS",
      "status_display": "Success",
      "checkout_url": null,
      "paid_at": "2026-10-29T15:12:45Z",
      "created_at": "2026-10-29T15:10:00Z"
    }
  ]
}
```

---

## 3. To'lovni Bekor Qilish

### `POST /api/v1/payments/<payment_number>/cancel/`

Faqat `PENDING` statusdagi to'lovni bekor qilish mumkin.

**Request:**
```json
{
  "reason": "Mijoz tomonidan bekor qilindi"
}
```

**Response `200 OK`:**
```json
{
  "detail": "Payment PAY-20261029-8F9B2C cancelled successfully.",
  "payment": { "...payment detail..." }
}
```

**Xato holatlari:**

| HTTP Status | Sabab |
|-------------|-------|
| `400 Bad Request` | To'lov `PENDING` emas (masalan, allaqachon `SUCCESS`) |
| `404 Not Found` | To'lov topilmadi yoki sizniki emas |

---

## 4. Saqlangan Kartalar (1-Click Checkout)

### Karta qo'shish — `POST /api/v1/payments/cards/`

```http
POST /api/v1/payments/cards/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "card_number": "8600123456781234",
  "expire_month": "08",
  "expire_year": "2028",
  "card_holder": "SARDOR KARIMOV",
  "provider": "PAYME"
}
```

> ⚠️ Karta raqami **hech qachon bazada saqlanmaydi** (PCI-DSS talabi).  
> Faqat `card_mask` va gateway `card_token` saqlanadi.

**Response `201 Created`:**
```json
{
  "detail": "Card registered. Please enter the OTP code sent via SMS to verify.",
  "card": {
    "id": 7,
    "provider": "PAYME",
    "provider_display": "Payme",
    "card_mask": "8600 12** **** 1234",
    "card_holder": "SARDOR KARIMOV",
    "card_type": "UZCARD",
    "card_type_display": "Uzcard",
    "expire_month": "08",
    "expire_year": "2028",
    "is_default": true,
    "is_verified": false,
    "created_at": "2026-10-29T15:15:00Z"
  },
  "otp_code": "482931"
}
```

---

### Kartani Tasdiqlash — `POST /api/v1/payments/cards/<pk>/verify/`

```json
{ "otp_code": "482931" }
```

**Response `200 OK`:**
```json
{
  "detail": "Card verified successfully and activated for 1-click checkout.",
  "card": { "...is_verified: true..." }
}
```

---

### 1-Click To'lov — `POST /api/v1/payments/pay-with-card/`

```json
{
  "order_number": "ORD-20261029-A8F2K1",
  "card_id": 7
}
```

**Response `200 OK`:**
```json
{
  "detail": "Order ORD-20261029-A8F2K1 paid successfully.",
  "payment": { "...status: SUCCESS, paid_at: ..." }
}
```

---

## 5. Gateway Webhooklar

### Payme — `POST /api/v1/payments/webhooks/payme/`

Payme **JSON-RPC 2.0** protokolida ishlaydi. Quyidagi methodlarni qabul qiladi:

| Method | Tavsif |
|--------|--------|
| `CheckPerformTransaction` | Buyurtma to'lanishi mumkinligini tekshirish |
| `CreateTransaction` | Payme trafida tranzaksiya ochish |
| `PerformTransaction` | To'lovni amalga oshirish |
| `CancelTransaction` | Tranzaksiyani bekor qilish |
| `CheckTransaction` | Tranzaksiya holatini so'rash |

**Autentifikatsiya:** HTTP Basic `Authorization: Basic <base64(merchant_id:key)>`

**Namuna request:**
```json
{
  "id": 1,
  "method": "PerformTransaction",
  "params": {
    "id": "payme_transaction_id_123"
  }
}
```

---

### Click — `POST /api/v1/payments/webhooks/click/`

Click **Prepare** va **Complete** ikki bosqichli protokolida ishlaydi.

| `action` | Tavsif |
|----------|--------|
| `0` | Prepare — to'lovni tekshirish |
| `1` | Complete — to'lovni yakunlash |

---

### Uzum — `POST /api/v1/payments/webhooks/uzum/`

Uzum Bank webhook'ini `X-Uzum-Signature` header orqali imzolash bilan autentifikatsiya qiladi.

---

## 6. Refund (Pul Qaytarish)

### `POST /api/v1/payments/admin/<payment_number>/refund/`

**Ruxsatlar:** Faqat **staff** (admin).

**Request:**
```json
{
  "amount": "5000000.00",
  "reason": "Mahsulot qaytarildi",
  "provider_refund_id": "payme_ref_abc123"
}
```

**Request maydonlari:**

| Maydon | Turi | Majburiy | Tavsif |
|--------|------|----------|--------|
| `amount` | `decimal` | ✅ | Qaytariladigan summa (≤ to'lanmagan qoldiq) |
| `reason` | `string` | ❌ | Qaytarish sababi |
| `provider_refund_id` | `string` | ❌ | Gateway refund ID (agar oldindan ruxsat olingan bo'lsa) |

**Response `201 Created`:**
```json
{
  "id": 3,
  "refund_number": "REF-20261029-7A3C1D",
  "payment_number": "PAY-20261029-8F9B2C",
  "order_number": "ORD-20261029-A8F2K1",
  "amount": "5000000.00",
  "currency": "UZS",
  "status": "COMPLETED",
  "status_display": "Completed",
  "reason": "Mahsulot qaytarildi",
  "provider_refund_id": "payme_ref_abc123",
  "created_by_username": "admin",
  "processed_at": "2026-10-29T16:00:00Z",
  "metadata": {},
  "created_at": "2026-10-29T16:00:00Z",
  "updated_at": "2026-10-29T16:00:00Z"
}
```

**Refund logikasi:**

| Holat | Payment Status | Order Payment Status |
|-------|---------------|---------------------|
| Qisman refund (`amount < payment.amount`) | `PARTIALLY_REFUNDED` | `PARTIALLY_REFUNDED` |
| To'liq refund (`amount == payment.amount`) | `REFUNDED` | `REFUNDED` |

---

## 7. Admin — To'lov Tafsiloti

### `GET /api/v1/payments/admin/<payment_number>/`

Admin uchun kengaytirilgan response — `transactions` va `refunds` ham kiritilgan:

```json
{
  "id": 42,
  "payment_number": "PAY-20261029-8F9B2C",
  "...payment fields...",
  "transactions": [
    {
      "id": 1,
      "transaction_type": "CREATE",
      "amount": "15325000.00",
      "status": "SUCCESS",
      "idempotency_key": "INIT_PAY-20261029-8F9B2C",
      "request_payload": { "order_number": "ORD-20261029-A8F2K1", "provider": "PAYME" },
      "response_payload": { "checkout_url": "https://checkout.paycom.uz/..." },
      "created_at": "2026-10-29T15:10:00Z"
    },
    {
      "id": 2,
      "transaction_type": "PERFORM",
      "amount": "15325000.00",
      "status": "SUCCESS",
      "idempotency_key": "payme_trans_id_xxx",
      "created_at": "2026-10-29T15:12:45Z"
    }
  ],
  "refunds": []
}
```

---

## 8. Xizmat Sathi (Service Layer)

### `PaymentService`

| Metod | Tavsif |
|-------|--------|
| `initialize_payment()` | To'lov yaratish, checkout URL generatsiya qilish |
| `process_success()` | To'lovni SUCCESS ga o'tkazish, Orderni yangilash, bildirishnomalar yuborish |
| `process_failure()` | FAILED, xato logi yozish, mijozga xabar |
| `process_cancellation()` | CANCELLED, audit logi |

### `RefundService`

| Metod | Tavsif |
|-------|--------|
| `process_refund()` | Refund yaratish, Payment va Order statusini yangilash, bildirishnomalar |

### `SavedCardService`

| Metod | Tavsif |
|-------|--------|
| `add_card()` | Kartani ro'yxatga olish, OTP generatsiya qilish (cache, 10 daqiqa) |
| `verify_card()` | OTP tekshirish, kartani faollashtirish |
| `set_default_card()` | Asosiy kartani o'zgartirish |
| `delete_card()` | Kartani o'chirish, keyingisini default qilish |
| `charge_saved_card()` | 1-click to'lov amalga oshirish |

---

## 9. Xato Holatlari

| HTTP Status | Sabab |
|-------------|-------|
| `401 Unauthorized` | Token yo'q yoki muddati o'tgan |
| `403 Forbidden` | Ruxsat yo'q (masalan, staff bo'lmagan refund so'rayapti) |
| `404 Not Found` | Payment/Card topilmadi yoki sizniki emas |
| `400 Bad Request` | Noto'g'ri input (to'lov allaqachon amalga oshirilgan, karta tasdiqlanmagan va h.k.) |

---

## 10. Tegishli Endpointlar

| Endpoint | Tavsif |
|----------|--------|
| `POST /api/v1/orders/` | Order yaratish (kartdan) |
| `GET /api/v1/orders/<order_number>/` | Order holati va to'lov statusi |
| `GET /api/v1/orders/<order_number>/invoice/` | Hisob-faktura (billing chek) |
| `POST /api/v1/payments/initialize/` | **To'lov boshlash** |
| `POST /api/v1/payments/pay-with-card/` | **1-click to'lov** |
