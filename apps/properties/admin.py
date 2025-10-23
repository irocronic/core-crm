# apps/properties/admin.py

from django.contrib import admin
from .models import Property, PropertyImage, PropertyDocument, PaymentPlan, Project # Project import edildi


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'created_at']
    search_fields = ['name', 'location']
    # YENİ: fieldsets'e resim alanlarını ekliyoruz.
    fieldsets = (
        ('Proje Bilgileri', {
            'fields': ('name', 'location', 'description')
        }),
        ('Tapu Bilgileri', {
            'fields': ('island', 'parcel', 'block')
        }),
        ('Proje Görselleri', {
            'fields': ('project_image', 'site_plan_image')
        }),
    )


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ['image', 'image_type', 'title', 'order']


class PropertyDocumentInline(admin.TabularInline):
    model = PropertyDocument
    extra = 1
    fields = ['document', 'document_type', 'title', 'uploaded_by']
    readonly_fields = ['uploaded_by']


class PaymentPlanInline(admin.TabularInline):
    model = PaymentPlan
    extra = 1
    fields = ['plan_type', 'name', 'is_active']


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = [
        '__str__', # GÜNCELLENDİ
        'property_type', 'room_count', 'cash_price', 'status',
        'created_at'
    ]
    list_filter = ['status', 'property_type', 'project', 'block'] # 'project_name' -> 'project'
    search_fields = ['project__name', 'block', 'unit_number', 'room_count'] # 'project_name' -> 'project__name'
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Proje ve Konum', {
            'fields': ('project', 'block', 'floor', 'unit_number', 'facade') # 'project_name' -> 'project'
        }),
        ('Mülk Özellikleri', {
            'fields': ('property_type', 'room_count', 'gross_area_m2', 'net_area_m2')
        }),
        ('Fiyatlandırma', {
            'fields': ('cash_price', 'installment_price')
        }),
        ('Durum ve Açıklama', {
            'fields': ('status', 'description')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PropertyImageInline, PropertyDocumentInline, PaymentPlanInline]
    
    def save_model(self, request, obj, form, change):
        if not change:  # Yeni kayıt
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

# Diğer Admin sınıfları aynı kalacak...
@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ['property', 'image_type', 'title', 'order', 'uploaded_at']
    list_filter = ['image_type', 'uploaded_at']
    search_fields = ['property__project__name', 'title'] # 'property__project_name'


@admin.register(PropertyDocument)
class PropertyDocumentAdmin(admin.ModelAdmin):
    list_display = ['property', 'document_type', 'title', 'uploaded_by', 'uploaded_at']
    list_filter = ['document_type', 'uploaded_at']
    search_fields = ['property__project__name', 'title'] # 'property__project_name'
    readonly_fields = ['uploaded_by', 'uploaded_at']


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = ['property', 'plan_type', 'name', 'is_active', 'created_at']
    list_filter = ['plan_type', 'is_active', 'created_at']
    search_fields = ['property__project__name', 'name'] # 'property__project_name'
    readonly_fields = ['created_at', 'updated_at']
