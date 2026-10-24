# Plan: Django Admin Panel Sidebar Collapsible Menu & Accordion (`django-jazzmin`)

## Header & Metadata
- **Title**: Django Admin Panel Sidebar App Treeview & Accordion Navigation
- **Date**: 2026-10-24
- **Status**: COMPLETED
- **Branch**: `fix/admin-sidebar-accordion`
- **Author**: Antigravity

---

## 1. Context & Motivation

### Muammo (Problem)
Hozirgi vaqtda Django Admin panelida (`django-jazzmin` temasi ostida) barcha ilovalar (`dashboard`, `orders`, `payments`, `products`, `carts`, `reviews`, `notifications`, `users`, `auth`) va ularning barcha modellari (25 dan ortiq model) chap menyuda (sidebar) statik tarzda to'liq ochilgan holatda (`navigation_expanded: True`) ko'rinmoqda.

Buning oqibatida:
1. Menyuni yopib-ochish (accordion / collapsible treeview) imkoniyati mavjud emas; har bir app modeli doimiy ravishda ochiq turadi va sahifani vertikal scroll qilish talab etiladi.
2. Foydalanuvchi ma'lum bir ilovaga (masalan, Mahsulotlar yoki Buyurtmalar) kirganda faqat shu ilova ochilishi, boshqa ilovalar esa ixcham yopiq turishi kerak edi, ammo hozir hammasi birdek ochiq qolmoqda.

---

## 2. Architecture & Technical Design

### Yechim (Solution)

1. **`JAZZMIN_SETTINGS` konfiguratsiyasini yangilash (`config/settings.py`)**:
   - `"navigation_expanded": False` ga o'zgartiriladi.
   - Bu `django-jazzmin` shablonida har bir app'ni `<li class="nav-item has-treeview">` shakliga keltiradi va yig'iladigan (collapsible) dropdown holatiga o'tkazadi.
   - `"custom_js": "admin/js/custom_sidebar.js"` parametrini ulash.

2. **Statik fayllar sozlamasi (`config/settings.py`)**:
   - `STATICFILES_DIRS = [BASE_DIR / 'static']` sozlamasini qo'shish (loyihada maxsus admin skriptlarini saqlash uchun).

3. **Maxsus Sidebar Accordion & Active State skripti (`static/admin/js/custom_sidebar.js`)**:
   - **Accordion xatti-harakati**: `#jazzy-navigation` menyusida `data-accordion="true"` xususiyatini faollashtirish. Bu bitta ilova ochilganda, ilgari ochilgan boshqa ilovalar avtomatik ravishda yopilishini (ochilib-yopilishini) ta'minlaydi.
   - **Faol ilovani avtomatik ochish**: Foydalanuvchi qaysi ilova yoki model sahifasiga kirsa (masalan `/admin/orders/order/`, `/admin/orders/order/add/`, yoki `/admin/orders/` app index), URL yo'liga qarab tegishli app menyusi avtomatik ravishda ochiladi (`menu-open`), boshqa barcha ilovalar esa ixcham yopiladi.
   - **Interaktivlik**: Menyudagi ilova nomini bosganda u silliq (slideDown/slideUp) ochiladi va yopiladi, o'ng tarafdagi strelka piktogrammasi (`fas fa-chevron-right`) 90 gradusga aylanadi.

---

## 3. Detailed Sequential Checklist

- [x] **Step 1**: Git branch yaratish (`fix/admin-sidebar-accordion`) va dev bazasida tekshirish.
- [x] **Step 2**: `config/settings.py` fayliga `STATICFILES_DIRS = [BASE_DIR / 'static']` sozlamasini qo'shish.
- [x] **Step 3**: `config/settings.py` faylidagi `JAZZMIN_SETTINGS` da `"navigation_expanded": False` va `"custom_js": "admin/js/custom_sidebar.js"` ni sozlash.
- [x] **Step 4**: `static/admin/js/custom_sidebar.js` faylini yaratish (accordion funksionalligi, app index va model sahifalarida faol menyuni avtomatik ochish va yopish logikasi).
- [x] **Step 5**: Django tizim tekshiruvi (`python manage.py check`) va admin testlarini ishga tushirish.
- [x] **Step 6**: Admin HTML renderingini test qilish (`has-treeview` klasslari, faol app holati, skript ulanishi).
- [x] **Step 7**: Checklistni to'liq yangilash, o'zgarishlarni commit qilish va `dev` tarmog'iga qo'shish (merge).

---

## 4. Verification & Testing

1. `python manage.py check` xatoliklarsiz o'tishi.
2. `python manage.py test` testlar to'liq muvaffaqiyatli yakunlanishi.
3. Django test client orqali `/admin/`, `/admin/orders/order/`, `/admin/products/product/` sahifalarida sidebar to'g'ri `has-treeview` tuzilmasiga ega ekanligini va `custom_sidebar.js` skripti mavjudligini tasdiqlash.
