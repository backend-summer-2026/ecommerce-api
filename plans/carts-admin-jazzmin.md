# Plan: Carts Django Admin Panelni Yaxshilash (`django-jazzmin` uchun)

## Metadata
- **Sarlavha**: `apps/carts/admin.py` ni `django-jazzmin` uchun takomillashtirish va optimallashtirish
- **Sana**: 2026-10-24
- **Holat**: YAKUNLANDI (Completed)
- **Filial**: `feat/carts-admin-jazzmin`
- **Fayl**: [apps/carts/admin.py](file:///Users/djumanov/network-school/Groups/NS26-BD-01/ecommerce/apps/carts/admin.py)

---

## 1. Muammo va Maqsad

Hozirgi [apps/carts/admin.py](file:///Users/djumanov/network-school/Groups/NS26-BD-01/ecommerce/apps/carts/admin.py) faylida standart Django admin konfiguratsiyasi minimal darajada qo'llanilgan:
1. **Vizual kamchiliklar**:
   - Savatcha holati (`status`) oddiy matn ko'rinishida, Jazzmin/Bootstrap 4 badjlari (`badge badge-success`, `badge badge-info`, `badge badge-warning` va h.k.) va FontAwesome piktogrammalari ishlatilmagan.
   - Foydalanuvchi va Mehmon (Guest) o'rtasida aniq vizual ajratish yo'q, foydalanuvchi profiliga bevosita havola mavjud emas.
   - Savatcha ichidagi tovarlar ro'yxatida (`CartItemInline`) mahsulotning rasmi (thumbnail) ko'rinmaydi.
   - Tovarlar zaxirasi holati va narx o'zgarishi indikatorlari yetarli darajada ko'rgazmali emas.
2. **UX va Boshqaruv Qulayligi**:
   - `autocomplete_fields` ishlatilmagan (variantlarni tanlashda sekin ishlaydigan `raw_id_fields` qo'llangan).
   - Foydali guruhli amallar (`admin.action`) mavjud emas (masalan, savatlarni "Tashlab ketilgan" (Abandoned) qilish yoki eski bo'sh savatlarni tozalash).
   - Mehmon yoki ro'yxatdan o'tgan foydalanuvchilar bo'yicha maxsus filtrlar yo'q.
   - Bo'sh savatlar yoki mavjud bo'lmagan tovarlari bor savatlarni ajratib ko'rsatish filtrlari mavjud emas.
3. **Unumdorlik (N+1 Query muammosi)**:
   - Ro'yxat sahifasida `total_items_display` va `total_price_display` chaqirilganda, har bir savat uchun alohida SQL so'rovlar bajariladi (50 ta savat ko'rsatilganda 100+ qo'shimcha so'rov vujudga keladi).
   - `get_queryset` da `select_related('user')` va `prefetch_related` yoki `annotate(Count(...))` optimizatsiyalari qo'llanmagan.

Ushbu reja doirasida [apps/carts/admin.py](file:///Users/djumanov/network-school/Groups/NS26-BD-01/ecommerce/apps/carts/admin.py) to'liq qayta ishlanib, `django-jazzmin` interfeysiga 100% mos, zamonaviy, qulay va yuqori unumdor boshqaruv paneliga aylantiriladi.

---

## 2. Rejalashtirilgan Yaxshilanishlar (Komponentlar kesimida)

### 2.1. `CartAdmin`
- **Holat badjlari (`status_badge`)**:
  - `OPEN`: `<span class="badge badge-success"><i class="fas fa-shopping-cart"></i> Ochiq (Open)</span>`
  - `MERGED`: `<span class="badge badge-info"><i class="fas fa-code-branch"></i> Birlashtirilgan (Merged)</span>`
  - `CONVERTED`: `<span class="badge badge-primary"><i class="fas fa-check-circle"></i> Xarid qilingan (Converted)</span>`
  - `ABANDONED`: `<span class="badge badge-secondary"><i class="fas fa-clock"></i> Tashlab ketilgan (Abandoned)</span>`
- **Egasi / Mijoz ko'rinishi (`customer_display`)**:
  - Ro'yxatdan o'tgan foydalanuvchi bo'lsa: `admin:users_user_change` havolasi bilan `<i class="fas fa-user-circle text-primary"></i> email`.
  - Mehmon (Guest) bo'lsa: `<span class="badge badge-light text-muted"><i class="fas fa-user-secret"></i> Mehmon (sessiya: {session_key[:8]}...)</span>`.
- **Savatcha ID ko'rinishi (`cart_id_display`)**:
  - Qisqa ID (`code` tegi bilan) va hover qilinganda to'liq UUID ko'rinadigan qulay format.
- **Moliyaviy ko'rsatkichlar**:
  - `total_price_display`: Qalin shrift bilan `<strong>120,000.00</strong> UZS`.
  - `subtotal_display`, `total_discount_display`: Chegirma mavjud bo'lsa, qizil badjda aks etadi.
- **Mavjudlik indikatori (`availability_badge`)**:
  - Barchasi mavjud bo'lsa: `<span class="badge badge-success"><i class="fas fa-check-circle"></i> Barchasi mavjud</span>`
  - Tugagan yoki faol bo'lmagan tovar bo'lsa: `<span class="badge badge-danger"><i class="fas fa-exclamation-triangle"></i> Muammoli tovarlar bor</span>`
- **Maydonlar guruhlanishi (`fieldsets`)**: Jazzmin `horizontal_tabs` ga moslab toza bo'limlarga ajratish:
  - *Savatcha Tafsilotlari*: `id`, `user`, `session_key`, `status`
  - *Moliyaviy Ko'rsatkichlar*: `total_items_display`, `unique_items_display`, `subtotal_display`, `total_discount_display`, `total_price_display`, `availability_badge`
  - *Tizim Vaqtlari*: `created_at`, `updated_at` (collapse)
- **Guruhli Amallar (`actions`)**:
  - `mark_as_abandoned`: Tanlangan savatlarni "Tashlab ketilgan" holatiga o'tkazish.
  - `mark_as_open`: Tanlangan savatlarni "Ochiq" holatiga qaytarish.
  - `clear_empty_carts`: Ichida hech qanday tovari bo'lmagan tanlangan savatlarni tozalash/o'chirish.
- **Filtrlar**:
  - `status` bo'yicha filtr.
  - `date_hierarchy = 'created_at'`.
  - `CartOwnerTypeFilter`: Ro'yxatdan o'tganlar / Mehmonlar savatini ajratish.
  - `CartHasItemsFilter`: Bo'sh savatlar va to'la savatlarni filtrlash.
- **N+1 Optimizatsiyasi**:
  - `get_queryset` da `select_related('user')`, `prefetch_related('items__variant__product', 'items__variant__inventory')` qo'llash va ro'yxat uchun hisob-kitoblarni annotatsiyalar orqali tezlashtirish.

### 2.2. `CartItemInline`
- **Mahsulot rasmi thumbnail (`product_thumbnail`)**: Mahsulotning asosiy media rasmi 40x40px o'lchamda chiroyli ramka bilan ko'rinadi (rasm bo'lmasa FontAwesome ikonkasi).
- **Variant Autocomplete**: `raw_id_fields` o'rniga Jazzmin Select2 qidiruvi bilan ishlaydigan `autocomplete_fields = ['variant']`.
- **Narx o'zgarishi ogohlantirishi (`price_status_display`)**:
  - Savatchaga qo'shilgan vaqtdagi narx bilan hozirgi narx farq qilsa (`is_price_changed`):
    `<span class="badge badge-warning" title="Eski: {unit_price_at_addition}, Yangi: {current_unit_price}"><i class="fas fa-tag"></i> Narx o'zgargan</span>`
- **Zaxira statusi (`stock_status_badge`)**:
  - Qoldiq miqdori bilan: `<span class="badge badge-success"><i class="fas fa-boxes"></i> Omborda bor ({stock} dona)</span>` yoki `<span class="badge badge-danger"><i class="fas fa-times-circle"></i> Tugagan</span>`.
- **Qator havolasi**: `show_change_link = True` orqali to'g'ridan-to'g'ri `CartItem` sahifasiga o'tish imkoniyati.

### 2.3. `CartItemAdmin` (Alohida Model Admini)
- `list_display`:
  - `id_display`, `cart_link`, `product_thumbnail`, `variant`, `quantity`, `unit_price_at_addition`, `current_unit_price_display`, `total_price_display`, `stock_status_badge`, `created_at`
- `autocomplete_fields = ['cart', 'variant']`.
- `search_fields = ('id', 'cart__id', 'cart__user__email', 'variant__sku', 'variant__title', 'variant__product__name')`.
- `list_filter = ('created_at', 'variant__is_active')`.
- `date_hierarchy = 'created_at'`.
- `get_queryset` da `select_related('cart__user', 'variant__product', 'variant__inventory')`.

---

## 3. Ketma-ket Amalga Oshirish Rejasi (Checklist)

- [x] **Bosqich 1: Git tarmog'i va muhitni sozlash**
  - `feat/carts-admin-jazzmin` tarmog'ida ishlashni tekshirish va tasdiqlash.
- [x] **Bosqich 2: Yordamchi HTML va Badj formatlovchi komponentlarni yaratish**
  - Jazzmin / Bootstrap 4 mos status badjlari, narx ko'rinishlari, foydalanuvchi havolalari va zaxira holati indikatorlarini ishlab chiqish.
- [x] **Bosqich 3: Maxsus Filtrlarni (`CartOwnerTypeFilter`, `CartHasItemsFilter`, `CartAvailabilityFilter`) yaratish**
  - Mehmon va ro'yxatdan o'tgan foydalanuvchilar hamda bo'sh/to'la savatlarni filtrlash uchun `admin.SimpleListFilter` larini qo'shish.
- [x] **Bosqich 4: `CartItemInline` ni yangilash**
  - Rasmlar prevyusi (thumbnail), `autocomplete_fields`, `show_change_link`, narx o'zgarishi va zaxira badjlarini sozlash.
- [x] **Bosqich 5: `CartAdmin` ni to'liq qayta ishlab modernizatsiya qilish**
  - Holat badjlari, mijoz havolalari, xavfsiz formatlar, guruhli amallar (`mark_as_abandoned`, `mark_as_open`, `clear_empty_carts`), `fieldsets` va `date_hierarchy` ni sozlash.
  - `get_queryset` da N+1 so'rovlarni yo'qotish uchun `select_related`, `prefetch_related` va annotatsiyalarni integratsiya qilish.
- [x] **Bosqich 6: `CartItemAdmin` ni takomillashtirish**
  - Ro'yxat, qidiruv maydonlari, `autocomplete_fields`, `select_related` bilan optimallashtirish.
- [x] **Bosqich 7: Testlar va sifat nazorati**
  - `python manage.py check` va `python manage.py test apps.carts` orqali admin va cart testlarini xatosiz o'tishini tekshirish.
- [x] **Bosqich 8: Yakuniy ko'rib chiqish va foydalanuvchiga taqdim etish**
  - Natijani umumlashtirish va tekshirish.
