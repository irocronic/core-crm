# apps/users/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
import logging

logger = logging.getLogger(__name__)


class User(AbstractUser):
    """
    Özelleştirilmiş kullanıcı modeli
    Rol bazlı yetkilendirme için genişletilmiştir
    """
    
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        SATIS_MUDUR = 'SATIS_MUDUR', 'Satış Müdürü'
        SATIS_TEMSILCISI = 'SATIS_TEMSILCISI', 'Satış Temsilcisi'
        ASISTAN = 'ASISTAN', 'Asistan'
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.SATIS_TEMSILCISI,
        verbose_name='Rol'
    )
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Telefon numarası '+999999999' formatında olmalıdır. 15 karaktere kadar."
    )
    
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        verbose_name='Telefon Numarası'
    )
    
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        verbose_name='Profil Fotoğrafı'
    )
    
    team = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_members',
        limit_choices_to={'role': Role.SATIS_MUDUR},
        verbose_name='Bağlı Olduğu Satış Müdürü'
    )
    
    is_active_employee = models.BooleanField(
        default=True,
        verbose_name='Aktif Çalışan'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')
    
    class Meta:
        verbose_name = 'Kullanıcı'
        verbose_name_plural = 'Kullanıcılar'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"
    
    def is_admin(self):
        return self.role == self.Role.ADMIN
    
    def is_sales_manager(self):
        return self.role == self.Role.SATIS_MUDUR
    
    def is_sales_rep(self):
        return self.role == self.Role.SATIS_TEMSILCISI
    
    def is_assistant(self):
        return self.role == self.Role.ASISTAN
    
    def get_team_members(self):
        """Satış müdürü ise ekibindeki üyeleri döner"""
        if self.is_sales_manager():
            return User.objects.filter(team=self, is_active_employee=True)
        return User.objects.none()