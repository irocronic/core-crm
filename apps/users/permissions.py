# apps/users/permissions.py

from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """Sadece Admin rolüne sahip kullanıcılar"""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin()


class IsSalesManager(permissions.BasePermission):
    """Satış Müdürü veya Admin"""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_sales_manager() or request.user.is_admin())
        )


class IsSalesRep(permissions.BasePermission):
    """Satış Temsilcisi, Satış Müdürü veya Admin"""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_sales_rep() or request.user.is_sales_manager() or request.user.is_admin())
        )


class IsAssistant(permissions.BasePermission):
    """Asistan veya üst roller"""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['ASISTAN', 'SATIS_TEMSILCISI', 'SATIS_MUDUR', 'ADMIN']
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Obje sahibi veya sadece okuma yetkisi"""
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return obj == request.user or request.user.is_admin()


class CanManageTeam(permissions.BasePermission):
    """Ekip yönetimi yetkisi (Satış Müdürü veya Admin)"""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_sales_manager() or request.user.is_admin())
        )
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        
        if request.user.is_sales_manager():
            return obj.team == request.user or obj == request.user
        
        return False