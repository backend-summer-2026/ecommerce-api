from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import OTPCode, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin interface for custom User model.
    """

    list_display = (
        'email',
        'first_name',
        'last_name',
        'phone_number',
        'role',
        'is_active',
        'is_staff',
        'created_at',
    )
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Role & Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login')

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
            },
        ),
    )


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    """
    Admin interface for OTPCode model.
    """

    list_display = (
        'user',
        'code',
        'otp_type',
        'is_used',
        'expires_at',
        'created_at',
    )
    list_filter = ('otp_type', 'is_used')
    search_fields = ('user__email', 'code')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
