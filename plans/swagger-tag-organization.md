# Plan: Swagger API Endpoints Tag Organization & Classification

## Metadata
- **Title**: Swagger OpenAPI Endpoints Tag Organization & Removing 'v1' Default Tag
- **Date**: 2026-10-24
- **Status**: COMPLETED
- **Completed**: 2026-10-24
- **Branch**: `fix/swagger-tags`
- **Author**: Antigravity

---

## 1. Context & Problem Statement

Hozirgi Swagger UI hujjatida barcha endpointlar default bo'yicha yagona `v1` tegiga tushib qolgan edi. Buning sababi `drf-spectacular` standart holatda URL prefiksi `/api/` dan keyingi birinchi qismni (`v1`) asosiy tag deb hisoblagan.

Natijada:
1. `config/settings.py` dagi `SPECTACULAR_SETTINGS['TAGS']` da belgilangan 8 ta tematik guruh (`Auth`, `Catalog`, `Cart`, `Orders`, `Payments`, `Notifications`, `Reviews`, `Dashboard`) bo'sh turgan edi.
2. Barcha endpointlar yagona `v1` nomli papkaga to'planib qolgan edi.

---

## 2. Technical Solution

1. **`SCHEMA_PATH_PREFIX` ni sozlash**:
   - `config/settings.py` dagi `SPECTACULAR_SETTINGS` ga `'SCHEMA_PATH_PREFIX': r'/api/v[0-9]+'` qiymati berildi. Bu `drf-spectacular` ga URL prefiksidagi `/api/v1` ni kesib tashlashni ta'minlaydi.

2. **Maxsus Postprocessing Hook (`config/spectacular.py`)**:
   - `custom_tag_postprocessing_hook` yaratildi.
   - Har bir endpoint URL prefiksi asosida o'zining tegishli moduliga xaritalandi:
     - `/api/v1/auth/*` -> `Auth` (9 endpoints)
     - `/api/v1/catalog/*` -> `Catalog` (10 endpoints)
     - `/api/v1/cart/*` -> `Cart` (8 endpoints)
     - `/api/v1/orders/*` -> `Orders` (11 endpoints)
     - `/api/v1/payments/*` -> `Payments` (19 endpoints)
     - `/api/v1/notifications/*` -> `Notifications` (24 endpoints)
     - `/api/v1/reviews/*` -> `Reviews` (13 endpoints)
     - `/api/v1/dashboard/*` -> `Dashboard` (20 endpoints)
   - Barcha endpointlardan ortiqcha `v1` tegi to'liq olib tashlandi.

3. **`config/settings.py` ga hook ulandi**:
   - `POSTPROCESSING_HOOKS` ro'yxatiga `config.spectacular.custom_tag_postprocessing_hook` qo'shildi.

4. **Avtomatlashtirilgan Testlar (`config/tests/test_swagger.py`)**:
   - Sxemada `v1` tegi yo'qligi va barcha 8 ta tematik tag bo'yicha endpointlar to'g'ri taqsimlanganligi tekshirildi.

---

## 3. Detailed Checklist

- [x] Step 1: `fix/swagger-tags` branchini ochish va holatni tekshirish
- [x] Step 2: `config/spectacular.py` faylida `custom_tag_postprocessing_hook` hookini yaratish
- [x] Step 3: `config/settings.py` dagi `SPECTACULAR_SETTINGS` ga `SCHEMA_PATH_PREFIX` va `POSTPROCESSING_HOOKS` ni ulash
- [x] Step 4: `python manage.py spectacular --validate` buyrug'i orqali sxemani qayta generatsiya qilish va taglarni tekshirish
- [x] Step 5: `config/tests/test_swagger.py` ga taglar taqsimoti bo'yicha yangi testlarni qo'shish
- [x] Step 6: Barcha testlarni ishga tushirish (`python manage.py test config.tests`)
- [x] Step 7: Rejadagi barcha bandlarni `[x]` qilib belgilash va o'zgarishlarni commit qilib `dev` tarmog'iga birlashtirish
