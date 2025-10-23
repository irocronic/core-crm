# apps/users/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import UserViewSet, FCMDeviceViewSet

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')
router.register(r'fcm-devices', FCMDeviceViewSet, basename='fcm-device')

urlpatterns = [
    # JWT Authentication
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User endpoints
    path('', include(router.urls)),
]