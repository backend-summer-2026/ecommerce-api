# Plan: Custom User Model, SMTP OTP Verification, and Authentication

## Metadata
- **Title**: Custom User Model, SMTP OTP Verification, and JWT Authentication System
- **Date**: 2026-10-17
- **Status**: IN_PROGRESS
- **Branch**: `feat/auth-custom-user-model`

---

## Context & Motivation
In an ecommerce application, user authentication is a core foundation. A standard Django `User` model uses `username`, whereas modern ecommerce applications require:
1. `email` as the unique user identifier (`USERNAME_FIELD`).
2. Email verification via One-Time Password (OTP) sent through SMTP before activating accounts (`is_active=False` -> `is_active=True`).
3. Resend OTP functionality with cooldown rate limiting.
4. JWT token-based authentication (`rest_framework_simplejwt`) for stateless REST APIs.
5. Roles (`customer`, `admin`) to prepare for customer and administrator access control.

---

## Architecture & Technical Design

### 1. Database & Models (`apps/users/models.py`)
- **`UserManager`**: Custom manager implementing `create_user` and `create_superuser` without requiring a username.
- **`User`**: Subclasses `AbstractBaseUser` and `PermissionsMixin`.
  - `email`: `EmailField(unique=True, db_index=True)`
  - `first_name`: `CharField(max_length=150, blank=True)`
  - `last_name`: `CharField(max_length=150, blank=True)`
  - `phone_number`: `CharField(max_length=20, blank=True, null=True)`
  - `role`: `CharField(choices=[('customer', 'Customer'), ('admin', 'Admin')], default='customer')`
  - `is_active`: `BooleanField(default=False)` (Activated upon OTP verification)
  - `is_staff`: `BooleanField(default=False)`
  - `is_superuser`: `BooleanField(default=False)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **`OTPCode`**: Model storing verification codes.
  - `user`: `ForeignKey(User, on_delete=CASCADE, related_name='otp_codes')`
  - `code`: `CharField(max_length=6)`
  - `otp_type`: `CharField(choices=[('register', 'Register'), ('password_reset', 'Password Reset'), ('login', 'Login')], default='register')`
  - `expires_at`: `DateTimeField` (Default: 5 minutes from creation)
  - `is_used`: `BooleanField(default=False)`
  - `created_at`: `DateTimeField(auto_now_add=True)`

### 2. Service Layer (`apps/users/services.py`)
- `generate_otp(user, otp_type='register') -> OTPCode`: Generates a secure random 6-digit code.
- `send_otp_email(user, otp_code, otp_type='register') -> bool`: Sends formatted email using Django's email backend.
- Fallback support: Uses `console.EmailBackend` if SMTP credentials are blank in development.

### 3. API Endpoints (`apps/users/urls.py` -> `/api/v1/auth/`)
- `POST /api/v1/auth/register/` - Create inactive user and dispatch OTP.
- `POST /api/v1/auth/verify-otp/` - Validate code, activate user, return access & refresh JWT tokens.
- `POST /api/v1/auth/resend-otp/` - Request a new OTP (with 60-second cooldown).
- `POST /api/v1/auth/login/` - Authenticate active user with email & password, return JWT tokens.
- `POST /api/v1/auth/token/refresh/` - Refresh JWT access token.
- `GET, PATCH /api/v1/auth/me/` - Retrieve or update authenticated user profile.

---

## Execution Checklist

- [x] Step 1: Configure `config/settings.py` for `.env`, `rest_framework`, `rest_framework_simplejwt`, `AUTH_USER_MODEL`, and SMTP email settings
- [x] Step 2: Implement custom `User` and `UserManager` models in `apps/users/models.py`
- [x] Step 3: Implement `OTPCode` model in `apps/users/models.py`
- [x] Step 4: Generate and apply initial migrations for `apps/users` (`makemigrations`, `migrate`)
- [x] Step 5: Implement email sending and OTP generation service in `apps/users/services.py`
- [x] Step 6: Implement serializers in `apps/users/serializers.py` (Register, VerifyOTP, ResendOTP, Login, Profile)
- [ ] Step 7: Implement API views in `apps/users/views.py` and configure routing in `apps/users/urls.py` & `config/urls.py`
- [ ] Step 8: Configure Django Admin in `apps/users/admin.py` for User and OTPCode
- [ ] Step 9: Write comprehensive automated tests in `apps/users/tests.py` and run test suite
- [ ] Step 10: Synchronize and verify master Postman collection in `postman/ecommerce_api_collection.json`
- [ ] Step 11: Final verification (`manage.py check`, run tests) and update plan status to COMPLETED
