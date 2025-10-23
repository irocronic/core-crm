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

# Media files (development only)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin customization
admin.site.site_header = "RealtyFlow CRM"
admin.site.site_title = "RealtyFlow Admin"
admin.site.index_title = "Yönetim Paneli"
