# apps/users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User
from fcm_django.models import FCMDevice


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'team', 'is_active_employee']
    list_filter = ['role', 'is_active_employee', 'is_staff', 'is_superuser']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'phone_number']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Ek Bilgiler', {
            'fields': ('role', 'phone_number', 'profile_picture', 'team', 'is_active_employee')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Ek Bilgiler', {
            'fields': ('role', 'phone_number', 'profile_picture', 'team', 'is_active_employee')
        }),
    )


# FCMDevice admin zaten fcm_django paketinde kayıtlı
# Özelleştirmek isterseniz:
class CustomFCMDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'device_id', 'type', 'active', 'date_created']
    list_filter = ['type', 'active']
    search_fields = ['user__username', 'device_id', 'name']
    readonly_fields = ['date_created']

# Eğer fcm_django'nun default admin'ini override etmek isterseniz:
# admin.site.unregister(FCMDevice)
# admin.site.register(FCMDevice, CustomFCMDeviceAdmin)