from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm, UserAdminCreationForm
from .models import OTPCode, User


class HasOrdersFilter(admin.SimpleListFilter):
    """
    Filter users by whether they have placed any orders.
    """

    title = _("Buyurtmalar holati")
    parameter_name = 'has_orders'

    def lookups(self, request, model_admin):
        return (
            ('yes', _("Buyurtma bergan (≥ 1)")),
            ('no', _("Buyurtma bermagan (0)")),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(orders__isnull=False).distinct()
        if self.value() == 'no':
            return queryset.filter(orders__isnull=True)
        return queryset


class OTPCodeInline(admin.TabularInline):
    """
    Readonly tabular inline to display user OTP verification history.
    """

    model = OTPCode
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('code_display', 'otp_type_badge', 'status_badge', 'expires_at', 'created_at')
    readonly_fields = ('code_display', 'otp_type_badge', 'status_badge', 'expires_at', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Kod"))
    def code_display(self, obj):
        return format_html(
            '<code style="font-size: 12px; font-weight: bold; background-color: #f1f3f4; '
            'color: #202124; padding: 2px 6px; border-radius: 4px; border: 1px solid #dadce0;">{}</code>',
            obj.code,
        )

    @admin.display(description=_("Kod turi"))
    def otp_type_badge(self, obj):
        badge_configs = {
            OTPCode.OTPType.REGISTER: ('badge-info', 'fa-user-plus', "Ro‘yxatdan o‘tish"),
            OTPCode.OTPType.PASSWORD_RESET: ('badge-warning', 'fa-key', "Parolni tiklash"),
            OTPCode.OTPType.LOGIN: ('badge-success', 'fa-sign-in-alt', "Tizimga kirish"),
        }
        cls, icon, label = badge_configs.get(
            obj.otp_type, ('badge-secondary', 'fa-shield-alt', obj.get_otp_type_display())
        )
        return format_html(
            '<span class="badge {}" style="font-size: 11px; padding: 3px 6px;">'
            '<i class="fas {} mr-1"></i>{}'
            '</span>',
            cls,
            icon,
            label,
        )

    @admin.display(description=_("Holati"))
    def status_badge(self, obj):
        if obj.is_used:
            return format_html(
                '<span class="badge badge-secondary" style="font-size: 11px; padding: 3px 6px;">'
                '<i class="fas fa-check mr-1"></i> Ishlatilgan'
                '</span>'
            )
        if obj.is_valid():
            return format_html(
                '<span class="badge badge-success" style="font-size: 11px; padding: 3px 6px;">'
                '<i class="fas fa-clock mr-1"></i> Yaroqli'
                '</span>'
            )
        return format_html(
            '<span class="badge badge-danger" style="font-size: 11px; padding: 3px 6px;">'
            '<i class="fas fa-times-circle mr-1"></i> Muddati o‘tgan'
            '</span>'
        )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Enhanced Admin interface for custom User model tailored for Jazzmin theme.
    """

    form = UserAdminChangeForm
    add_form = UserAdminCreationForm

    list_display = (
        'email_display',
        'full_name_display',
        'phone_number_display',
        'role_badge',
        'status_badge',
        'staff_badge',
        'orders_count_display',
        'created_at_display',
    )
    list_filter = (
        'role',
        'is_active',
        'is_staff',
        'is_superuser',
        HasOrdersFilter,
        'created_at',
    )
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 25
    empty_value_display = '-'
    save_on_top = True
    filter_horizontal = ('groups', 'user_permissions')

    inlines = [OTPCodeInline]

    fieldsets = (
        (
            _("Asosiy hisob ma'lumotlari"),
            {
                'fields': (
                    ('email', 'password'),
                    ('role', 'is_active'),
                ),
            },
        ),
        (
            _("Shaxsiy ma'lumotlar"),
            {
                'fields': (
                    ('first_name', 'last_name'),
                    'phone_number',
                ),
            },
        ),
        (
            _("Huquqlar va Ruxsatlar"),
            {
                'classes': ('collapse',),
                'fields': (
                    ('is_staff', 'is_superuser'),
                    'groups',
                    'user_permissions',
                ),
            },
        ),
        (
            _("Statistika va Sanalar"),
            {
                'fields': (
                    ('last_login', 'created_at', 'updated_at'),
                    'orders_summary_display',
                ),
            },
        ),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login', 'orders_summary_display')

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'first_name', 'last_name', 'phone_number', 'role', 'password1', 'password2'),
            },
        ),
    )

    actions = [
        'activate_users',
        'deactivate_users',
        'make_admin_role',
        'make_customer_role',
        'make_staff_status',
        'remove_staff_status',
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(orders_count=models.Count('orders', distinct=True))

    @admin.display(description=_("Email"), ordering='email')
    def email_display(self, obj):
        return format_html(
            '<div style="display: inline-flex; align-items: center; gap: 6px;">'
            '<i class="fas fa-user-circle text-muted" style="font-size: 14px;"></i> '
            '<a href="mailto:{}" style="font-weight: 600; text-decoration: none;">{}</a>'
            '</div>',
            obj.email,
            obj.email,
        )

    @admin.display(description=_("F.I.Sh"), ordering='first_name')
    def full_name_display(self, obj):
        full = f"{obj.first_name} {obj.last_name}".strip()
        if not full:
            return format_html('<span class="text-muted">-</span>')
        return format_html('<strong>{}</strong>', full)

    @admin.display(description=_("Telefon"), ordering='phone_number')
    def phone_number_display(self, obj):
        if not obj.phone_number:
            return format_html('<span class="text-muted">-</span>')
        return format_html(
            '<span style="white-space: nowrap;"><i class="fas fa-phone-alt text-muted mr-1" style="font-size: 11px;"></i>{}</span>',
            obj.phone_number,
        )

    @admin.display(description=_("Rol"), ordering='role')
    def role_badge(self, obj):
        if obj.role == User.Role.ADMIN:
            return format_html(
                '<span class="badge badge-danger" style="font-size: 11px; padding: 4px 8px;">'
                '<i class="fas fa-user-shield mr-1"></i> Admin'
                '</span>'
            )
        return format_html(
            '<span class="badge badge-info" style="font-size: 11px; padding: 4px 8px;">'
            '<i class="fas fa-user mr-1"></i> Mijoz'
            '</span>'
        )

    @admin.display(description=_("Holat"), ordering='is_active')
    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span class="badge badge-success" style="font-size: 11px; padding: 4px 8px;">'
                '<i class="fas fa-check-circle mr-1"></i> Faol'
                '</span>'
            )
        return format_html(
            '<span class="badge badge-secondary" style="font-size: 11px; padding: 4px 8px;">'
            '<i class="fas fa-ban mr-1"></i> Nofaol'
            '</span>'
        )

    @admin.display(description=_("Ruxsat"), ordering='is_staff')
    def staff_badge(self, obj):
        if obj.is_superuser:
            return format_html(
                '<span class="badge badge-warning" style="font-size: 10px; padding: 3px 6px;">'
                '<i class="fas fa-crown mr-1"></i> Superadmin'
                '</span>'
            )
        if obj.is_staff:
            return format_html(
                '<span class="badge badge-primary" style="font-size: 10px; padding: 3px 6px;">'
                '<i class="fas fa-id-badge mr-1"></i> Xodim'
                '</span>'
            )
        return format_html('<span class="text-muted">-</span>')

    @admin.display(description=_("Buyurtmalar"), ordering='orders_count')
    def orders_count_display(self, obj):
        count = getattr(obj, 'orders_count', None)
        if count is None:
            count = obj.orders.count() if hasattr(obj, 'orders') else 0

        if count == 0:
            return format_html('<span class="text-muted">0 ta</span>')

        changelist_url = reverse('admin:orders_order_changelist')
        return format_html(
            '<a href="{}?user__id__exact={}" class="badge badge-primary" '
            'style="font-size: 11px; padding: 4px 8px; text-decoration: none;" title="Buyurtmalarni ko‘rish">'
            '<i class="fas fa-shopping-bag mr-1"></i> {} ta'
            '</a>',
            changelist_url,
            obj.id,
            count,
        )

    @admin.display(description=_("Ro'yxatdan o'tgan"), ordering='created_at')
    def created_at_display(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M')

    @admin.display(description=_("Buyurtmalar hisoboti"))
    def orders_summary_display(self, obj):
        if not obj or not obj.pk:
            return "-"
        count = obj.orders.count() if hasattr(obj, 'orders') else 0
        if count == 0:
            return format_html('<span class="text-muted">Ushbu foydalanuvchida hali buyurtmalar mavjud emas.</span>')

        changelist_url = reverse('admin:orders_order_changelist')
        return format_html(
            '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 6px; border: 1px solid #e9ecef;">'
            '<p style="margin-bottom: 6px;">Jami buyurtmalar soni: <strong>{} ta</strong></p>'
            '<a href="{}?user__id__exact={}" class="btn btn-sm btn-outline-primary" target="_blank">'
            '<i class="fas fa-external-link-alt mr-1"></i> Foydalanuvchi buyurtmalarini ko‘rish'
            '</a>'
            '</div>',
            count,
            changelist_url,
            obj.id,
        )

    @admin.action(description=_("Tanlangan foydalanuvchilarni faollashtirish (is_active=True)"))
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} ta foydalanuvchi muvaffaqiyatli faollashtirildi.", messages.SUCCESS)

    @admin.action(description=_("Tanlangan foydalanuvchilarni bloklash / nofaol qilish (is_active=False)"))
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} ta foydalanuvchi nofaol holatga o'tkazildi.", messages.WARNING)

    @admin.action(description=_("Tanlangan foydalanuvchilarga Admin rolini berish"))
    def make_admin_role(self, request, queryset):
        updated = queryset.update(role=User.Role.ADMIN)
        self.message_user(request, f"{updated} ta foydalanuvchining roli Admin deb belgilandi.", messages.SUCCESS)

    @admin.action(description=_("Tanlangan foydalanuvchilarga Mijoz (Customer) rolini berish"))
    def make_customer_role(self, request, queryset):
        updated = queryset.update(role=User.Role.CUSTOMER)
        self.message_user(request, f"{updated} ta foydalanuvchining roli Mijoz deb belgilandi.", messages.SUCCESS)

    @admin.action(description=_("Tanlangan foydalanuvchilarga xodim (staff) maqomini berish"))
    def make_staff_status(self, request, queryset):
        updated = queryset.update(is_staff=True)
        self.message_user(request, f"{updated} ta foydalanuvchiga xodim (staff) maqomi berildi.", messages.SUCCESS)

    @admin.action(description=_("Tanlangan foydalanuvchilardan xodim (staff) maqomini olib tashlash"))
    def remove_staff_status(self, request, queryset):
        updated = queryset.update(is_staff=False)
        self.message_user(request, f"{updated} ta foydalanuvchidan xodim (staff) maqomi olib tashlandi.", messages.INFO)


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    """
    Enhanced Admin interface for OTPCode model tailored for Jazzmin theme.
    """

    list_display = (
        'id',
        'user_link',
        'code_display',
        'otp_type_badge',
        'status_badge',
        'expires_at',
        'created_at',
    )
    list_filter = (
        'otp_type',
        'is_used',
        'created_at',
        'expires_at',
    )
    search_fields = (
        'code',
        'user__email',
        'user__first_name',
        'user__last_name',
        'user__phone_number',
    )
    autocomplete_fields = ['user']
    readonly_fields = ('code', 'status_display', 'created_at', 'expires_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 30
    empty_value_display = '-'

    fieldsets = (
        (
            _("OTP Kod Ma'lumotlari"),
            {
                'fields': (
                    'user',
                    'code',
                    'otp_type',
                ),
            },
        ),
        (
            _("Holat va Muddat"),
            {
                'fields': (
                    'is_used',
                    'status_display',
                    'expires_at',
                    'created_at',
                ),
            },
        ),
    )

    actions = ['mark_as_used', 'invalidate_codes']

    @admin.display(description=_("Foydalanuvchi"), ordering='user__email')
    def user_link(self, obj):
        url = reverse('admin:users_user_change', args=[obj.user.id])
        return format_html(
            '<a href="{}" style="font-weight: 600; text-decoration: none;">'
            '<i class="fas fa-user text-muted mr-1"></i>{}'
            '</a>',
            url,
            obj.user.email,
        )

    @admin.display(description=_("Kod"), ordering='code')
    def code_display(self, obj):
        return format_html(
            '<code style="font-size: 13px; font-weight: bold; background-color: #f1f3f4; '
            'color: #202124; padding: 3px 8px; border-radius: 4px; border: 1px solid #dadce0; letter-spacing: 1px;">{}</code>',
            obj.code,
        )

    @admin.display(description=_("Kod turi"), ordering='otp_type')
    def otp_type_badge(self, obj):
        badge_configs = {
            OTPCode.OTPType.REGISTER: ('badge-info', 'fa-user-plus', "Ro‘yxatdan o‘tish"),
            OTPCode.OTPType.PASSWORD_RESET: ('badge-warning', 'fa-key', "Parolni tiklash"),
            OTPCode.OTPType.LOGIN: ('badge-success', 'fa-sign-in-alt', "Tizimga kirish"),
        }
        cls, icon, label = badge_configs.get(
            obj.otp_type, ('badge-secondary', 'fa-shield-alt', obj.get_otp_type_display())
        )
        return format_html(
            '<span class="badge {}" style="font-size: 11px; padding: 4px 8px;">'
            '<i class="fas {} mr-1"></i>{}'
            '</span>',
            cls,
            icon,
            label,
        )

    @admin.display(description=_("Holati"))
    def status_badge(self, obj):
        if obj.is_used:
            return format_html(
                '<span class="badge badge-secondary" style="font-size: 11px; padding: 4px 8px;">'
                '<i class="fas fa-check mr-1"></i> Ishlatilgan'
                '</span>'
            )
        if obj.is_valid():
            return format_html(
                '<span class="badge badge-success" style="font-size: 11px; padding: 4px 8px;">'
                '<i class="fas fa-clock mr-1"></i> Yaroqli'
                '</span>'
            )
        return format_html(
            '<span class="badge badge-danger" style="font-size: 11px; padding: 4px 8px;">'
            '<i class="fas fa-times-circle mr-1"></i> Muddati o‘tgan'
            '</span>'
        )

    @admin.display(description=_("Yaroqlilik holati"))
    def status_display(self, obj):
        return self.status_badge(obj)

    @admin.action(description=_("Tanlangan kodlarni ishlatilgan deb belgilash"))
    def mark_as_used(self, request, queryset):
        updated = queryset.update(is_used=True)
        self.message_user(request, f"{updated} ta OTP kod ishlatilgan deb belgilandi.", messages.SUCCESS)

    @admin.action(description=_("Tanlangan kodlarning muddatini tugatish (bekor qilish)"))
    def invalidate_codes(self, request, queryset):
        updated = queryset.update(expires_at=timezone.now())
        self.message_user(request, f"{updated} ta OTP kodning muddati bekor qilindi.", messages.SUCCESS)
