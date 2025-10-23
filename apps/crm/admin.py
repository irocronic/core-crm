# apps/crm/admin.py

from django.contrib import admin
from .models import Customer, Activity, Appointment, Note


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ['activity_type', 'outcome_score', 'notes', 'created_by', 'created_at']
    readonly_fields = ['created_by', 'created_at']


class AppointmentInline(admin.TabularInline):
    model = Appointment
    extra = 0
    fields = ['appointment_date', 'sales_rep', 'status', 'location']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'phone_number', 'email', 'assigned_to',
        'source', 'created_by', 'created_at'
    ]
    list_filter = ['source', 'assigned_to', 'created_at']
    search_fields = ['full_name', 'phone_number', 'email']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Müşteri Bilgileri', {
            'fields': ('full_name', 'phone_number', 'email')
        }),
        ('Atama ve Kaynak', {
            'fields': ('assigned_to', 'source', 'created_by')
        }),
        ('İlgi Alanı ve Bütçe', {
            'fields': ('interested_in', 'budget_min', 'budget_max')
        }),
        ('Notlar', {
            'fields': ('notes',)
        }),
        ('Tarihler', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ActivityInline, AppointmentInline]
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['customer', 'activity_type', 'outcome_score', 'created_by', 'created_at']
    list_filter = ['activity_type', 'outcome_score', 'created_at']
    search_fields = ['customer__full_name', 'notes']
    readonly_fields = ['created_by', 'created_at']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['customer', 'sales_rep', 'appointment_date', 'status', 'reminder_sent']
    list_filter = ['status', 'reminder_sent', 'appointment_date']
    search_fields = ['customer__full_name', 'sales_rep__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['customer', 'is_important', 'created_by', 'created_at']
    list_filter = ['is_important', 'created_at']
    search_fields = ['customer__full_name', 'content']
    readonly_fields = ['created_by', 'created_at']