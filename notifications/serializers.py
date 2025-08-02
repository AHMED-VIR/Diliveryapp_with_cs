from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    related_object = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'message_ar',
            'message_en',
            'is_read',
            'created_at',
            'related_object'
        ]
        read_only_fields = fields

    def get_related_object(self, obj):
        if not obj.content_object:
            return None
        
        # Customize this based on your model serialization needs
        return {
            'type': obj.content_type.model,
            'id': obj.object_id
        }