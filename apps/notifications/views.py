from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import (
    EmailNotification,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)
from apps.notifications.pagination import NotificationPagination
from apps.notifications.permissions import IsAdminOrStaff, IsNotificationOwner
from apps.notifications.serializers import (
    EmailNotificationDetailSerializer,
    EmailNotificationListSerializer,
    NotificationBroadcastSerializer,
    NotificationDetailSerializer,
    NotificationListSerializer,
    NotificationPreferenceSerializer,
    NotificationTemplateSerializer,
    NotificationUnreadCountSerializer,
    TemplateTestSendSerializer,
)
from apps.notifications.services import (
    EmailService,
    NotificationService,
    TemplateRenderService,
)

User = get_user_model()


# ============================================================================
# Customer In-App Notification Views
# ============================================================================

class NotificationListView(generics.ListAPIView):
    """
    GET /api/v1/notifications/
    List personal in-app notifications for the authenticated user.
    Supports filtering by is_read, type, priority, and text search.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationListSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.for_user(user)

        # Filter by read/unread status
        is_read_param = self.request.query_params.get('is_read')
        if is_read_param is not None:
            if is_read_param.lower() in ['true', '1']:
                queryset = queryset.filter(is_read=True)
            elif is_read_param.lower() in ['false', '0']:
                queryset = queryset.filter(is_read=False)

        # Filter by notification type
        notif_type = self.request.query_params.get('type') or self.request.query_params.get('notification_type')
        if notif_type:
            queryset = queryset.filter(notification_type=notif_type.upper())

        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority.upper())

        # Text search in title and message
        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(Q(title__icontains=q) | Q(message__icontains=q))

        return queryset.order_by('-created_at')


class NotificationUnreadCountView(APIView):
    """
    GET /api/v1/notifications/unread-count/
    Returns lightweight counter for navbar/bell icon badges.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        counters = NotificationService.get_unread_count(request.user)
        serializer = NotificationUnreadCountSerializer(counters)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationDetailView(generics.RetrieveDestroyAPIView):
    """
    GET /api/v1/notifications/<int:pk>/
    DELETE /api/v1/notifications/<int:pk>/
    View full notification details or remove from personal feed.
    """

    permission_classes = [permissions.IsAuthenticated, IsNotificationOwner]
    serializer_class = NotificationDetailSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return Notification.objects.all()
        return Notification.objects.for_user(self.request.user)


class NotificationMarkReadView(APIView):
    """
    POST /api/v1/notifications/<int:pk>/read/
    Mark a single in-app notification as read.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        NotificationService.mark_as_read(notification, request.user)
        serializer = NotificationDetailSerializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationMarkUnreadView(APIView):
    """
    POST /api/v1/notifications/<int:pk>/unread/
    Revert a single in-app notification back to unread status.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        NotificationService.mark_as_unread(notification, request.user)
        serializer = NotificationDetailSerializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(APIView):
    """
    POST /api/v1/notifications/read-all/
    Mark all unread notifications of the user as read in a single SQL UPDATE.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        marked_count = NotificationService.mark_all_as_read(request.user)
        return Response({
            'marked_read_count': marked_count,
            'message': 'All unread notifications marked as read.',
        }, status=status.HTTP_200_OK)


class NotificationClearReadView(APIView):
    """
    DELETE /api/v1/notifications/clear-read/
    Bulk delete all notifications marked as read for the current user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        deleted_count = NotificationService.clear_read_notifications(request.user)
        return Response({
            'deleted_count': deleted_count,
            'message': 'Read notifications cleared successfully.',
        }, status=status.HTTP_200_OK)


# ============================================================================
# Customer Notification Preferences Views
# ============================================================================

class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """
    GET /api/v1/notifications/preferences/
    PUT / PATCH /api/v1/notifications/preferences/
    Retrieve or update user opt-in/opt-out notification preferences.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationPreferenceSerializer

    def get_object(self):
        preference, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return preference


# ============================================================================
# Admin / Staff Management Views
# ============================================================================

class AdminInAppNotificationListView(generics.ListAPIView):
    """
    GET /api/v1/notifications/admin/in-app/
    Administrative inspection of in-app notifications across all accounts.
    """

    permission_classes = [IsAdminOrStaff]
    serializer_class = NotificationDetailSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        queryset = Notification.objects.select_related('user').all()

        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        notif_type = self.request.query_params.get('type')
        if notif_type:
            queryset = queryset.filter(notification_type=notif_type.upper())

        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority.upper())

        is_read_param = self.request.query_params.get('is_read')
        if is_read_param is not None:
            if is_read_param.lower() in ['true', '1']:
                queryset = queryset.filter(is_read=True)
            elif is_read_param.lower() in ['false', '0']:
                queryset = queryset.filter(is_read=False)

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(message__icontains=q) |
                Q(user__email__icontains=q)
            )

        return queryset.order_by('-created_at')


class AdminBroadcastNotificationView(APIView):
    """
    POST /api/v1/notifications/admin/in-app/broadcast/
    Dispatch in-app notifications to all active users or targeted user group.
    """

    permission_classes = [IsAdminOrStaff]

    def post(self, request):
        serializer = NotificationBroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        created_count = NotificationService.broadcast(
            title=data['title'],
            message=data['message'],
            notification_type=data.get('notification_type', Notification.NotificationType.SYSTEM),
            priority=data.get('priority', Notification.NotificationPriority.NORMAL),
            action_url=data.get('action_url', ''),
            data=data.get('data', {}),
            user_ids=data.get('user_ids') if not data.get('broadcast') else None,
            recipient_type=data.get('recipient_type', 'ALL'),
        )

        return Response({
            'created_count': created_count,
            'message': f"Successfully dispatched notifications to {created_count} users.",
        }, status=status.HTTP_201_CREATED)


class AdminEmailNotificationListView(generics.ListAPIView):
    """
    GET /api/v1/notifications/admin/emails/
    Admin list of outbound email dispatch queue and audit trail.
    """

    permission_classes = [IsAdminOrStaff]
    serializer_class = EmailNotificationListSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        queryset = EmailNotification.objects.select_related('user').all()

        email_status = self.request.query_params.get('status')
        if email_status:
            queryset = queryset.filter(status=email_status.upper())

        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority.upper())

        recipient = self.request.query_params.get('recipient_email')
        if recipient:
            queryset = queryset.filter(recipient_email__icontains=recipient)

        template_code = self.request.query_params.get('template_code')
        if template_code:
            queryset = queryset.filter(template_code=template_code)

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(
                Q(subject__icontains=q) |
                Q(recipient_email__icontains=q)
            )

        return queryset.order_by('-created_at')


class AdminEmailNotificationDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/notifications/admin/emails/<int:pk>/
    Inspect full email log including HTML payload and error traces.
    """

    permission_classes = [IsAdminOrStaff]
    serializer_class = EmailNotificationDetailSerializer
    queryset = EmailNotification.objects.select_related('user').all()


class AdminEmailRetryView(APIView):
    """
    POST /api/v1/notifications/admin/emails/<int:pk>/retry/
    Manually retry dispatching a failed or pending email.
    """

    permission_classes = [IsAdminOrStaff]

    def post(self, request, pk):
        email_record = get_object_or_404(EmailNotification, pk=pk)
        try:
            success = EmailService.retry_email(email_record)
        except (ValidationError, DjangoValidationError) as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = EmailNotificationDetailSerializer(email_record)
        return Response({
            'success': success,
            'email': serializer.data,
            'message': 'Email dispatch executed.',
        }, status=status.HTTP_200_OK)


class AdminEmailCancelView(APIView):
    """
    POST /api/v1/notifications/admin/emails/<int:pk>/cancel/
    Cancel a pending email notification before dispatch.
    """

    permission_classes = [IsAdminOrStaff]

    def post(self, request, pk):
        email_record = get_object_or_404(EmailNotification, pk=pk)
        try:
            EmailService.cancel_email(email_record)
        except (ValidationError, DjangoValidationError) as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': f"Email #{email_record.id} cancelled successfully.",
        }, status=status.HTTP_200_OK)


class AdminNotificationTemplateListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/notifications/admin/templates/
    POST /api/v1/notifications/admin/templates/
    List and create dynamic notification templates.
    """

    permission_classes = [IsAdminOrStaff]
    serializer_class = NotificationTemplateSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        queryset = NotificationTemplate.objects.all()

        is_active_param = self.request.query_params.get('is_active')
        if is_active_param is not None:
            if is_active_param.lower() in ['true', '1']:
                queryset = queryset.filter(is_active=True)
            elif is_active_param.lower() in ['false', '0']:
                queryset = queryset.filter(is_active=False)

        notif_type = self.request.query_params.get('type')
        if notif_type:
            queryset = queryset.filter(notification_type=notif_type.upper())

        return queryset.order_by('code')


class AdminNotificationTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET / PUT / PATCH / DELETE /api/v1/notifications/admin/templates/<str:code>/
    Retrieve, update or delete a dynamic notification template by unique code.
    """

    permission_classes = [IsAdminOrStaff]
    serializer_class = NotificationTemplateSerializer
    lookup_field = 'code'
    queryset = NotificationTemplate.objects.all()


class AdminNotificationTemplateTestSendView(APIView):
    """
    POST /api/v1/notifications/admin/templates/<str:code>/test-send/
    Preview template rendering and optionally send test email or in-app notification.
    """

    permission_classes = [IsAdminOrStaff]

    def post(self, request, code):
        serializer = TemplateTestSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        context_data = data.get('context_data', {})
        test_email = data.get('test_email')
        send_email = data.get('send_email', True)
        send_in_app = data.get('send_in_app', False)
        user_id = data.get('user_id')

        try:
            rendered = TemplateRenderService.render_template(code, context_data)
        except ValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        email_result = None
        in_app_result = None

        if send_email and test_email:
            email_record = EmailService.send_or_queue_email(
                recipient_email=test_email,
                template_code=code,
                context_data=context_data,
                send_immediately=True,
                force=True,
            )
            email_result = {
                'id': email_record.id if email_record else None,
                'status': email_record.status if email_record else 'FAILED',
            }

        if send_in_app and user_id:
            target_user = get_object_or_404(User, id=user_id)
            notif = NotificationService.send_in_app(
                user=target_user,
                title=rendered['in_app_title'] or rendered['email_subject'],
                message=rendered['in_app_message'] or rendered['email_body_text'],
                notification_type=rendered['template'].notification_type,
                force=True,
            )
            in_app_result = {
                'id': notif.id if notif else None,
            }

        return Response({
            'template_code': code,
            'rendered_preview': {
                'email_subject': rendered['email_subject'],
                'email_body_html': rendered['email_body_html'],
                'email_body_text': rendered['email_body_text'],
                'in_app_title': rendered['in_app_title'],
                'in_app_message': rendered['in_app_message'],
            },
            'dispatched': {
                'email': email_result,
                'in_app': in_app_result,
            },
        }, status=status.HTTP_200_OK)
