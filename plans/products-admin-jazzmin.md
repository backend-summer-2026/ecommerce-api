# Plan: Django Admin Panelni Yaxshilash (`django-jazzmin` uchun)

## Metadata
- **Sarlavha**: `apps/products/admin.py` ni `django-jazzmin` uchun takomillashtirish va optimallashtirish
- **Sana**: 2026-10-24
- **Holat**: YAKUNLANDI (Barcha bosqichlar muvaffaqiyatli amalga oshirildi)
- **Filial**: `refactor/products-admin-jazzmin`
- **Fayl**: [apps/products/admin.py](file:///Users/djumanov/network-school/Groups/NS26-BD-01/ecommerce/apps/products/admin.py)

---

## 1. Muammo va Maqsad

Hozirgi `apps/products/admin.py` faylida Django standart admin imkoniyatlarining minimal qismi ishlatilgan:
1. **Vizual kamchiliklar**:
   - Rasmlar (mahsulot, kategoriya, brend, media) ro'yxatlarda va inlinelarda ko'rinmaydi.
   - Narxlar, zaxira (stock) holati, chegirmalar oddiy matn yoki oddiy HTML ko'rinishida, Jazzmin/Bootstrap 4 komponentlari (`badge`, `pill`, `fa-*` ikonkalari) bilan bezatilmagan.
2. **UX va boshqaruv qulayligi**:
   - Qatorlarda tezkor o'zgartirish (`list_editable`) yo'q (narx, faollik, zaxira soni kabilarni har bir obyekt sahifasiga kirmasdan o'zgartirib bo'lmaydi).
   - Foreign key maydonlarida `autocomplete_fields` yetarli darajada kiritilmagan (`Brand` mahsulotda, `Parent` toifada).
   - Foydali guruhli amallar (`admin.action`) yo'q (mahsulotlarni yoqish/o'chirish, zaxira sozlamalari).
   - Zaxira (Inventory) bo'yicha maxsus holat filtrlari (tugagan, oz qolgan, mavjud) mavjud emas.
3. **Unumdorlik (N+1 Query muammosi)**:
   - Mahsulotlar, variantlar va zaxiralar ro'yxatida bog'langan jadvallar (`brand`, `category`, `product`, `inventory`, `media`) uchun `select_related` va `prefetch_related` ishlatilmagani sababli har bir satr uchun alohida SQL so'rovlar bajariladi.

Ushbu reja orqali [apps/products/admin.py](file:///Users/djumanov/network-school/Groups/NS26-BD-01/ecommerce/apps/products/admin.py) to'liq qayta ishlanib, `django-jazzmin` interfeysiga 100% mos, chiroyli va tezkor boshqaruv paneliga aylantiriladi.

---

## 2. Rejalashtirilgan Yaxshilanishlar (Komponentlar kesimida)

### 2.1. `ProductAdmin`
- **Rasm prevyusi (`thumbnail_preview`)**: Ro'yxatda mahsulotning asosiy rasmi (45x45px yumaloq ramkali thumbnail), rasm bo'lmasa qulay ikonka.
- **Narx diapazoni (`price_range_display`)**: Mahsulot variantlaridagi minimal va maksimal narxlar ko'rinishi (masalan: `$19.99 — $49.99`).
- **Variantlar soni badji (`variants_count_badge`)**: Bootstrap badjida variantlar soni (`<span class="badge badge-info"><i class="fas fa-boxes"></i> 3 ta</span>`).
- **Umumiy zaxira statusi (`stock_status_badge`)**: Mahsulot barcha variantlarining umumiy qoldig'iga qarab yashil/sariq/qizil rangli badj.
- **Tezkor tahrirlash (`list_editable`)**: Ro'yxatning o'zidan mahsulotni faol/nofaol qilish (`is_active`).
- **Guruhli amallar (`actions`)**: Tanlangan mahsulotlarni ommaviy faollashtirish va faolsizlantirish.
- **Maydonlar guruhlanishi (`fieldsets`)**: Jazzmin `horizontal_tabs` ga moslab toza bo'limlarga ajratish:
  - *Asosiy ma'lumotlar*: `name`, `slug`, `brand`, `is_active`
  - *Tavsiflar*: `short_description`, `description`
  - *Tizim vaqt ma'lumotlari*: `created_at`, `updated_at` (collapse)
- **N+1 optimizatsiyasi**: `get_queryset` da `select_related('brand')`, `prefetch_related('categories', 'variants__inventory', 'media')` qo'llash.

### 2.2. `ProductVariantAdmin`
- **Rasm ko'rinishi**: Variant yoki asosiy mahsulot rasmi thumbnail ko'rinishida.
- **Narx va chegirma vizuali**: Chegirma mavjud bo'lsa, asl narx ustidan chizilgan va chegirma badji (`badge badge-danger -15%`).
- **Zaxira badjlari**: `badge badge-success` (Yetarli), `badge badge-warning` (Kam qolgan), `badge badge-danger` (Tugagan).
- **Asosiy variant badji**: `badge badge-primary` bilan ko'rsatish (`<i class="fas fa-star"></i> Asosiy`).
- **Tezkor tahrirlash (`list_editable`)**: `price`, `discount_price`, `is_active`, `is_default` to'g'ridan-to'g'ri jadvalda o'zgartirilishi mumkin.
- **N+1 optimizatsiyasi**: `select_related('product', 'inventory')` va `prefetch_related('attributes', 'media')`.

### 2.3. `InventoryAdmin`
- **Zaxira holati filtri (`StockStatusFilter`)**:
  - Sotuvda mavjud (`available > low_stock_threshold`)
  - Oz qolgan (`0 < available <= low_stock_threshold`)
  - Tugagan (`available == 0`)
  - Band qilingan qismi mavjud (`reserved_quantity > 0`)
- **Tezkor tahrirlash (`list_editable`)**: `quantity` va `low_stock_threshold` to'g'ridan-to'g'ri jadvaldan o'zgartirilishi mumkin.
- **Mavjud va band qilingan zaxira ko'rsatkichi**: Aniq va tushunarli badjlar.
- **Amallar**: Band qilingan miqdorlarni nolga tushirish yoki zaxirani to'ldirish amali.

### 2.4. `CategoryAdmin` & `BrandAdmin`
- **Rasm/Logo prevyusi**: Toifa rasmi/ikonkasi va Brend logotipini ro'yxatda hamda forma maydonlarida 40x40px o'lchamda ko'rsatish.
- **Toifalar ierarxiyasi**: Kategoriya to'liq yo'li (`get_full_path`) va mahsulotlar soni badji.
- **Brend veb-sayti tugmasi**: To'g'ridan-to'g'ri rasmiy saytga o'tish tugmasi (`btn btn-sm btn-outline-info`).
- **`autocomplete_fields`**: Toifaning ota elementi (`parent`) uchun qidiruv tizimi.
- **Tezkor tahrirlash**: `is_active` jadvalda o'zgartirish.

### 2.5. Inlines (`ProductMediaInline`, `ProductCategoryInline`, `ProductVariantInline`, `InventoryInline`, `AttributeValueInline`)
- `ProductMediaInline`: Rasm yoki video faylning thumbnail ko'rinishi inline jadval qatorida aks etadi (`media_preview`).
- `ProductCategoryInline`: `autocomplete_fields = ['category']` va ixcham jadval ko'rinishi (`extra = 0`).
- `InventoryInline`: Variant sahifasida mavjud qoldiq, band qilingan qoldiq va holat badjlarini qulay chiqarish.

---

## 3. Ketma-ket Amalga Oshirish Rejasi (Checklist)

- [x] **Bosqich 1: Git tarmog'i va tayyorgarlik**
  - Git tarmog'ini `refactor/products-admin-jazzmin` holatida tekshirish.
- [x] **Bosqich 2: Yordamchi HTML va Badj formatlovchi funksiyalarni ishlab chiqish**
  - Bootstrap 4 / Jazzmin standartidagi xavfsiz `format_html` yordamchilarini yaratish (rasm thumbnail, zaxira status badji, narx formati, sayt havolasi).
- [x] **Bosqich 3: Inlinelarni (`ProductMediaInline`, `ProductCategoryInline`, `InventoryInline`, `ProductVariantInline`) modernizatsiya qilish**
  - Rasmlar prevyusi, `autocomplete_fields`, ixcham tartib va `show_change_link` qo'shish.
- [x] **Bosqich 4: `CategoryAdmin` va `BrandAdmin` ni takomillashtirish**
  - Logo/rasm thumbnail, mahsulotlar soni annotatsiyasi, veb-sayt tugmasi, `list_editable` va optimallashtirilgan `get_queryset`.
- [x] **Bosqich 5: `ProductAdmin` ni modernizatsiya qilish**
  - Asosiy rasm prevyusi, variantlar soni, narxlar diapazoni, zaxira indikatori, maydonlar guruhlanishi (`fieldsets`), guruhli amallar (`actions`), `select_related`/`prefetch_related`.
- [x] **Bosqich 6: `ProductVariantAdmin` va `InventoryAdmin` ni modernizatsiya qilish**
  - Narx va chegirma ko'rsatkichlari, zaxira holati badjlari, maxsus `StockStatusFilter`, tezkor tahrirlash (`list_editable`), N+1 so'rovlarni yo'qotish.
- [x] **Bosqich 7: `AttributeAdmin` va `AttributeValueAdmin` ni boyitish**
  - Qirqimlar (tags/badges) ko'rinishi, qidiruv va bog'lanishlarni sozlash.
- [x] **Bosqich 8: Testlar va sifat nazorati**
  - Django tizim tekshiruvi (`python manage.py check`) va testlarni (`python manage.py test apps.products`) xatosiz ishlashini tasdiqlash.
- [x] **Bosqich 9: Yakuniy tekshiruv va hujjatlashtirish**
  - O'zgarishlarni ko'rib chiqish va foydalanuvchiga taqdim etish.
