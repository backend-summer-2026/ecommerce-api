from django.urls import path

from apps.notifications.views import (
    AdminBroadcastNotificationView,
    AdminEmailCancelView,
    AdminEmailNotificationDetailView,
    AdminEmailNotificationListView,
    AdminEmailRetryView,
    AdminInAppNotificationListView,
    AdminNotificationTemplateDetailView,
    AdminNotificationTemplateListCreateView,
    AdminNotificationTemplateTestSendView,
    NotificationClearReadView,
    NotificationDetailView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationMarkUnreadView,
    NotificationPreferenceView,
    NotificationUnreadCountView,
)

app_name = 'notifications'

urlpatterns = [
    # Customer summary and bulk operations (placed before <int:pk> to avoid collision)
    path('unread-count/', NotificationUnreadCountView.as_view(), name='unread-count'),
    path('read-all/', NotificationMarkAllReadView.as_view(), name='mark-all-read'),
    path('clear-read/', NotificationClearReadView.as_view(), name='clear-read'),
    path('preferences/', NotificationPreferenceView.as_view(), name='preferences'),

    # Admin Management Endpoints
    path('admin/in-app/', AdminInAppNotificationListView.as_view(), name='admin-in-app-list'),
    path('admin/in-app/broadcast/', AdminBroadcastNotificationView.as_view(), name='admin-broadcast'),
    path('admin/emails/', AdminEmailNotificationListView.as_view(), name='admin-email-list'),
    path('admin/emails/<int:pk>/', AdminEmailNotificationDetailView.as_view(), name='admin-email-detail'),
    path('admin/emails/<int:pk>/retry/', AdminEmailRetryView.as_view(), name='admin-email-retry'),
    path('admin/emails/<int:pk>/cancel/', AdminEmailCancelView.as_view(), name='admin-email-cancel'),
    path('admin/templates/', AdminNotificationTemplateListCreateView.as_view(), name='admin-template-list'),
    path('admin/templates/<str:code>/', AdminNotificationTemplateDetailView.as_view(), name='admin-template-detail'),
    path('admin/templates/<str:code>/test-send/', AdminNotificationTemplateTestSendView.as_view(), name='admin-template-test-send'),

    # Customer In-App Notification Listing & Single Notification Details
    path('', NotificationListView.as_view(), name='notification-list'),
    path('<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('<int:pk>/read/', NotificationMarkReadView.as_view(), name='mark-read'),
    path('<int:pk>/unread/', NotificationMarkUnreadView.as_view(), name='mark-unread'),
]
