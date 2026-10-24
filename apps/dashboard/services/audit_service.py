from typing import Any, Dict, Optional
from apps.dashboard.models import StaffActivityLog


def get_client_ip(request) -> Optional[str]:
    """
    Extracts client IP address from HttpRequest, taking into account proxies.
    """
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request) -> str:
    """
    Extracts User-Agent string from HttpRequest.
    """
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:500]


def log_staff_activity(
    actor,
    action: str,
    module: str,
    description: str,
    target: Any = None,
    changes: Optional[Dict[str, Any]] = None,
    request: Any = None,
) -> StaffActivityLog:
    """
    Creates an immutable audit log entry for administrative activity.
    """
    target_model = ''
    target_id = ''
    target_repr = ''

    if target is not None:
        target_model = target.__class__.__name__
        target_id = str(getattr(target, 'pk', ''))
        target_repr = str(target)[:255]

    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)

    return StaffActivityLog.objects.create(
        actor=actor,
        action=action,
        module=module,
        target_model=target_model,
        target_id=target_id,
        target_repr=target_repr,
        description=description,
        changes=changes or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
