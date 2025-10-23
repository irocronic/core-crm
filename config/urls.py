# config/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

urlpatterns = [
    # Admin Panel
    path('admin/', admin.site.urls),
    
    # API v1 Endpoints
    path('api/v1/users/', include('apps.users.urls')),
    path('api/v1/properties/', include('apps.properties.urls')),
    path('api/v1/crm/', include('apps.crm.urls')),
    path('api/v1/sales/', include('apps.sales.urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# 🔥 GÜNCELLEME:
# DEBUG=True olduğunda dosyaları sunmak için.
# MEDIA_URL (Firebase) artık lokal sunuma ihtiyaç duymaz.
# Sadece STATIC_URL (lokal CSS/JS) sunulur.
if settings.DEBUG:
    # Lokal statik dosyaları (CSS, JS) sun
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Firebase kullanılıyorsa, bu satıra artık gerek yok.
    # Eğer Firebase ayarları (yukarıdaki settings) yapılmadıysa
    # ve lokal depolama kullanılıyorsa, bu satır GEREKLİDİR.
    # Ayarlarımızda 'if/else' olduğu için burayı güvende tutmak adına
    # 'MEDIA_ROOT'un dolu olup olmadığını kontrol edebiliriz.
    if settings.MEDIA_ROOT:
         urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# 🔥 GÜNCELLEME SONU 🔥


# Admin customization
admin.site.site_header = "RealtyFlow CRM"
admin.site.site_title = "RealtyFlow Admin"
admin.site.index_title = "Yönetim Paneli"
