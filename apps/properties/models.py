# apps/properties/models.py

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import json


class Project(models.Model):
    """Gayrimenkul Projesi Modeli"""
    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Proje Adı'
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Konum'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Açıklama'
    )
    island = models.CharField(
        max_length=50,
        verbose_name='Ada',
        blank=True,
        null=True
    )
    parcel = models.CharField(
        max_length=50,
        verbose_name='Pafta',
        blank=True,
        null=True
    )
    block = models.CharField(
        max_length=50,
        verbose_name='Blok (Genel)',
        blank=True,
        null=True,
        help_text="Proje tek blok ise burayı doldurun."
    )
    # YENİ EKLENDİ
    project_image = models.ImageField(
        upload_to='projects/images/',
        blank=True,
        null=True,
        verbose_name='Proje Görseli'
    )
    # YENİ EKLENDİ
    site_plan_image = models.ImageField(
        upload_to='projects/site_plans/',
        blank=True,
        null=True,
        verbose_name='Proje Vaziyet Planı'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')

    class Meta:
        verbose_name = 'Proje'
        verbose_name_plural = 'Projeler'
        ordering = ['name']

    def __str__(self):
        return self.name


class Property(models.Model):
    """Gayrimenkul (Mülk) Modeli"""
    
    class PropertyType(models.TextChoices):
        DAIRE = 'DAIRE', 'Daire'
        VILLA = 'VILLA', 'Villa'
        OFIS = 'OFIS', 'Ofis'
    
    class Status(models.TextChoices):
        SATILABILIR = 'SATILABILIR', 'Satılabilir'
        REZERVE = 'REZERVE', 'Rezerve'
        SATILDI = 'SATILDI', 'Satıldı'
        PASIF = 'PASIF', 'Pasif'
    
    class Facade(models.TextChoices):
        GUNEY = 'GUNEY', 'Güney'
        KUZEY = 'KUZEY', 'Kuzey'
        DOGU = 'DOGU', 'Doğu'
        BATI = 'BATI', 'Batı'
        GUNEY_DOGU = 'GUNEY_DOGU', 'Güney-Doğu'
        GUNEY_BATI = 'GUNEY_BATI', 'Güney-Batı'
        KUZEY_DOGU = 'KUZEY_DOGU', 'Kuzey-Doğu'
        KUZEY_BATI = 'KUZEY_BATI', 'Kuzey-Batı'
    
    # Proje ve Konum Bilgileri
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='properties',
        verbose_name='Proje',
        null=True
    )
    
    # island alanı Project modeline taşındı
    # parcel alanı Project modeline taşındı
    
    block = models.CharField(
        max_length=50,
        verbose_name='Blok',
        # GÜNCELLEME: Projede birden fazla blok olabileceği için opsiyonel
        blank=True,
        help_text="Projede birden fazla blok varsa burayı doldurun."
    )
    
    floor = models.IntegerField(
        verbose_name='Kat',
        validators=[MinValueValidator(-5)]  # -5: Bodrum katlar için
    )
    
    unit_number = models.CharField(
        max_length=20,
        verbose_name='Bağımsız Bölüm No'
    )
    
    facade = models.CharField(
        max_length=20,
        choices=Facade.choices,
        verbose_name='Cephe'
    )
    
    # Mülk Özellikleri
    property_type = models.CharField(
        max_length=10,
        choices=PropertyType.choices,
        default=PropertyType.DAIRE,
        verbose_name='Mülk Tipi'
    )
    
    room_count = models.CharField(
        max_length=50,
        verbose_name='Oda Sayısı',
        help_text='Örn: 1+1, 2+1, 3+1 Dubleks'
    )
    
    gross_area_m2 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Brüt Alan (m²)'
    )
    
    net_area_m2 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Net Alan (m²)'
    )
    
    # Fiyatlandırma
    cash_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Peşin Fiyat (TL)'
    )
    
    installment_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        blank=True,
        null=True,
        verbose_name='Vadeli Fiyat (TL)'
    )
    
    # Durum
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.SATILABILIR,
        verbose_name='Durum'
    )
    
    # Açıklama
    description = models.TextField(
        blank=True,
        verbose_name='Açıklama'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_properties',
        verbose_name='Oluşturan'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')
    
    class Meta:
        verbose_name = 'Gayrimenkul'
        verbose_name_plural = 'Gayrimenkuller'
        ordering = ['project', 'block', 'floor', 'unit_number']
        unique_together = ['project', 'block', 'floor', 'unit_number']
    
    def __str__(self):
        return f"{self.project.name} - {self.block} Blok - Kat:{self.floor} - No:{self.unit_number}"
    
    def is_available(self):
        """Mülk satılabilir durumda mı?"""
        return self.status == self.Status.SATILABILIR
    
    def reserve(self):
        """Mülkü rezerve et"""
        if self.is_available():
            self.status = self.Status.REZERVE
            self.save(update_fields=['status'])
            return True
        return False
    
    def mark_as_sold(self):
        """Mülkü satıldı olarak işaretle"""
        if self.status == self.Status.REZERVE:
            self.status = self.Status.SATILDI
            self.save(update_fields=['status'])
            return True
        return False
    
    def cancel_reservation(self):
        """Rezervasyonu iptal et, mülkü tekrar satılabilir yap"""
        if self.status == self.Status.REZERVE:
            self.status = self.Status.SATILABILIR
            self.save(update_fields=['status'])
            return True
        return False

# Diğer modeller (PropertyImage, PropertyDocument, PaymentPlan) aynı kalacak...
class PropertyImage(models.Model):
    """Gayrimenkul Görselleri"""
    
    class ImageType(models.TextChoices):
        EXTERIOR = 'EXTERIOR', 'Dış Görünüm'
        INTERIOR = 'INTERIOR', 'İç Görünüm'
        FLOOR_PLAN = 'FLOOR_PLAN', 'Kat Planı'
        SITE_PLAN = 'SITE_PLAN', 'Vaziyet Planı'
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Gayrimenkul'
    )
    
    image = models.ImageField(
        upload_to='properties/images/%Y/%m/',
        verbose_name='Görsel'
    )
    
    image_type = models.CharField(
        max_length=20,
        choices=ImageType.choices,
        default=ImageType.INTERIOR,
        verbose_name='Görsel Tipi'
    )
    
    title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Başlık'
    )
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Sıralama'
    )
    
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Yüklenme Tarihi')
    
    class Meta:
        verbose_name = 'Gayrimenkul Görseli'
        verbose_name_plural = 'Gayrimenkul Görselleri'
        ordering = ['property', 'order']
    
    def __str__(self):
        return f"{self.property} - {self.get_image_type_display()}"


class PropertyDocument(models.Model):
    """Gayrimenkul Belgeleri (Ruhsat, tapular vb.)"""
    
    class DocumentType(models.TextChoices):
        RUHSAT = 'RUHSAT', 'İnşaat Ruhsatı'
        TAPU = 'TAPU', 'Tapu'
        ISKAN = 'ISKAN', 'İskan Belgesi'
        KAT_IRTIFAKI = 'KAT_IRTIFAKI', 'Kat İrtifakı'
        DIGER = 'DIGER', 'Diğer'
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Gayrimenkul'
    )
    
    document = models.FileField(
        upload_to='properties/documents/%Y/%m/',
        verbose_name='Belge'
    )
    
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        verbose_name='Belge Tipi'
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name='Başlık'
    )
    
    uploaded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Yükleyen'
    )
    
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Yüklenme Tarihi')
    
    class Meta:
        verbose_name = 'Gayrimenkul Belgesi'
        verbose_name_plural = 'Gayrimenkul Belgeleri'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.property} - {self.title}"


class PaymentPlan(models.Model):
    """Ödeme Planı Modeli"""
    
    class PlanType(models.TextChoices):
        PESIN = 'PESIN', 'Peşin'
        VADELI = 'VADELI', 'Vadeli'
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='payment_plans',
        verbose_name='Gayrimenkul'
    )
    
    plan_type = models.CharField(
        max_length=10,
        choices=PlanType.choices,
        verbose_name='Plan Tipi'
    )
    
    name = models.CharField(
        max_length=255,
        verbose_name='Plan Adı',
        help_text='Örn: %25 Peşin, 120 Ay Vade'
    )
    
    # Vadeli plan detayları (JSON formatında)
    details = models.JSONField(
        default=dict,
        verbose_name='Plan Detayları',
        help_text='Peşinat, taksit sayısı, aylık taksit vb.'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktif'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')
    
    class Meta:
        verbose_name = 'Ödeme Planı'
        verbose_name_plural = 'Ödeme Planları'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.property} - {self.name}"
    
    def get_details_display(self):
        """Ödeme planı detaylarını okunabilir formatta döner"""
        if self.plan_type == self.PlanType.PESIN:
            return f"Peşin Fiyat: {self.details.get('cash_price', 0)} TL"
        
        details_text = f"""
        Vadeli Fiyat: {self.details.get('installment_price', 0)} TL
        Peşinat: %{self.details.get('down_payment_percent', 0)} ({self.details.get('down_payment_amount', 0)} TL)
        Taksit Sayısı: {self.details.get('installment_count', 0)} Ay
        Aylık Taksit: {self.details.get('monthly_installment', 0)} TL
        """
        
        if self.details.get('interest_rate'):
            details_text += f"\nVade Farkı: %{self.details.get('interest_rate', 0)}"
        
        return details_text.strip()
