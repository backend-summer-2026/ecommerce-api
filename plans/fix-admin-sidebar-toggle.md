# Plan: Fix Admin Sidebar Menu Toggle & Item Expansion

## Header & Metadata
- **Title**: Fix Sidebar Menu Click Toggle and Item Expansion in Django Admin
- **Date**: 2026-10-24
- **Status**: COMPLETED
- **Branch**: `fix/admin-sidebar-menu-toggle`
- **Author**: Antigravity

---

## 1. Context & Motivation

### Muammo tahlili (Root Cause Analysis)
Foydalanuvchi sidebar menyusidagi ilovani bosganda, ichki modellar ro'yxati (itemlar) ochilmayapti.
Buning aniq texnik sababi aniqlandi:
1. `django-jazzmin==3.0.5` tarkibidagi AdminLTE v4-rc3 (`adminlte.min.js`) kutubxonasida `#jazzy-navigation` menyusiga `addEventListener("click", ...)` orqali standart treeview tinglovchisi biriktirilgan.
2. Shu bilan birga, `custom_sidebar.js` faylimizda ham `#jazzy-navigation` elementiga click tinglovchisi qo'yilgan edi.
3. Foydalanuvchi menyuni bosganda:
   - AdminLTE ning tinglovchisi birinchi ishga tushib, menyuga `menu-open` klassini qo'shadi;
   - Darhol ketidan bizning jQuery tinglovchimiz ishlab, `menu-open` allaqachon mavjudligini ko'radi va foydalanuvchi menyuni "yopmoqchi" deb o'ylab, `slideUp()` qilib menyuni yopib qo'yadi!
   - Natijada ikki skript bir-biri bilan to'qnashib, menyu ochilishi bilan 0.001 soniyada qayta yopilib qolgan va foydalanuvchiga itemlar umuman ko'rinmagan.
4. Bundan tashqari, AdminLTE 4-rc3 ning ichki `P.open()` kodida `if (e !== this._element.parentElement)` degan xatolik mavjud bo'lib, `accordion=true` bo'lganda AdminLTE o'zi ochayotgan elementni ham yopishga harakat qiladi.

---

## 2. Architecture & Technical Design

### Yechim (Solution)
1. **DOM Capture Phase orqali to'liq nazorat**:
   - `document.addEventListener('click', handler, true)` (uchinchi parametr `useCapture: true`) orqali chertish (click) hodisasini **Capture fazasida** tutib olamiz.
   - Capture fazasi DOM daraxti bo'ylab eng birinchi (Bubble fazasidan oldin) ishlaydi.
   - Agar chertish `#jazzy-navigation > li.nav-item.has-treeview > a.nav-link` (app sarlavhasi) ustida bo'lsa:
     - `e.preventDefault()`, `e.stopPropagation()` va `e.stopImmediatePropagation()` chaqiriladi.
     - Bu hodisaning AdminLTE ning bubble-tinglovchisiga yetib borishini **100% to'xtatadi** va barcha ziddiyatlarni bartaraf etadi.
2. **Mukammal Accordion va Toggle logikasi**:
   - Agar bosilgan app yopiq bo'lsa:
     - Boshqa barcha ochiq turgan ilovalar silliq yopiladi (`slideUp(200)` va `menu-open` olib tashlanadi);
     - Tanlangan ilova silliq ochiladi (`slideDown(200)` va `menu-open` qo'shiladi);
     - Strelka piktogrammasi 90 gradusga aylanadi.
   - Agar bosilgan app allaqachon ochiq bo'lsa:
     - U silliq yopiladi (`slideUp(200)` va `menu-open` olib tashlanadi).
3. **Ichki model havolalari**:
   - Model havolalari (`ul.nav-treeview a.nav-link`) app sarlavhasi emas, shuning uchun capture handler ularni to'xtatmaydi va standart Django Admin navigatsiyasi benuqson ishlaydi.
4. **Faol sahifani ochish (`autoExpandActiveApp`)**:
   - Sahifa yuklanganda (masalan, `/admin/orders/order/` yoki `/admin/orders/`), faol ilova avtomatik `menu-open` holatida ochiladi va boshqa ilovalar yopiq turadi.

---

## 3. Detailed Sequential Checklist

- [x] **Step 1**: `fix/admin-sidebar-menu-toggle` tarmog'ini yaratish va holatni tekshirish *(bajarildi)*
- [x] **Step 2**: `static/admin/js/custom_sidebar.js` skriptini Capture fazasi va to'qnashuvsiz accordion bilan to'liq qayta yangilash
- [x] **Step 3**: Django tizim tekshiruvi (`python manage.py check`) va testlarni (`python manage.py test config.tests.test_admin_sidebar`) ishga tushirish
- [x] **Step 4**: Barcha 294 ta loyiha testlarini (`python manage.py test`) muvaffaqiyatli yakunlash
- [x] **Step 5**: O'zgarishlarni commit qilish, `dev` tarmog'iga birlashtirish (merge) va `fix/admin-sidebar-menu-toggle` tarmog'ini o'chirish

---

## 4. Verification & Testing

1. `python manage.py test config.tests.test_admin_sidebar` barcha testlar muvaffaqiyatli o'tishi.
2. `custom_sidebar.js` sintaksis va logika tekshiruvi.
3. To'liq regression testlar (`python manage.py test`).
