# apps/crm/filters.py

import django_filters
from django.utils import timezone
from .models import Customer, Appointment, Activity # Activity import edildi


class CustomerFilter(django_filters.FilterSet):
    """Müşteri filtreleme"""

    full_name = django_filters.CharFilter(lookup_expr='icontains')
    phone_number = django_filters.CharFilter(lookup_expr='icontains')
    interested_in = django_filters.CharFilter(lookup_expr='icontains')

    min_budget = django_filters.NumberFilter(field_name='budget_min', lookup_expr='gte')
    max_budget = django_filters.NumberFilter(field_name='budget_max', lookup_expr='lte')

    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = Customer
        fields = ['source', 'assigned_to', 'created_by']


class AppointmentFilter(django_filters.FilterSet):
    """Randevu filtreleme"""

    date = django_filters.DateFilter(field_name='appointment_date', lookup_expr='date')
    date_after = django_filters.DateTimeFilter(field_name='appointment_date', lookup_expr='gte')
    date_before = django_filters.DateTimeFilter(field_name='appointment_date', lookup_expr='lte')

    class Meta:
        model = Appointment
        fields = ['customer', 'sales_rep', 'status']

# **** YENİ: ActivityFilter ****
class ActivityFilter(django_filters.FilterSet):
    """Aktivite Filtreleme"""
    customer_name = django_filters.CharFilter(field_name='customer__full_name', lookup_expr='icontains')
    created_by_name = django_filters.CharFilter(field_name='created_by__username', lookup_expr='icontains')

    # Tarih Filtreleri
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = Activity
        fields = ['customer', 'activity_type', 'outcome_score', 'created_by', 'start_date', 'end_date']
# **** YENİ SONU ****
