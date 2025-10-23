# apps/sales/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ReservationViewSet,
    PaymentViewSet,
    ContractViewSet,
    SalesReportViewSet
)

# DefaultRouter, @action ile tanımlanan endpoint'ler için otomatik URL oluşturur.
# Bu, manuel URL sıralama hatalarını tamamen ortadan kaldırır.
router = DefaultRouter()
router.register(r'reservations', ReservationViewSet, basename='reservation')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'contracts', ContractViewSet, basename='contract')

# SalesReportViewSet'i de router'a kaydediyoruz.
# Artık export ve generate URL'leri otomatik olarak oluşturulacak.
router.register(r'reports', SalesReportViewSet, basename='report')

# urlpatterns artık çok daha temiz ve hataya kapalı!
urlpatterns = [
    path('', include(router.urls)),
]
