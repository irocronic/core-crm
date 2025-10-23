# apps/sales/filters.py

import django_filters
from django.utils import timezone
from .models import Reservation, Payment


class ReservationFilter(django_filters.FilterSet):
    """Rezervasyon filtreleme"""

    customer_name = django_filters.CharFilter(
        field_name='customer__full_name',
        lookup_expr='icontains'
    )

    customer_phone = django_filters.CharFilter(
        field_name='customer__phone_number',
        lookup_expr='icontains'
    )
    
    project_name = django_filters.CharFilter(
        field_name='property__project__name', # Eğer Project modeli varsa
        lookup_expr='icontains'
    )

    property_type = django_filters.CharFilter(
        field_name='property__property_type'
    )

    reservation_date_after = django_filters.DateFilter(
        field_name='reservation_date',
        lookup_expr='gte'
    )

    reservation_date_before = django_filters.DateFilter(
        field_name='reservation_date',
        lookup_expr='lte'
    )

    min_deposit = django_filters.NumberFilter(
        field_name='deposit_amount',
        lookup_expr='gte'
    )

    max_deposit = django_filters.NumberFilter(
        field_name='deposit_amount',
        lookup_expr='lte'
    )

    # Müşteri ID'sine göre filtreleme
    customer_id = django_filters.NumberFilter(
        field_name='customer__id'
    )

    # 🔥 GÜNCELLEME: status filtresi artık birden fazla değeri işleyebilir
    status = django_filters.CharFilter(method='filter_by_status_in')

    class Meta:
        model = Reservation
        fields = ['status', 'sales_rep', 'deposit_payment_method', 'customer_id']

    # 🔥 YENİ METOT: Virgülle ayrılmış status değerlerini filtreler
    def filter_by_status_in(self, queryset, name, value):
        statuses = [status.strip() for status in value.split(',') if status.strip()]
        if statuses:
            return queryset.filter(status__in=statuses)
        return queryset


class PaymentFilter(django_filters.FilterSet):
    """Ödeme filtreleme"""

    reservation_id = django_filters.NumberFilter(field_name='reservation__id')

    customer_name = django_filters.CharFilter(
        field_name='reservation__customer__full_name',
        lookup_expr='icontains'
    )

    due_date_after = django_filters.DateFilter(
        field_name='due_date',
        lookup_expr='gte'
    )

    due_date_before = django_filters.DateFilter(
        field_name='due_date',
        lookup_expr='lte'
    )

    payment_date_after = django_filters.DateFilter(
        field_name='payment_date',
        lookup_expr='gte'
    )

    payment_date_before = django_filters.DateFilter(
        field_name='payment_date',
        lookup_expr='lte'
    )

    class Meta:
        model = Payment
        fields = ['payment_type', 'payment_method', 'status']
