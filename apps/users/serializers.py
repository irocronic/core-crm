# apps/users/serializers.py

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User
from fcm_django.models import FCMDevice


class UserSerializer(serializers.ModelSerializer):
    """Kullanıcı listesi ve detay serializeri"""
    
    team_name = serializers.CharField(source='team.get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_display', 'phone_number', 'profile_picture',
            'team', 'team_name', 'is_active_employee',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']


class UserCreateSerializer(serializers.ModelSerializer):
    """Yeni kullanıcı oluşturma serializeri"""
    
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'role', 'phone_number',
            'profile_picture', 'team'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Şifreler eşleşmiyor."
            })
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Kullanıcı güncelleme serializeri"""
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone_number',
            'profile_picture', 'role', 'team', 'is_active_employee'
        ]


class ChangePasswordSerializer(serializers.Serializer):
    """Şifre değiştirme serializeri"""
    
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                "new_password": "Yeni şifreler eşleşmiyor."
            })
        return attrs


# ==========================================
# 🔥 FCM DEVICE SERIALIZER GÜNCELLENDI
# ==========================================
class FCMDeviceSerializer(serializers.ModelSerializer):
    """FCM cihaz token serializeri - fcm_django.models.FCMDevice kullanıyor"""
    
    class Meta:
        model = FCMDevice
        fields = ['id', 'name', 'registration_id', 'device_id', 'type', 'active', 'date_created']
        read_only_fields = ['id', 'date_created']
    
    def validate_registration_id(self, value):
        """Registration ID benzersiz olmalı"""
        user = self.context['request'].user
        
        # Aynı kullanıcının başka bir cihazında bu token varsa güncelle
        existing = FCMDevice.objects.filter(registration_id=value).exclude(user=user).first()
        if existing:
            raise serializers.ValidationError('Bu token başka bir kullanıcıya ait')
        
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """Kullanıcı profil bilgileri serializeri"""
    
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    team_name = serializers.CharField(source='team.get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_display', 'phone_number', 'profile_picture',
            'team', 'team_name', 'is_active_employee',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'username', 'date_joined', 'last_login']