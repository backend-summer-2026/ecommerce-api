# Plan: Reviews REST API Implementation (`apps/reviews`)

## Metadata
- **Title**: Customer Reviews, Ratings, Media Upload, Helpful Voting, and Seller Replies REST API
- **Date**: 2026-10-24
- **Status**: COMPLETED
- **Completed**: 2026-10-24
- **Branch**: `feat/reviews-api`
- **Author**: Antigravity

---

## 1. Context & Motivation

`apps/reviews` moduli uchun ma'lumotlar bazasi modellari (`Review`, `ReviewImage`, `ReviewReply`, `ReviewVote`, `ProductRatingSummary`) to'liq ishlab chiqildi, migratsiya qilindi, testlandi va `dev` tarmog'iga birlashtirildi.

Endi ushbu modellar asosida frontend (mobil ilova va veb-sayt) hamda admin panel uchun xavfsiz, yuqori tezlikda ishlovchi REST API ishlab chiqish talab etiladi:

1. **Ommaviy (Public) API**:
   - Har qanday foydalanuvchi yoki mehmon mahsulot bo'yicha tasdiqlangan sharhlar (`APPROVED`) va fotosuratlarni ko'rishi, reyting taqsimotini (`ProductRatingSummary`) olishi;
   - Filtrlash: reyting (1-5 yulduz), faqat rasmli sharhlar, faqat xarid tasdiqlanganlar (`is_verified_purchase`);
   - Saralash: eng yangilar (`-created_at`), eng foydalilar (`-likes_count`), yuqori va past baholilar.

2. **Mijozlar (Customer) API**:
   - Avtorizatsiyadan o'tgan mijoz mahsulotga baho va sharh qoldirishi (bitta mahsulotga 1 ta sharh);
   - Tizim avtomatik ravishda mijoz buyurtmalarini tekshirib `is_verified_purchase` ni belgilashi;
   - O'z sharhiga fotosuratlar biriktirish (`ReviewImage`);
   - O'z sharhini tahrirlash yoki o'chirish;
   - Boshqa sharhlarga foydali (`HELPFUL`) yoki foydasiz (`UNHELPFUL`) deb ovoz berish (`ReviewVote`).

3. **Sotuvchi va Admin (Staff) API**:
   - Sotuvchi/admin mijoz sharhiga rasmiy javob (`ReviewReply`) qoldirishi;
   - Moderatorlar kutilayotgan sharhlarni tasdiqlashi (`approve`) yoki sababi bilan rad etishi (`reject`).

4. **Postman to'plami va Hujjatlashtirish**:
   - `postman/ecommerce_api_collection.json` ga barcha endpointlar uchun real so'rov va javob namunalarini qo'shish.

---

## 2. API Endpoints Specification

| Metod | Endpoint | Ruxsat | Tavsif |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/reviews/products/<product_id>/summary/` | Ochiq (AllowAny) | Mahsulot umumiy reytingi va yulduzlar taqsimoti |
| `GET` | `/api/v1/reviews/products/<product_id>/` | Ochiq (AllowAny) | Mahsulot tasdiqlangan sharhlari ro'yxati (filter, sort, pagination) |
| `POST` | `/api/v1/reviews/products/<product_id>/` | IsAuthenticated | Mahsulotga yangi sharh qoldirish |
| `GET` | `/api/v1/reviews/<id>/` | Ochiq (AllowAny) | Muayyan sharh batafsil ma'lumotlari, rasmlari va javobi |
| `PATCH/PUT` | `/api/v1/reviews/<id>/` | IsOwner | O'z sharhini tahrirlash (status avtomatik PENDING ga qaytadi) |
| `DELETE` | `/api/v1/reviews/<id>/` | IsOwner / IsAdmin | O'z sharhini o'chirish |
| `POST` | `/api/v1/reviews/<id>/images/` | IsOwner | Sharhga yangi fotosurat yuklash |
| `DELETE` | `/api/v1/reviews/images/<image_id>/` | IsOwner / IsAdmin | Sharh rasmini o'chirish |
| `POST` | `/api/v1/reviews/<id>/vote/` | IsAuthenticated | Sharhga ovoz berish (like/dislike yoki qayta bekor qilish) |
| `POST` | `/api/v1/reviews/<id>/reply/` | IsAdmin / Staff | Sotuvchi/Admin rasmiy javobi (yaratish yoki yangilash) |
| `GET` | `/api/v1/reviews/admin/moderation/` | IsAdminUser | Moderatsiyadagi barcha sharhlar ro'yxati |
| `POST` | `/api/v1/reviews/admin/<id>/moderate/` | IsAdminUser | Sharhni tasdiqlash yoki rad etish |

---

## 3. Detailed Checklist

- [x] Step 1: Git tarmog'ini yaratish: `git checkout -b feat/reviews-api`
- [x] Step 2: `apps/reviews/permissions.py` (IsReviewOwnerOrReadOnly, IsAdminOrStaffUser) va pagination sinflarini yaratish
- [x] Step 3: `apps/reviews/serializers/` modulini yaratish (`ReviewListSerializer`, `ReviewDetailSerializer`, `ReviewCreateUpdateSerializer`, `ReviewImageSerializer`, `ReviewReplySerializer`, `ReviewVoteSerializer`, `ProductRatingSummarySerializer`)
- [x] Step 4: `apps/reviews/views.py` da ochiq katalog, mijozlar sharhlari, rasm yuklash va ovoz berish viewset/viewlarini yaratish
- [x] Step 5: `apps/reviews/views.py` da sotuvchi javoblari (`ReviewReply`) va admin moderatsiya endpointlarini yaratish
- [x] Step 6: `apps/reviews/urls.py` ni yaratish va `config/urls.py` ga ulash (`/api/v1/reviews/`)
- [x] Step 7: `apps/reviews/tests/test_api.py` da to'liq unit va integratsion testlarni (barcha endpointlar va ruxsatlar bo'yicha) yozish
- [x] Step 8: `postman/ecommerce_api_collection.json` master to'plamiga yangi Reviews endpointlarini integratsiya qilish
- [x] Step 9: To'liq testlarni ishga tushirish, reja holatini `COMPLETED` ga o'tkazish va o'zgarishlarni commit qilish
