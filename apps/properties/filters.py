# apps/properties/filters.py

import django_filters
from .models import Property


class PropertyFilter(django_filters.FilterSet):
    """Gayrimenkul filtreleme"""
    
    # project_name -> project olarak değiştirildi (ID ile filtreleme)
    project = django_filters.NumberFilter(field_name='project__id')
    room_count = django_filters.CharFilter(lookup_expr='icontains')
    block = django_filters.CharFilter(lookup_expr='iexact')
    
    min_cash_price = django_filters.NumberFilter(field_name='cash_price', lookup_expr='gte')
    max_cash_price = django_filters.NumberFilter(field_name='cash_price', lookup_expr='lte')
    
    min_area = django_filters.NumberFilter(field_name='net_area_m2', lookup_expr='gte')
    max_area = django_filters.NumberFilter(field_name='net_area_m2', lookup_expr='lte')
    
    min_floor = django_filters.NumberFilter(field_name='floor', lookup_expr='gte')
    max_floor = django_filters.NumberFilter(field_name='floor', lookup_expr='lte')
    
    class Meta:
        model = Property
        fields = ['property_type', 'status', 'facade', 'project', 'block', 'floor']
