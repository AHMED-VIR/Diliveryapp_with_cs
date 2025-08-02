# profiles/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Profile

User = get_user_model()

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['image', 'bio']  # الصورة والبيو فقط

class UserProfileDisplaySerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name',
            'phone_number', 'address', 'email', 'profile',
        ]

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name',
            'phone_number', 'address', 'email', 'profile'
        ]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        profile = instance.profile

        # تحديث بيانات المستخدم
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # تحديث بيانات البروفايل (bio و image فقط)
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        return instance
from rest_framework import serializers
from accounts.models import User, Profile

class PublicUserProfileSerializer(serializers.ModelSerializer):
    bio = serializers.CharField(source="profile.bio", allow_blank=True, read_only=True)
    image = serializers.ImageField(source="profile.image", read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'role', 'phone_number', 'address', 'bio', 'image']
