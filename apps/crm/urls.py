# apps/crm/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CustomerViewSet, ActivityViewSet, AppointmentViewSet, NoteViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'activities', ActivityViewSet, basename='activity')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'notes', NoteViewSet, basename='note')

urlpatterns = [
    path('', include(router.urls)),
]