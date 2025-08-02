from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Notification
from .serializers import NotificationSerializer
from django.utils import timezone
from django.db.models import Q

class NotificationListView(APIView):
    """
    List all notifications for the authenticated user
    Supports filtering by read/unread status and notification type
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get query parameters
        is_read = request.query_params.get('is_read', None)
        notification_type = request.query_params.get('type', None)
        
        # Base queryset
        notifications = request.user.user_notifications.all().order_by('-created_at')
        
        # Apply filters
        if is_read is not None:
            notifications = notifications.filter(is_read=is_read.lower() == 'true')
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)
        
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


class MarkAsReadView(APIView):
    """
    Mark a specific notification as read
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            user=request.user
        )
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()  # Add this field to your model if needed
            notification.save()
        return Response({'status': 'marked as read'}, status=status.HTTP_200_OK)


class UnreadCountView(APIView):
    """
    Get count of unread notifications
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = request.user.user_notifications.filter(is_read=False).count()
        return Response({'unread_count': count})


class MarkAllAsReadView(APIView):
    """
    Mark all notifications as read for the user
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = request.user.user_notifications.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()  # Requires read_at field in model
        )
        return Response({'status': f'marked {updated} notifications as read'})


class NotificationDetailView(APIView):
    """
    Retrieve a specific notification and mark as read when viewed
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            user=request.user
        )
        
        # Mark as read when retrieved
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            
        serializer = NotificationSerializer(notification)
        return Response(serializer.data)