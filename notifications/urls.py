from django.urls import path
from .views import (
    NotificationListView,
    MarkAsReadView,
    UnreadCountView,
    MarkAllAsReadView
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),  # Changed from 'notifications/'
    path('<int:notification_id>/read/', MarkAsReadView.as_view(), name='mark-read'),
    path('unread-count/', UnreadCountView.as_view(), name='unread-count'),
    path('mark-all-read/', MarkAllAsReadView.as_view(), name='mark-all-read'),
]