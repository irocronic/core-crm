# apps/users/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import update_session_auth_hash
from django.db import models
import logging

from .models import User
from fcm_django.models import FCMDevice
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    ChangePasswordSerializer, FCMDeviceSerializer, UserProfileSerializer
)
from .permissions import IsAdmin, IsSalesManager, CanManageTeam
from .services import UserService

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    """
    Kullanıcı yönetimi ViewSet
    
    list: Tüm kullanıcıları listele (Admin, Satış Müdürü)
    retrieve: Kullanıcı detayı (Admin, Satış Müdürü veya kendisi)
    create: Yeni kullanıcı oluştur (Admin)
    update: Kullanıcı güncelle (Admin veya kendisi)
    delete: Kullanıcı sil (Admin)
    """
    
    queryset = User.objects.filter(is_active_employee=True)
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'team', 'is_active_employee']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'phone_number']
    ordering_fields = ['date_joined', 'last_name']
    ordering = ['-date_joined']
    
    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            permission_classes = [IsAdmin]
        elif self.action in ['list', 'my_team', 'sales_reps']:
            permission_classes = [IsSalesManager]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        elif self.action == 'change_password':
            return ChangePasswordSerializer
        elif self.action == 'profile':
            return UserProfileSerializer
        return UserSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_admin():
            return User.objects.all()
        
        if user.is_sales_manager():
            return User.objects.filter(
                models.Q(team=user) |
                models.Q(id=user.id)
            )
        
        return User.objects.filter(id=user.id)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def profile(self, request):
        """
        Giriş yapan kullanıcının profil bilgileri
        GET /api/v1/users/profile/
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    # DEĞİŞİKLİK: 'patch' metodu eklendi ve yorumlar düzeltildi.
    @action(detail=False, methods=['put', 'patch'], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        """
        Giriş yapan kullanıcının profil bilgilerini güncelle
        PUT veya PATCH /api/v1/users/update_profile/
        """
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        response_serializer = UserProfileSerializer(request.user, context={'request': request})
        
        return Response({
            'message': 'Profil başarıyla güncellendi',
            'user': response_serializer.data
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        """
        Kullanıcı şifre değiştirme
        POST /api/v1/users/change_password/
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Mevcut şifre hatalı'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        update_session_auth_hash(request, user)
        
        logger.info(f"Kullanıcı şifre değiştirdi: {user.username}")
        
        return Response({
            'message': 'Şifreniz başarıyla değiştirildi'
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsSalesManager])
    def my_team(self, request):
        """
        Satış müdürünün ekip üyelerini listele
        GET /api/v1/users/my_team/
        """
        team_members = request.user.get_team_members()
        serializer = self.get_serializer(team_members, many=True)
        
        return Response({
            'team_leader': UserSerializer(request.user).data,
            'team_members': serializer.data,
            'total_members': team_members.count()
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def statistics(self, request):
        """
        Giriş yapan kullanıcının rolüne göre
        dashboard istatistiklerini getirir.
        GET /api/v1/users/statistics/
        """
        user = request.user
        try:
            stats = UserService.get_user_statistics(user)
            return Response(stats)
        except Exception as e:
            logger.error(f"Kullanıcı istatistikleri alınırken hata: {e}", exc_info=True)
            return Response(
                {'error': 'İstatistikler alınamadı'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], permission_classes=[IsSalesManager])
    def sales_reps(self, request):
        """
        Müşteri atama için aktif satış temsilcilerini listele
        GET /api/v1/users/sales_reps/
        """
        if request.user.is_admin():
            sales_reps = User.objects.filter(
                role=User.Role.SATIS_TEMSILCISI,
                is_active_employee=True
            )
        else:
            sales_reps = User.objects.filter(
                role=User.Role.SATIS_TEMSILCISI,
                team=request.user,
                is_active_employee=True
            )
        
        serializer = self.get_serializer(sales_reps, many=True)
        return Response(serializer.data)


class FCMDeviceViewSet(viewsets.ModelViewSet):
    """
    FCM cihaz token yönetimi
    """
    
    queryset = FCMDevice.objects.all()
    serializer_class = FCMDeviceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    
    def get_queryset(self):
        return FCMDevice.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        registration_id = serializer.validated_data.get('registration_id')
        device_id = serializer.validated_data.get('device_id')
        
        existing_device = FCMDevice.objects.filter(
            registration_id=registration_id
        ).first()
        
        if existing_device:
            existing_device.user = self.request.user
            existing_device.name = serializer.validated_data.get('name', existing_device.name)
            existing_device.device_id = device_id
            existing_device.type = serializer.validated_data.get('type', existing_device.type)
            existing_device.active = True
            existing_device.save()
            
            serializer.instance = existing_device
            logger.info(f"FCM cihaz güncellendi: {existing_device.name} - User: {self.request.user.username}")
        else:
            device = serializer.save(user=self.request.user)
            logger.info(f"Yeni FCM cihaz kaydedildi: {device.name} - User: {self.request.user.username}")
    
    @action(detail=False, methods=['post'])
    def deactivate(self, request):
        registration_id = request.data.get('registration_id')
        
        if not registration_id:
            return Response(
                {'error': 'registration_id gerekli'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_count = FCMDevice.objects.filter(
            user=request.user,
            registration_id=registration_id
        ).update(active=False)
        
        if updated_count > 0:
            logger.info(f"FCM cihaz deaktif edildi - User: {request.user.username}")
            return Response({'message': 'Cihaz deaktif edildi'})
        else:
            return Response(
                {'error': 'Cihaz bulunamadı'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def deactivate_all(self, request):
        updated_count = FCMDevice.objects.filter(
            user=request.user,
            active=True
        ).update(active=False)
        
        logger.info(f"Kullanıcının tüm FCM cihazları deaktif edildi ({updated_count} adet) - User: {request.user.username}")
        
        return Response({
            'message': f'{updated_count} cihaz deaktif edildi'
        })
