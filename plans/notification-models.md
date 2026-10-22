# Plan: Notification Data Models Architecture (`apps/notifications`)

## Metadata
- **Title**: Notification Data Models Architecture: Notification (In-App/Account), EmailNotification, NotificationPreference, and NotificationTemplate
- **Date**: 2026-10-22
- **Status**: COMPLETED
- **Branch**: `feat/notifications-models`
- **Completed**: 2026-10-22
- **Author**: Antigravity

---

## 1. Context & Motivation

E-commerce platformasida buyurtmalar (`apps/orders`), to'lovlar (`apps/payments`), savat (`apps/carts`) va foydalanuvchilar (`apps/users`) modullari yaratildi. Har qanday zamonaviy va ishonchli elektron tijorat tizimida xaridor va ma'murlar uchun o'z vaqtida, aniq va ishonchli bildirishnomalar yetkazib berish juda muhim biznes omili hisoblanadi.

Foydalanuvchi talabiga ko'ra `apps/notifications/` ilovasida quyidagi asosiy ehtiyojlar qondirilishi lozim:
1. **Account Notification (Shaxsiy kabinet / In-App bildirishnomalari)**:
   - Foydalanuvchining hisobiga yuboriladigan shaxsiy bildirishnomalar (web yoki mobil interfeysdagi qo'ng'iroqcha / bildirishnomalar bo'limi).
   - O'qilgan va o'qilmagan holatlarni kuzatish (`is_read`, `read_at`), o'qilgan deb belgilash metodlari.
   - Bildirishnoma turlari (Buyurtma, To'lov, Xavfsizlik/Akkaunt, Aksiya, Tizim).
   - Harakatga undovchi havola (`action_url`) va ixtiyoriy metadata (`data`).
2. **Email Notification (Email orqali yuboriladigan bildirishnomalar)**:
   - Ro'yxatdan o'tgan foydalanuvchilar yoki mehmonlarga (masalan, buyurtma kvitansiyasi) yuboriladigan transactional va marketing xatlari.
   - Email holatlarini boshqarish (`PENDING`, `SENDING`, `SENT`, `FAILED`, `CANCELLED`).
   - Qayta urinish mexanizmi (`attempts`, `max_retries`, `last_attempt_at`, `error_message`).
   - Xatlarning rejalashtirilgan yuborilishi (`scheduled_at`) va provayder tranzaksiya kodi (`provider_message_id`).
3. **NotificationPreference (Foydalanuvchi bildirishnoma sozlamalari)**:
   - Mijozlarga qaysi bildirishnomalarni email yoki sayt orqali olishni xohlashlarini mustaqil boshqarish imkoniyati (opt-in / opt-out).
4. **NotificationTemplate (Dinamik xabarnoma shablonlari)**:
   - Email mavzulari, HTML/tekst maketlari va in-app matnlarini tizimli, qayta ishlatiluvchi formatda boshqarish.

---

## 2. Architecture & Technical Design

### 2.1. Entity-Relationship Diagram

```mermaid
erDiagram
    User ||--o{ Notification : "receives (in-app)"
    User ||--o{ EmailNotification : "receives (email)"
    User ||--o| NotificationPreference : "configures"
    NotificationTemplate ||--o{ Notification : "generates (optional)"
    NotificationTemplate ||--o{ EmailNotification : "renders (optional)"

    Notification {
        bigint id PK
        fk user FK "CASCADE"
        string notification_type "ORDER/PAYMENT/ACCOUNT/PROMOTION/SYSTEM"
        string priority "LOW/NORMAL/HIGH/URGENT"
        string title "Short title"
        text message "Full body text"
        boolean is_read "Read/Unread status"
        datetime read_at "Timestamp when read"
        string action_url "Deep link redirect"
        json data "Metadata payload (order_id, etc.)"
        datetime created_at
        datetime updated_at
    }

    EmailNotification {
        bigint id PK
        fk user FK "SET_NULL"
        string recipient_email "Target email address"
        string subject "Email subject line"
        text body_text "Plain text body fallback"
        text body_html "Rendered HTML body"
        string template_code "Template identifier"
        json context_data "Variables used in rendering"
        string status "PENDING/SENDING/SENT/FAILED/CANCELLED"
        string priority "LOW/NORMAL/HIGH/URGENT"
        int attempts "Attempt counter"
        int max_retries "Max retry limit"
        datetime last_attempt_at
        datetime sent_at
        datetime scheduled_at
        text error_message "Failure details"
        string provider_message_id "SMTP/SES/SendGrid Message ID"
        datetime created_at
        datetime updated_at
    }

    NotificationPreference {
        bigint id PK
        fk user UK "CASCADE (OneToOne)"
        boolean email_order_updates "Order emails"
        boolean email_payment_receipts "Payment receipts"
        boolean email_promotions "Marketing emails"
        boolean email_security_alerts "Security emails"
        boolean in_app_order_updates "Order in-app alerts"
        boolean in_app_payment_updates "Payment in-app alerts"
        boolean in_app_promotions "Promotional in-app alerts"
        datetime created_at
        datetime updated_at
    }

    NotificationTemplate {
        bigint id PK
        string code UK "e.g. order_confirmed, payment_success"
        string name "Template human name"
        text description "Template description"
        string notification_type "ORDER/PAYMENT/ACCOUNT/PROMOTION/SYSTEM"
        string email_subject_template "Subject template"
        text email_body_html_template "HTML template"
        text email_body_text_template "Text template"
        string in_app_title_template "Title template"
        text in_app_message_template "Message template"
        boolean is_active "Active flag"
        datetime created_at
        datetime updated_at
    }
```

---

## 3. Models Detailed Specification (`apps/notifications/models.py`)

### 3.1. `Notification` (Account / In-App Bildirishnomalari)
- **Table Name**: `account_notifications`
- **Maqsadi**: Foydalanuvchining platforma ichidagi shaxsiy bildirishnomalarini saqlaydi va boshqaradi.
- **Maydonlar**:
  - `id`: `BigAutoField(primary_key=True)`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', db_index=True)`
  - `notification_type`: `CharField(max_length=30, choices=NotificationType.choices, default=NotificationType.SYSTEM)`
    - `ORDER`: Buyurtma bosqichlari (yaratildi, tasdiqlandi, yo'lga chiqdi, yetkazildi, bekor qilindi)
    - `PAYMENT`: To'lov va pul qaytarishlar
    - `ACCOUNT`: Profil, xavfsizlik, login xabarlari
    - `PROMOTION`: Maxsus chegirma, aksiya va promokodlar
    - `SYSTEM`: Tizim yangilanishlari va ogohlantirishlar
  - `priority`: `CharField(max_length=20, choices=NotificationPriority.choices, default=NotificationPriority.NORMAL)`
    - `LOW`, `NORMAL`, `HIGH`, `URGENT`
  - `title`: `CharField(max_length=255)` — qisqa sarlavha
  - `message`: `TextField()` — to'liq xabar matni
  - `is_read`: `BooleanField(default=False, db_index=True)` — o'qilgan/o'qilmagan holati
  - `read_at`: `DateTimeField(null=True, blank=True)` — o'qilgan vaqti
  - `action_url`: `CharField(max_length=500, blank=True, null=True)` — bosilganda ochiladigan sahifa yoki API yo'nalishi
  - `data`: `JSONField(default=dict, blank=True)` — qo'shimcha obyekt identifikatorlari (masalan: `{"order_id": 101, "order_number": "ORD-20261022-ABCDEF"}`)
  - `created_at`: `DateTimeField(auto_now_add=True, db_index=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Biznes Metodlar & QuerySet**:
  - `mark_as_read(save=True)`: `is_read = True`, `read_at = timezone.now()` qiladi.
  - `mark_as_unread(save=True)`: `is_read = False`, `read_at = None` qiladi.
  - `NotificationQuerySet`:
    - `.unread()` -> `filter(is_read=False)`
    - `.read()` -> `filter(is_read=True)`
    - `.mark_all_as_read()` -> barcha topilgan qatorlarni bitta SQL so'rovi bilan `update(is_read=True, read_at=timezone.now())` qiladi.
- **Indekslar**:
  - `['user', 'is_read', '-created_at']` (foydalanuvchining o'qilmagan xabarlarini tezda olish uchun)
  - `['user', '-created_at']`

---

### 3.2. `EmailNotification` (Email Xabarlari va Yuborish Jurnali)
- **Table Name**: `email_notifications`
- **Maqsadi**: Barcha chiqish email xabarlarini, ularning yetkazilish holatini, qayta urinishlarini va xatoliklarini qayd etadi.
- **Maydonlar**:
  - `id`: `BigAutoField(primary_key=True)`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_notifications', db_index=True)`
  - `recipient_email`: `EmailField(db_index=True)` — qabul qiluvchi manzili
  - `subject`: `CharField(max_length=255)` — xat mavzusi
  - `body_text`: `TextField(blank=True)` — plain text varianti
  - `body_html`: `TextField(blank=True)` — HTML varianti
  - `template_code`: `CharField(max_length=100, blank=True, null=True, db_index=True)` — shablon kodi
  - `context_data`: `JSONField(default=dict, blank=True)` — shablonda ishlatilgan dinamik o'zgaruvchilar
  - `status`: `CharField(max_length=20, choices=EmailStatus.choices, default=EmailStatus.PENDING, db_index=True)`
    - `PENDING`: Navbatda turibdi
    - `SENDING`: Yuborilmoqda
    - `SENT`: Muvaffaqiyatli yuborildi
    - `FAILED`: Xatolik ro'y berdi
    - `CANCELLED`: Bekor qilindi
  - `priority`: `CharField(max_length=20, choices=NotificationPriority.choices, default=NotificationPriority.NORMAL)`
  - `attempts`: `PositiveSmallIntegerField(default=0)` — urinishlar soni
  - `max_retries`: `PositiveSmallIntegerField(default=3)` — maksimal urinishlar
  - `last_attempt_at`: `DateTimeField(null=True, blank=True)`
  - `sent_at`: `DateTimeField(null=True, blank=True)`
  - `scheduled_at`: `DateTimeField(null=True, blank=True, db_index=True)` — kechiktirilgan yuborish vaqti
  - `error_message`: `TextField(blank=True, null=True)` — xatolik matni
  - `provider_message_id`: `CharField(max_length=255, blank=True, null=True)` — tashqi email server qaytargan ID
  - `created_at`: `DateTimeField(auto_now_add=True, db_index=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Biznes Metodlar**:
  - `mark_as_sent(provider_message_id=None)`: `status = SENT`, `sent_at = timezone.now()`
  - `mark_as_failed(error_message)`: `attempts += 1`, agar `attempts >= max_retries` bo'lsa `status = FAILED`, aks holda `status = PENDING` qilib qayta urinishga qoldiradi
  - `can_retry()` -> bool: holat va urinishlar chegarasini tekshiradi.
- **Indekslar**:
  - `['status', 'scheduled_at']` (navbatdagi xatlarni worker/Celery orqali tezkor filtrlash uchun)
  - `['recipient_email', '-created_at']`

---

### 3.3. `NotificationPreference` (Bildirishnoma Sozlamalari)
- **Table Name**: `notification_preferences`
- **Maqsadi**: Har bir foydalanuvchining qaysi kanal va qaysi mavzudagi bildirishnomalarni olishi bo'yicha sozlamalari.
- **Maydonlar**:
  - `id`: `BigAutoField(primary_key=True)`
  - `user`: `OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preference')`
  - `email_order_updates`: `BooleanField(default=True)` — buyurtma yangilanishlari xati
  - `email_payment_receipts`: `BooleanField(default=True)` — to'lov kvitansiyalari
  - `email_promotions`: `BooleanField(default=False)` — marketing va chegirmalar (standart bo'yicha o'chirilgan)
  - `email_security_alerts`: `BooleanField(default=True)` — xavfsizlik ogohlantirishlari
  - `in_app_order_updates`: `BooleanField(default=True)` — saytdagi buyurtma xabarlari
  - `in_app_payment_updates`: `BooleanField(default=True)` — saytdagi to'lov xabarlari
  - `in_app_promotions`: `BooleanField(default=True)` — saytdagi aksiyalar
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`

---

### 3.4. `NotificationTemplate` (Xabarnoma Shablonlari)
- **Table Name**: `notification_templates`
- **Maqsadi**: Ko'p marta ishlatiladigan email va akkaunt bildirishnoma shablonlarini markazlashgan holda boshqarish.
- **Maydonlar**:
  - `id`: `BigAutoField(primary_key=True)`
  - `code`: `CharField(max_length=100, unique=True, db_index=True)` (e.g. `order_confirmed`, `order_shipped`, `payment_success`, `welcome_email`, `password_reset`)
  - `name`: `CharField(max_length=255)`
  - `description`: `TextField(blank=True)`
  - `notification_type`: `CharField(max_length=30, choices=NotificationType.choices)`
  - `email_subject_template`: `CharField(max_length=255, blank=True)`
  - `email_body_html_template`: `TextField(blank=True)`
  - `email_body_text_template`: `TextField(blank=True)`
  - `in_app_title_template`: `CharField(max_length=255, blank=True)`
  - `in_app_message_template`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`

---

## 4. Django Admin Integration (`apps/notifications/admin.py`)
- `NotificationAdmin`:
  - `list_display`: `('id', 'user', 'notification_type', 'priority', 'title', 'is_read_badge', 'created_at')`
  - `list_filter`: `('is_read', 'notification_type', 'priority', 'created_at')`
  - `search_fields`: `('user__email', 'title', 'message')`
  - `actions`: `['mark_as_read', 'mark_as_unread']`
- `EmailNotificationAdmin`:
  - `list_display`: `('id', 'recipient_email', 'subject', 'status_badge', 'attempts', 'sent_at', 'created_at')`
  - `list_filter`: `('status', 'priority', 'created_at', 'sent_at')`
  - `search_fields`: `('recipient_email', 'subject', 'provider_message_id', 'error_message')`
  - `readonly_fields`: `('provider_message_id', 'attempts', 'sent_at', 'last_attempt_at', 'created_at', 'updated_at')`
  - `actions`: `['retry_failed_emails', 'mark_as_cancelled']`
- `NotificationPreferenceAdmin`:
  - `list_display`: `('user', 'email_order_updates', 'email_promotions', 'in_app_order_updates', 'updated_at')`
- `NotificationTemplateAdmin`:
  - `list_display`: `('code', 'name', 'notification_type', 'is_active', 'updated_at')`
  - `list_filter`: `('notification_type', 'is_active')`
  - `search_fields`: `('code', 'name')`

---

## 5. Automated Tests Specification (`apps/notifications/tests/test_models.py`)
- `NotificationModelTest`:
  - Akkaunt bildirishnomasini yaratish (`is_read=False`).
  - `mark_as_read()` va `mark_as_unread()` metodlari va vaqt (`read_at`) to'g'ri ishlashi.
  - `NotificationQuerySet` filtrlari: `.unread()`, `.read()`, `.mark_all_as_read()`.
  - JSON `data` maydoniga parametrlar saqlanishi.
- `EmailNotificationModelTest`:
  - Email modelini `PENDING` holatda yaratish.
  - `mark_as_sent()` chaqirilganda `status=SENT`, `sent_at` to'ldirilishi.
  - `mark_as_failed()` chaqirilganda `attempts` oshishi va `max_retries` tekshiruvi.
  - `can_retry()` mantiqiy sharti.
- `NotificationPreferenceModelTest`:
  - Foydalanuvchi uchun OneToOne sozlama yaratish va standart qiymatlar.
- `NotificationTemplateModelTest`:
  - Shablon kodi unikal bo'lishi va saqlanishi.

---

## 6. Execution Checklist

- [x] Step 1: Git tekshiruvi va `feat/notifications-models` tarmog'ida ekanlikni tasdiqlash
- [x] Step 2: `apps/notifications/models.py` da barcha modellarni (`Notification`, `EmailNotification`, `NotificationPreference`, `NotificationTemplate`) va ularning metodlarini to'liq yaratish
- [x] Step 3: `apps/notifications/admin.py` da modellarni qulay filtrlar, rangli status badge'lari va admin action'lari bilan ro'yxatdan o'tkazish
- [x] Step 4: Django migratsiyasini yaratish (`python manage.py makemigrations notifications`) va bazaga qo'llash (`python manage.py migrate`)
- [x] Step 5: `apps/notifications/tests/test_models.py` faylida to'liq unit testlarni yozish
- [x] Step 6: Testlarni ishga tushirish (`python manage.py test apps.notifications`) va barcha testlar muvaffaqiyatli o'tishini tasdiqlash
- [x] Step 7: Loyihani umumiy tekshirish (`python manage.py check`) va reja statusini `COMPLETED` ga yangilash
