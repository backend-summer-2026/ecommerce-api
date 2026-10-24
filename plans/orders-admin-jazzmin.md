# Plan: Orders Django Admin Panelni Yaxshilash (`django-jazzmin` uchun)

## Metadata
- **Sarlavha**: `apps/orders/admin.py` ni `django-jazzmin` uchun takomillashtirish va optimallashtirish
- **Sana**: 2026-10-24
- **Holat**: REJALASHTIRILGAN (Kutish rejimida: Foydalanuvchi tasdig'i talab etiladi)
- **Filial**: `feat/orders-admin-jazzmin`
- **Fayl**: [apps/orders/admin.py](file:///Users/djumanov/network-school/Groups/NS26-BD-01/ecommerce/apps/orders/admin.py)

---

## 1. Muammo va Maqsad

Hozirgi [apps/orders/admin.py](file:///Users/djumanov/network-school/Groups/NS26-BD-01/ecommerce/apps/orders/admin.py) faylida standart Django admin konfiguratsiyasi qo'llanilgan, biroq `django-jazzmin` boshqaruv mavzusi va zamonaviy e-commerce admin panellari talablariga to'liq moslashtirilmagan:
1. **Vizual va UI kamchiliklar**:
   - Buyurtma holatlari (`status`) va to'lov holatlari (`payment_status`) oddiy inline-style orqali berilgan, Jazzmin va Bootstrap 4 ning standart badjlari (`badge badge-*`) hamda FontAwesome piktogrammalari bilan boyitilmagan.
   - Foydalanuvchi (`user`) oddiy email sifatida chiqadi, foydalanuvchi tahrirlash sahifasiga (`admin:users_user_change`) to'g'ridan-to'g'ri o'tish havolasi va mehmonlar (guest) uchun maxsus belgi yo'q.
   - Manzil ma'lumotlarida telefon raqami uchun `tel:` havolasi va GPS koordinatalari (kenglik/uzunlik) mavjud bo'lganda xaritada ochish imkoniyati (Google Maps / Yandex Maps) yo'q.
   - Buyurtma tarixi (`OrderStatusHistoryInline`) oddiy matn jadvali bo'lib, eski va yangi statuslar badjlarda ko'rinmaydi.
2. **UX va Boshqaruv Qulayligi (Ish unumdorligi)**:
   - Buyurtmalar bilan ishlovchi menejerlar uchun eng muhim bo'lgan tezkor amallar (`admin.action`) yo'q: buyurtmani bir bosish bilan tasdiqlash (`Confirmed`), tayyorlashga o'tkazish (`Processing`), jo'natish (`Shipped`), yetkazildi deb belgilash (`Delivered`), to'langan deb belgilash (`Paid`) yoki xavfsiz bekor qilish (`Cancelled`).
   - Jazzmin'ning qulay gorizontal tablar (`changeform_format = "horizontal_tabs"`) imkoniyati to'liq ochilmagan.
   - Kuponlar bo'yicha ularni ommaviy faollashtirish va faolsizlantirish amallari, qulay amal qilish muddati indikatori (faol, muddati o'tgan, kelgusi) yo'q.
3. **Unumdorlik (N+1 Query muammosi)**:
   - Ro'yxat sahifasida `shipping_address`, `user`, `coupon`, `cart` bilan bog'liq ma'lumotlar olinayotganda `select_related` to'liq qo'llanmagan.
   - Sanalar bo'yicha tezkor navigatsiya (`date_hierarchy = 'created_at'`) yo'q.

Ushbu reja orqali [apps/orders/admin.py](file:///Users/djumanov/network-school/Groups/NS26-BD-01/ecommerce/apps/orders/admin.py) to'liq modernizatsiya qilinib, `django-jazzmin` interfeysiga 100% mos, zamonaviy, vizual jihatdan chiroyli va qulay boshqaruv paneliga aylantiriladi.

---

## 2. Rejalashtirilgan Yaxshilanishlar (Komponentlar kesimida)

### 2.1. `OrderAdmin`
- **Tabli struktura (`changeform_format = "horizontal_tabs"`)**:
  - `📋 Buyurtma identifikatsiyasi`: `order_number`, `user`, `customer_link`, `cart`, `coupon`, `tracking_number`
  - `🔄 Holat va Yetkazib berish`: `status`, `payment_status`, `payment_method`, `shipping_method`
  - `💰 Moliyaviy hisob-kitob`: `subtotal_display`, `shipping_fee`, `discount_amount`, `total_price_display`, `currency`
  - `📝 Izohlar va Eslatmalar`: `customer_notes`, `admin_notes`, `cancellation_reason`
  - `⏱ Tizim vaqtlari (Audit)`: `paid_at`, `delivered_at`, `cancelled_at`, `created_at`, `updated_at` (collapse)
- **Zamonaviy Badjlar (Jazzmin / Bootstrap 4 + FontAwesome)**:
  - `status_badge`:
    - `PENDING`: `<span class="badge badge-warning"><i class="fas fa-clock mr-1"></i> Kutilyapti</span>`
    - `AWAITING_PAYMENT`: `<span class="badge badge-info"><i class="fas fa-hourglass-half mr-1"></i> To'lov kutilmoqda</span>`
    - `CONFIRMED`: `<span class="badge badge-primary"><i class="fas fa-check-circle mr-1"></i> Tasdiqlangan</span>`
    - `PROCESSING`: `<span class="badge badge-secondary"><i class="fas fa-box mr-1"></i> Tayyorlanmoqda</span>`
    - `SHIPPED`: `<span class="badge badge-dark"><i class="fas fa-shipping-fast mr-1"></i> Yetkazilmoqda</span>`
    - `DELIVERED`: `<span class="badge badge-success"><i class="fas fa-check-double mr-1"></i> Yetkazib berildi</span>`
    - `CANCELLED`: `<span class="badge badge-danger"><i class="fas fa-times-circle mr-1"></i> Bekor qilingan</span>`
    - `REFUNDED`: `<span class="badge badge-secondary"><i class="fas fa-undo mr-1"></i> Qaytarilgan</span>`
  - `payment_status_badge`:
    - `PAID`: `<span class="badge badge-success"><i class="fas fa-check-circle mr-1"></i> To'langan</span>`
    - `PENDING`: `<span class="badge badge-warning"><i class="fas fa-clock mr-1"></i> Kutilmoqda</span>`
    - `PARTIALLY_REFUNDED`: `<span class="badge badge-info"><i class="fas fa-adjust mr-1"></i> Qisman qaytarilgan</span>`
    - `REFUNDED`: `<span class="badge badge-secondary"><i class="fas fa-undo mr-1"></i> Qaytarilgan</span>`
    - `FAILED`: `<span class="badge badge-danger"><i class="fas fa-exclamation-triangle mr-1"></i> Xatolik</span>`
  - `payment_method_badge` & `shipping_method_badge`:
    - To'lov va yetkazib berish usullari uchun chiroyli piktogrammali badjlar (Payme, Click, Uzum, Naqd pul, Karta).
- **Mijoz ko'rinishi (`customer_display`)**:
  - Ro'yxatdan o'tgan foydalanuvchi bo'lsa: `admin:users_user_change` ga bevosita havola va ism/email.
  - Mehmon (Guest) bo'lsa: `<span class="badge badge-light border"><i class="fas fa-user-secret"></i> Mehmon (Ism)</span>`.
- **Tezkor Guruhli Amallar (`actions`)**:
  - `mark_as_confirmed`: Tanlangan buyurtmalarni tasdiqlash (`CONFIRMED`).
  - `mark_as_processing`: Tanlangan buyurtmalarni tayyorlashga o'tkazish (`PROCESSING`).
  - `mark_as_shipped`: Tanlangan buyurtmalarni yetkazishga jo'natish (`SHIPPED`).
  - `mark_as_delivered`: Tanlangan buyurtmalarni yetkazilgan deb belgilash (`DELIVERED`).
  - `mark_as_paid`: Tanlangan buyurtmalarni to'langan deb belgilash (`order.mark_as_paid(user=request.user)`).
  - `cancel_orders`: Tanlangan bekor qilish mumkin bo'lgan buyurtmalarni bekor qilish (`order.cancel(...)`).
- **N+1 Optimizatsiyasi & Navigatsiya**:
  - `list_select_related = ('user', 'coupon', 'cart')`
  - `date_hierarchy = 'created_at'`
  - `list_per_page = 25`

### 2.2. Inlines (`OrderItemInline`, `OrderAddressInline`, `OrderStatusHistoryInline`)
- **`OrderItemInline` (TabularInline)**:
  - Tovar nomi, varianti va SKU ma'lumotlari.
  - Birlik narxi va qator umumiy narxi chiroyli formatda (`150,000 UZS`).
  - Variant tahrirlash sahifasiga o'tish uchun qulay havola (`show_change_link = True`).
- **`OrderAddressInline` (StackedInline)**:
  - Qabul qiluvchi shaxs va telefon raqamlari (to'g'ridan-to'g'ri qo'ng'iroq uchun `tel:` havolasi bilan).
  - To'liq manzil ko'rinishi.
  - GPS koordinatalari mavjud bo'lsa: Google Maps / Yandex Maps da ochish tugmasi (`btn btn-xs btn-outline-primary`).
- **`OrderStatusHistoryInline` (TabularInline)**:
  - Eski va yangi holatlar uchun rangli badjlar (`old_status_badge`, `new_status_badge`).
  - Amalni kim bajarganligi (`created_by` yoki "Tizim (Avtomatik)").
  - Xronologik teskari tartib (`-created_at`).

### 2.3. `CouponAdmin` & `CouponUsageAdmin`
- **`CouponAdmin`**:
  - `changeform_format = "horizontal_tabs"`
  - Faollik holati badji: `is_active_badge` (`<span class="badge badge-success"><i class="fas fa-check"></i> Faol</span>` / `<span class="badge badge-danger"><i class="fas fa-times"></i> Nofaol</span>`).
  - Chegirma turi va qiymati badji (foiz yoki qat'iy summa).
  - Ishlatilish ko'rsatkichi (`used_count / limit`).
  - Amal qilish muddati va statusi (Faol, Muddati o'tgan, Kelgusida).
  - Ommaviy amallar: `activate_coupons`, `deactivate_coupons`.
  - `date_hierarchy = 'valid_from'`.
- **`CouponUsageAdmin`**:
  - `list_select_related = ('coupon', 'user', 'order')`.
  - Kupon, mijoz va buyurtmaga to'g'ridan-to'g'ri havolalar.
  - `has_add_permission = False` (audit jurnali bo'lgani sababli faqat o'qish rejimi).
  - `date_hierarchy = 'used_at'`.

---

## 3. Ketma-ket Amalga Oshirish Rejasi (Checklist)

- [x] **Bosqich 1: Git tarmog'i va muhitni sozlash**
  - `feat/orders-admin-jazzmin` tarmog'ida ishlashni tekshirish va tasdiqlash.
- [x] **Bosqich 2: Yordamchi HTML va Badj formatlovchi komponentlarni yaratish**
  - Jazzmin / Bootstrap 4 ga mos `status_badge`, `payment_status_badge`, `payment_method_badge`, `shipping_method_badge`, `customer_display`, `price_display` yordamchilarini ishlab chiqish.
- [x] **Bosqich 3: Inlinelarni (`OrderItemInline`, `OrderAddressInline`, `OrderStatusHistoryInline`) yangilash**
  - `OrderItemInline` ga valyuta formatlash va variant havolasini qo'shish.
  - `OrderAddressInline` ga telefon va xarita havolalarini qo'shish.
  - `OrderStatusHistoryInline` ga status o'zgarish badjlarini qo'shish.
- [x] **Bosqich 4: `OrderAdmin` ni to'liq qayta ishlab modernizatsiya qilish**
  - Gorizontal tablar (`changeform_format`), badjlar, N+1 so'rovlar optimizatsiyasi (`list_select_related`), `date_hierarchy` va guruhli amallarni (`mark_as_confirmed`, `mark_as_processing`, `mark_as_shipped`, `mark_as_delivered`, `mark_as_paid`, `cancel_orders`) qo'shish.
- [x] **Bosqich 5: `CouponAdmin` va `CouponUsageAdmin` ni modernizatsiya qilish**
  - Kupon badjlari, limit va foydalanish foizi, amal qilish holati, `activate_coupons`/`deactivate_coupons` amallari va `list_select_related` optimizatsiyasini kiritish.
- [x] **Bosqich 6: Avtomatlashtirilgan testlar to'plamini yozish (`apps/orders/tests/test_admin.py`)**
  - Admin ro'yxatdan o'tganligini, barcha display metodlari xatosiz ishlashini va amallar buyurtma statuslarini to'g'ri yangilashini test qilish.
- [x] **Bosqich 7: Django tizim tekshiruvi va testlarni muvaffaqiyatli o'tkazish**
  - `python manage.py check` va `python manage.py test apps.orders` orqali to'liq tekshirish.
