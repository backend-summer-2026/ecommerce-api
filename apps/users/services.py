import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import OTPCode, User

logger = logging.getLogger(__name__)


def generate_otp_code(length: int = 6) -> str:
    """
    Generate a cryptographically secure random numeric OTP string.
    """
    range_start = 10 ** (length - 1)
    range_end = (10 ** length) - 1
    return str(secrets.randbelow(range_end - range_start + 1) + range_start)


def can_request_new_otp(user: User, otp_type: str = OTPCode.OTPType.REGISTER, cooldown_seconds: int = 60) -> tuple[bool, int]:
    """
    Check if the user is allowed to request a new OTP code based on the cooldown window.
    Returns (can_request: bool, remaining_seconds: int).
    """
    last_otp = OTPCode.objects.filter(user=user, otp_type=otp_type).order_by('-created_at').first()
    if not last_otp:
        return True, 0

    elapsed = (timezone.now() - last_otp.created_at).total_seconds()
    if elapsed < cooldown_seconds:
        remaining = int(cooldown_seconds - elapsed)
        return False, remaining

    return True, 0


def create_otp_for_user(
    user: User,
    otp_type: str = OTPCode.OTPType.REGISTER,
    expires_in_minutes: int = 5,
) -> OTPCode:
    """
    Invalidate previous unused codes of this type and generate a new OTPCode.
    """
    # Invalidate previous unused codes for this user & type
    OTPCode.objects.filter(
        user=user,
        otp_type=otp_type,
        is_used=False,
    ).update(is_used=True)

    code = generate_otp_code(6)
    expires_at = timezone.now() + timedelta(minutes=expires_in_minutes)

    otp_instance = OTPCode.objects.create(
        user=user,
        code=code,
        otp_type=otp_type,
        expires_at=expires_at,
        is_used=False,
    )
    return otp_instance


def send_otp_email(user: User, otp_code: str, otp_type: str = OTPCode.OTPType.REGISTER) -> bool:
    """
    Send OTP verification email to user's registered email address.
    """
    subject_map = {
        OTPCode.OTPType.REGISTER: 'Ecommerce - Email Verification Code',
        OTPCode.OTPType.PASSWORD_RESET: 'Ecommerce - Password Reset Code',
        OTPCode.OTPType.LOGIN: 'Ecommerce - Login Verification Code',
    }
    subject = subject_map.get(otp_type, 'Ecommerce - Verification Code')

    recipient_name = user.first_name if user.first_name else user.email
    message = (
        f"Assalomu alaykum, {recipient_name}!\n\n"
        f"Ecommerce platformasida hisobingizni tasdiqlash uchun bir martalik kodingiz (OTP):\n\n"
        f"    {otp_code}\n\n"
        f"Ushbu kod 5 daqiqa davomida amal qiladi. Agar siz ushbu amalni bajarmagan bo'lsangiz, xabarga e'tibor bermang.\n\n"
        f"Hurmat bilan,\nEcommerce jamoasi"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"OTP email sent successfully to {user.email}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send OTP email to {user.email}: {exc}", exc_info=True)
        return False
