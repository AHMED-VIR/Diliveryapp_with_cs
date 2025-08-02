from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('product_approved', 'Product Approved'),
        ('product_rejected', 'Product Rejected'),
        ('order_created', 'Order Created'),
        ('order_shipped', 'Order Shipped'),
        ('system_alert', 'System Alert'),
        ('wishlist_discount', 'Wishlist Discount')
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_notifications'  # Changed to unique name
    )
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message_ar = models.TextField()
    message_en = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-created_at']
        db_table = 'notifications_notification'