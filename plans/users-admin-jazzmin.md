# Plan: Modern Django-Jazzmin Admin Interface Enhancement for Users App (`apps/users/admin.py`)

## Metadata
- **Title**: Django-Jazzmin Admin Interface Optimization for Users & OTP Authentication
- **Date**: 2026-10-24
- **Status**: COMPLETED
- **Branch**: `feat/users-admin-jazzmin`
- **Target File**: `apps/users/admin.py`
- **Author**: Antigravity

---

## 1. Context & Motivation

Loyiha Django admin paneli zamonaviy `django-jazzmin` mavzusi bilan integratsiya qilingan bo'lib, `apps/orders/admin.py`, `apps/products/admin.py`, `apps/dashboard/admin.py` kabi boshqa asosiy modullarda chiroyli badge'lar, inline'lar, date-hierarchy va tezkor amallar (actions) tatbiq etilgan.

Biroq `apps/users/admin.py` hozirda standart minimal ko'rinishda qolib ketgan:
1. **Vizual ko'rinish yo'qligi**: Foydalanuvchining roli (`ADMIN` vs `CUSTOMER`), hisob holati (`is_active`), xodimlik (`is_staff`, `is_superuser`) va OTP kod holatlari quruq matn yoki standart boolean iconlar ko'rinishida.
2. **Katta multi-select muammosi**: `groups` va `user_permissions` uchun `filter_horizontal` belgilanmagan, bu Jazzmin'da noqulay va xunuk maydon hosil qiladi.
3. **Bog'langan ma'lumotlar yo'qligi**:
   - Foydalanuvchi sahifasida uning OTP kodlari tarixi ko'rinmaydi.
   - Foydalanuvchining buyurtmalariga tezkor havola yoki buyurtmalar soni changelist'da mavjud emas.
4. **Foydali amallar (Admin Actions) yo'qligi**:
   - Foydalanuvchilarni bir bosishda faollashtirish (activate) yoki bloklash (deactivate),
   - Xodimlik (staff) maqomini berish yoki bekor qilish,
   - OTP kodlarni ishlatilgan deb belgilash yoki bekor qilish amallari mavjud emas.
5. **OTP kodlar xavfsizligi va auditi**:
   - `OTPCodeAdmin`da qidiruv, kod monospace ko'rinishi, yaroqlilik holati (yaroqli, ishlatilgan, muddati o'tgan) badge ko'rinishida emas va tahrirlanmasligi kerak bo'lgan maydonlar himoyalanmagan.

---

## 2. Technical Architecture & Design

### 2.1. `UserAdmin` Enhancements (`apps/users/admin.py`)
- **`list_display`**:
  - `email_with_avatar`: Foydalanuvchi belgisi (`fas fa-user-circle`) + email + mailto link.
  - `full_name_display`: Foydalanuvchi F.I.Sh (mavjud bo'lsa qalin harflar bilan, aks holda `-`).
  - `phone_number_display`: Telefon raqam (`fas fa-phone-alt` belgisi bilan).
  - `role_badge`:
    - `ADMIN`: `<span class="badge badge-danger"><i class="fas fa-user-shield mr-1"></i> Admin</span>`
    - `CUSTOMER`: `<span class="badge badge-info"><i class="fas fa-user mr-1"></i> Customer</span>`
  - `status_badge`:
    - Faol: `<span class="badge badge-success"><i class="fas fa-check-circle mr-1"></i> Faol</span>`
    - Nofaol: `<span class="badge badge-secondary"><i class="fas fa-ban mr-1"></i> Nofaol</span>`
  - `staff_badge`:
    - Superuser: `<span class="badge badge-warning"><i class="fas fa-crown mr-1"></i> Superadmin</span>`
    - Staff: `<span class="badge badge-primary"><i class="fas fa-id-badge mr-1"></i> Xodim</span>`
    - Oddiy mijoz: `<span class="text-muted">-</span>`
  - `orders_count_display`: Foydalanuvchining buyurtmalar soni va buyurtmalar changelist'iga bevosita filtrlovchi kliklanadigan havola (`/admin/orders/order/?user__id__exact={id}`).
  - `created_at_display`: Ro'yxatdan o'tgan sana va vaqt.
- **`list_filter`**:
  - `role`, `is_active`, `is_staff`, `is_superuser`, `created_at`.
  - Maxsus filtr: `HasOrdersFilter` (Barcha foydalanuvchilar / Buyurtma berganlar / Buyurtma bermaganlar).
- **`search_fields`**:
  - `('email', 'first_name', 'last_name', 'phone_number')`
- **`date_hierarchy`**:
  - `date_hierarchy = 'created_at'` (tepadagi kalendar navigatsiya paneli).
- **`filter_horizontal`**:
  - `filter_horizontal = ('groups', 'user_permissions')` (ikki ustunli zamonaviy qidiruvli tanlash vidjeti).
- **`inlines`**:
  - `OTPCodeInline`: Foydalanuvchiga yuborilgan so'nggi OTP kodlar tarixi (kod, tur, holat, amal qilish muddati, yaratilgan vaqt). Xavfsizlik uchun faqat o'qish (read-only) rejimida, `can_delete = False`, `extra = 0`.
- **`fieldsets` (Jazzmin horizontal tabs bilan moslashgan)**:
  1. `Asosiy hisob ma'lumotlari`: `('email', 'password')`, `('role', 'is_active')`
  2. `Shaxsiy ma'lumotlar`: `('first_name', 'last_name')`, `'phone_number'`
  3. `Huquqlar va Ruxsatlar`: `('is_staff', 'is_superuser')`, `'groups'`, `'user_permissions'`
  4. `Statistika va Sanalar`: `('last_login', 'created_at', 'updated_at')`, `'orders_summary_display'`
- **`actions`**:
  - `activate_users`: Tanlangan foydalanuvchilarni faollashtirish (`is_active=True`).
  - `deactivate_users`: Tanlangan foydalanuvchilarni bloklash (`is_active=False`).
  - `make_admin_role`: Admin roliga o'tkazish.
  - `make_customer_role`: Customer roliga o'tkazish.
  - `make_staff_status`: Xodim maqomini berish (`is_staff=True`).
  - `remove_staff_status`: Xodim maqomini olib tashlash (`is_staff=False`).
- **`save_on_top = True`**, **`list_per_page = 25`**, **`empty_value_display = '-'`**.

---

### 2.2. `OTPCodeAdmin` Enhancements (`apps/users/admin.py`)
- **`list_display`**:
  - `id`
  - `user_link`: Foydalanuvchi profiliga bevosita o'tuvchi havola (`email`).
  - `code_display`: Monospace uslubidagi zamonaviy kod ko'rinishi (`<code>...</code>`).
  - `otp_type_badge`:
    - `REGISTER`: `<span class="badge badge-info"><i class="fas fa-user-plus mr-1"></i> Ro'yxatdan o'tish</span>`
    - `PASSWORD_RESET`: `<span class="badge badge-warning"><i class="fas fa-key mr-1"></i> Parolni tiklash</span>`
    - `LOGIN`: `<span class="badge badge-success"><i class="fas fa-sign-in-alt mr-1"></i> Tizimga kirish</span>`
  - `status_badge`:
    - Ishlatilgan: `<span class="badge badge-secondary"><i class="fas fa-check mr-1"></i> Ishlatilgan</span>`
    - Yaroqli (Faol): `<span class="badge badge-success"><i class="fas fa-clock mr-1"></i> Yaroqli</span>`
    - Muddati o'tgan: `<span class="badge badge-danger"><i class="fas fa-times-circle mr-1"></i> Muddati o'tgan</span>`
  - `expires_at`
  - `created_at`
- **`list_filter`**:
  - `otp_type`, `is_used`, `created_at`, `expires_at`
- **`search_fields`**:
  - `('code', 'user__email', 'user__first_name', 'user__last_name', 'user__phone_number')`
- **`autocomplete_fields`**:
  - `['user']`
- **`readonly_fields`**:
  - `('code', 'created_at', 'expires_at', 'status_display')`
- **`date_hierarchy`**:
  - `date_hierarchy = 'created_at'`
- **`actions`**:
  - `mark_as_used`: Tanlangan kodlarni ishlatilgan deb belgilash.
  - `invalidate_codes`: Tanlangan kodlar muddatini tugatish (bekor qilish).
- **`fieldsets`**:
  1. `OTP Kod Ma'lumotlari`: `'user'`, `'code'`, `'otp_type'`
  2. `Holat va Muddat`: `'is_used'`, `'status_display'`, `'expires_at'`, `'created_at'`

---

## 3. Checklist & Sequential Steps

- [x] **Step 1**: Git branch `feat/users-admin-jazzmin` tasdiqlanishi va tekshirilishi.
- [x] **Step 2**: `apps/users/admin.py` fayliga `OTPCodeInline`, `HasOrdersFilter`, xavfsiz badge yordamchilari va formatlovchilarni yozish.
- [x] **Step 3**: `UserAdmin` klassini boyitish (`list_display`, `list_filter`, `date_hierarchy`, `filter_horizontal`, `fieldsets`, `actions`, `orders_summary_display`).
- [x] **Step 4**: `OTPCodeAdmin` klassini boyitish (`list_display`, `otp_type_badge`, `status_badge`, `user_link`, `readonly_fields`, `actions`, `autocomplete_fields`).
- [x] **Step 5**: `apps/users/tests_admin.py` orqali admin paneldagi yangi metodlar, badglar, filtrlash va actionlarni to'liq unit test qilish.
- [x] **Step 6**: Mavjud testlar to'liq ishlashini (`python manage.py test apps.users`) tasdiqlash.
- [x] **Step 7**: Kodni formatlash, git commit qilish va `dev` tarmog'iga birlashtirishga tayyorlash.
