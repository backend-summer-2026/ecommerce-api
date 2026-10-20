from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address must be provided')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', False)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        if extra_fields.get('is_active') is not True:
            raise ValueError('Superuser must have is_active=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for ecommerce platform.
    Email is used as the primary identifier instead of username.
    """

    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        ADMIN = 'admin', 'Admin'

    email = models.EmailField(
        'email address',
        unique=True,
        db_index=True,
        max_length=255,
    )
    first_name = models.CharField('first name', max_length=150, blank=True)
    last_name = models.CharField('last name', max_length=150, blank=True)
    phone_number = models.CharField('phone number', max_length=20, blank=True, null=True)
    role = models.CharField(
        'role',
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )
    is_active = models.BooleanField(
        'active',
        default=False,
        help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.',
    )
    is_staff = models.BooleanField(
        'staff status',
        default=False,
        help_text='Designates whether the user can log into this admin site.',
    )
    created_at = models.DateTimeField('created at', auto_now_add=True)
    updated_at = models.DateTimeField('updated at', auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full if full else self.email

    def get_short_name(self):
        return self.first_name or self.email


class OTPCode(models.Model):
    """
    Model to store and validate One-Time Password (OTP) verification codes
    sent via SMTP or SMS.
    """

    class OTPType(models.TextChoices):
        REGISTER = 'register', 'Register'
        PASSWORD_RESET = 'password_reset', 'Password Reset'
        LOGIN = 'login', 'Login'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='otp_codes',
        verbose_name='user',
    )
    code = models.CharField('otp code', max_length=6)
    otp_type = models.CharField(
        'otp type',
        max_length=20,
        choices=OTPType.choices,
        default=OTPType.REGISTER,
    )
    expires_at = models.DateTimeField('expires at')
    is_used = models.BooleanField('is used', default=False)
    created_at = models.DateTimeField('created at', auto_now_add=True)

    class Meta:
        verbose_name = 'OTP code'
        verbose_name_plural = 'OTP codes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.code} ({self.otp_type})"

    def is_valid(self):
        """
        Check if the OTP code is unused and has not expired.
        """
        return not self.is_used and timezone.now() <= self.expires_at
