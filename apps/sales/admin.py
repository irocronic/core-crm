# apps/sales/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import Reservation, Payment, Contract, SalesReport


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ['payment_type', 'amount', 'due_date', 'payment_date', 'status', 'installment_number']
    readonly_fields = ['recorded_by']


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0
    fields = ['contract_type', 'contract_number', 'status', 'contract_date', 'signed_date']
    readonly_fields = ['created_by']


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'customer', 'property', 'sales_rep',
        'deposit_amount', 'status_badge', 'reservation_date'
    ]
    list_filter = ['status', 'deposit_payment_method', 'reservation_date', 'sales_rep']
    search_fields = [
        'customer__full_name', 'customer__phone_number',
        'property__project_name', 'property__unit_number'
    ]
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Rezervasyon Bilgileri', {
            'fields': ('property', 'customer', 'sales_rep', 'status')
        }),
        ('Ödeme Planı', {
            'fields': ('payment_plan_selected',)
        }),
        ('Kaparo Bilgileri', {
            'fields': (
                'deposit_amount', 'deposit_payment_method',
                'deposit_receipt_number'
            )
        }),
        ('Tarihler', {
            'fields': ('reservation_date', 'expiry_date')
        }),
        ('Notlar', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PaymentInline, ContractInline]
    
    def status_badge(self, obj):
        colors = {
            'AKTIF': 'green',
            'SATISA_DONUSTU': 'blue',
            'IPTAL_EDILDI': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Durum'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'reservation', 'payment_type', 'amount',
        'due_date', 'payment_date', 'status_badge', 'installment_number'
    ]
    list_filter = ['status', 'payment_type', 'payment_method', 'due_date']
    search_fields = [
        'reservation__customer__full_name',
        'receipt_number'
    ]
    readonly_fields = ['recorded_by', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Ödeme Bilgileri', {
            'fields': ('reservation', 'payment_type', 'amount', 'installment_number')
        }),
        ('Durum ve Tarihler', {
            'fields': ('status', 'due_date', 'payment_date')
        }),
        ('Ödeme Detayları', {
            'fields': ('payment_method', 'receipt_number')
        }),
        ('Notlar', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('recorded_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'BEKLENIYOR': 'orange',
            'ALINDI': 'green',
            'GECIKTI': 'red',
            'IPTAL': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Durum'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        'contract_number', 'reservation', 'contract_type',
        'status', 'contract_date', 'signed_date'
    ]
    list_filter = ['contract_type', 'status', 'contract_date']
    search_fields = ['contract_number', 'reservation__customer__full_name']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Sözleşme Bilgileri', {
            'fields': ('reservation', 'contract_type', 'contract_number', 'status')
        }),
        ('Tarihler', {
            'fields': ('contract_date', 'signed_date')
        }),
        ('Dosya', {
            'fields': ('contract_file',)
        }),
        ('Notlar', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SalesReport)
class SalesReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_type', 'start_date', 'end_date',
        'generated_by', 'generated_at'
    ]
    list_filter = ['report_type', 'generated_at']
    search_fields = ['generated_by__username']
    readonly_fields = ['statistics', 'generated_by', 'generated_at']
    
    fieldsets = (
        ('Rapor Bilgileri', {
            'fields': ('report_type', 'start_date', 'end_date')
        }),
        ('İstatistikler', {
            'fields': ('statistics',)
        }),
        ('Dosya', {
            'fields': ('report_file',)
        }),
        ('Metadata', {
            'fields': ('generated_by', 'generated_at')
        }),
    )