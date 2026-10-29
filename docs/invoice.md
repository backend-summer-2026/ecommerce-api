# Order Invoice — Texnik Dokumentatsiya

## Umumiy ma'lumot

Bu loyihada **alohida `Invoice` database modeli mavjud emas**.  
Invoice — bu mavjud `Order` ma'lumotlarini billing/chek formatida qaytaradigan **read-only API endpoint**.

> Invoice yangi object yaratmaydi — faqat Order'dagi ma'lumotlarni formatlaydi.

---

## Arxitektura

```
GET /api/v1/orders/<order_number>/invoice/
         │
         ▼
  OrderInvoiceView          (apps/orders/views.py)
         │
         ▼
  OrderInvoiceSerializer    (apps/orders/serializers/order_serializers.py)
         │
         ├── OrderAddressSerializer   (shipping_address)
         └── OrderItemSerializer      (items)
```

---

## Endpoint

| Metod | URL | Tavsif |
|-------|-----|--------|
| `GET` | `/api/v1/orders/<order_number>/invoice/` | Order uchun invoice (hisob-faktura) |

### Ruxsatlar

| Foydalanuvchi | Ruxsat |
|---------------|--------|
| Autentifikatsiyalanmagan | ❌ `401 Unauthorized` |
| O'z orderiga | ✅ Ko'ra oladi |
| Boshqa birovning orderiga | ❌ `404 Not Found` |
| Staff (admin) | ✅ Istalgan orderni ko'ra oladi |

---

## Request

```http
GET /api/v1/orders/ORD-20261029-A8F2K1/invoice/
Authorization: Bearer <access_token>
```

**Path parametr:**

| Parametr | Turi | Majburiy | Tavsif |
|----------|------|----------|--------|
| `order_number` | `string` | ✅ | Order raqami (masalan `ORD-20261029-A8F2K1`) |

---

## Response

### 200 OK — Muvaffaqiyatli javob

```json
{
  "order_number": "ORD-20261029-A8F2K1",
  "created_at": "2026-10-29T15:00:00Z",
  "paid_at": "2026-10-29T15:05:32Z",

  "customer_name": "Sardor Karimov",
  "customer_email": "sardor@example.com",
  "customer_phone": "+998901234567",

  "payment_method": "PAYME",
  "payment_status": "PAID",

  "shipping_method": "STANDARD",
  "shipping_address": {
    "id": 12,
    "recipient_name": "Sardor Karimov",
    "phone_number": "+998901234567",
    "alternative_phone_number": null,
    "region": "Tashkent",
    "district": "Yunusabad",
    "street_address": "Amir Temur ko'chasi, 15-uy",
    "apartment_office": "34",
    "postal_code": "100084",
    "landmark": "Yunusabad bozori yaqinida",
    "latitude": "41.299698",
    "longitude": "69.240073",
    "delivery_instructions": "Qo'ng'iroq qiling",
    "full_address": "Tashkent, Yunusabad, Amir Temur ko'chasi, 15-uy, Apt/Office: 34, Postal Code: 100084"
  },

  "items": [
    {
      "id": 101,
      "variant_id": 55,
      "product_name": "iPhone 15 Pro",
      "variant_sku": "IPH15PRO-256-BLK",
      "variant_attributes_display": "Color: Black Titanium | Storage: 256GB",
      "attributes_snapshot": {
        "Color": "Black Titanium",
        "Storage": "256GB"
      },
      "unit_price": "12000000.00",
      "quantity": 1,
      "total_price": "12000000.00",
      "image_url": "https://example.com/media/products/iphone15pro.jpg"
    },
    {
      "id": 102,
      "variant_id": 78,
      "product_name": "AirPods Pro 2",
      "variant_sku": "APPRO2-WHT",
      "variant_attributes_display": "Color: White",
      "attributes_snapshot": {
        "Color": "White"
      },
      "unit_price": "2500000.00",
      "quantity": 2,
      "total_price": "5000000.00",
      "image_url": "https://example.com/media/products/airpodspro2.jpg"
    }
  ],

  "total_items": 3,
  "subtotal": "17000000.00",
  "shipping_fee": "25000.00",
  "discount_amount": "1700000.00",
  "total_price": "15325000.00",
  "currency": "UZS"
}
```

### Response maydonlari

#### Asosiy maydonlar

| Maydon | Turi | Tavsif |
|--------|------|--------|
| `order_number` | `string` | Noyob order identifikatori |
| `created_at` | `datetime` | Order yaratilgan vaqt (ISO 8601) |
| `paid_at` | `datetime \| null` | To'lov amalga oshirilgan vaqt. To'lanmagan bo'lsa `null` |
| `currency` | `string` | Valyuta kodi (doim `UZS`) |

#### Mijoz ma'lumotlari

| Maydon | Turi | Tavsif |
|--------|------|--------|
| `customer_name` | `string` | Mijozning to'liq ismi (`user.full_name`) |
| `customer_email` | `string` | Mijoz email manzili |
| `customer_phone` | `string` | Mijoz telefon raqami |

#### To'lov va yetkazish

| Maydon | Turi | Mumkin qiymatlar |
|--------|------|-----------------|
| `payment_method` | `string` | `PAYME`, `CLICK`, `UZUM`, `CASH_ON_DELIVERY`, `CARD_ON_DELIVERY` |
| `payment_status` | `string` | `PENDING`, `PAID`, `PARTIALLY_REFUNDED`, `REFUNDED`, `FAILED` |
| `shipping_method` | `string` | `STANDARD`, `EXPRESS`, `PICKUP` |

#### Moliyaviy maydonlar

| Maydon | Turi | Tavsif |
|--------|------|--------|
| `subtotal` | `decimal` | Mahsulotlar jami narxi (yetkazish va chegirmasiz) |
| `shipping_fee` | `decimal` | Yetkazib berish narxi |
| `discount_amount` | `decimal` | Kupon yoki chegirma orqali tejangan summa |
| `total_price` | `decimal` | To'lanadigan yakuniy summa: `subtotal + shipping_fee - discount_amount` |

> **Hisob formulasi:**
> ```
> total_price = subtotal + shipping_fee - discount_amount
> ```

#### `shipping_address` obyekti

| Maydon | Turi | Tavsif |
|--------|------|--------|
| `recipient_name` | `string` | Qabul qiluvchi to'liq ismi |
| `phone_number` | `string` | Asosiy telefon raqam |
| `alternative_phone_number` | `string \| null` | Zaxira telefon raqam |
| `region` | `string` | Viloyat (masalan: `Tashkent`, `Samarkand`) |
| `district` | `string` | Tuman yoki shahar (masalan: `Mirabad`) |
| `street_address` | `string` | Ko'cha va uy raqami |
| `apartment_office` | `string \| null` | Xonadon yoki ofis raqami |
| `postal_code` | `string \| null` | Pochta indeksi |
| `landmark` | `string \| null` | Mo'ljal (mo'ljalga yaqin joy) |
| `latitude` | `decimal \| null` | GPS kenglik koordinatasi |
| `longitude` | `decimal \| null` | GPS uzunlik koordinatasi |
| `delivery_instructions` | `string \| null` | Kuryer uchun yo'riqnoma |
| `full_address` | `string` | Formatlangan to'liq manzil (computed property) |

#### `items` massivi elementlari

| Maydon | Turi | Tavsif |
|--------|------|--------|
| `id` | `integer` | OrderItem identifikatori |
| `variant_id` | `integer` | Mahsulot varianti ID |
| `product_name` | `string` | Mahsulot nomi (checkout vaqtidagi snapshot) |
| `variant_sku` | `string` | SKU kodi (checkout vaqtidagi snapshot) |
| `variant_attributes_display` | `string` | O'qilishi oson atributlar (`Color: Black \| Storage: 256GB`) |
| `attributes_snapshot` | `object` | JSON formatidagi atributlar snapshot |
| `unit_price` | `decimal` | Birlik narxi (checkout vaqtidagi snapshot) |
| `quantity` | `integer` | Miqdor |
| `total_price` | `decimal` | Qator jami: `unit_price × quantity` |
| `image_url` | `string \| null` | Mahsulot rasmi URL (variant yoki product media) |

---

### Xato holatlari

| HTTP Status | Sabab |
|-------------|-------|
| `401 Unauthorized` | Token yo'q yoki muddati o'tgan |
| `404 Not Found` | Order topilmadi yoki foydalanuvchiga tegishli emas |

---

## Kod tuzilmasi

### View — [`apps/orders/views.py`](../apps/orders/views.py)

```python
class OrderInvoiceView(APIView):
    """
    GET /api/v1/orders/<order_number>/invoice/
    Formatted receipt and invoice summary for billing and printing.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_number):
        prefetch_qs = Order.objects.select_related('shipping_address', 'user').prefetch_related(
            'items__variant__product__media',
            'items__variant__media',
        )

        if request.user.is_staff:
            order = get_object_or_404(prefetch_qs, order_number=order_number)
        else:
            order = get_object_or_404(prefetch_qs, order_number=order_number, user=request.user)

        serializer = OrderInvoiceSerializer(order, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
```

### Serializer — [`apps/orders/serializers/order_serializers.py`](../apps/orders/serializers/order_serializers.py)

```python
class OrderInvoiceSerializer(serializers.ModelSerializer):
    """
    Formatted invoice representation for billing, accounting, and printable receipts.
    """
    customer_name  = serializers.CharField(source='user.full_name', read_only=True)
    customer_email = serializers.CharField(source='user.email', read_only=True)
    customer_phone = serializers.CharField(source='user.phone_number', read_only=True)
    shipping_address = OrderAddressSerializer(read_only=True)
    items            = OrderItemSerializer(many=True, read_only=True)
    total_items      = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_number', 'created_at', 'paid_at',
            'customer_name', 'customer_email', 'customer_phone',
            'payment_method', 'payment_status',
            'shipping_method', 'shipping_address',
            'items', 'total_items',
            'subtotal', 'shipping_fee', 'discount_amount',
            'total_price', 'currency',
        ]
```

### URL — [`apps/orders/urls.py`](../apps/orders/urls.py)

```python
path('<str:order_number>/invoice/', OrderInvoiceView.as_view(), name='order-invoice'),
```

---

## Lifecycle: Invoice qachon mavjud bo'ladi?

```
Mijoz cart'ni checkout qiladi
          │
          ▼
    Order yaratiladi  ──────────────────────────────────────────────┐
    (status: PENDING yoki AWAITING_PAYMENT)                         │
          │                                                          │
          ▼                                                          │
  [To'lov usuli online: PAYME/CLICK/UZUM]                          │
  Payment to'lanadi → order.mark_as_paid()                         │
  → order.status: CONFIRMED                                         │
  → order.paid_at: <timestamp>                                      │
          │                                                          │
          ▼                                                    Invoice bu bosqichlarning
  [To'lov usuli offline: CASH/CARD ON DELIVERY]               barchasida GET orqali
  order.status: PENDING → PROCESSING → DELIVERED              mavjud bo'ladi ✅
  → order.paid_at: null (to'lov yetkazilganda belgilanadi)         │
          │                                                          │
          └──────────────────────────────────────────────────────────┘
```

> **Muhim:** Invoice endpoint order yaratilgan zahoti ishlaydi. `paid_at` field `null` bo'lishi mumkin — bu to'lov hali amalga oshirilmaganligini bildiradi.

---

## Tegishli endpointlar

| Endpoint | Tavsif |
|----------|--------|
| `POST /api/v1/orders/` | Yangi order yaratish (cart'dan) |
| `GET /api/v1/orders/<order_number>/` | Order to'liq ma'lumotlari |
| `GET /api/v1/orders/<order_number>/invoice/` | **Invoice (hisob-faktura)** |
| `GET /api/v1/orders/<order_number>/tracking/` | Order holati va tracking timeline |
| `POST /api/v1/orders/<order_number>/cancel/` | Orderni bekor qilish |
