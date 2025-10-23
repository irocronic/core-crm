# apps/properties/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PropertyViewSet,
    PropertyImageViewSet,
    PropertyDocumentViewSet,
    PaymentPlanViewSet,
    ProjectViewSet # YENİ IMPORT
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project') # YENİ KAYIT
router.register(r'', PropertyViewSet, basename='property')
router.register(r'images', PropertyImageViewSet, basename='property-image')
router.register(r'documents', PropertyDocumentViewSet, basename='property-document')
router.register(r'payment-plans', PaymentPlanViewSet, basename='payment-plan')

urlpatterns = [
    path('', include(router.urls)),
]
