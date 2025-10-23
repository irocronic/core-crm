# apps/sales/models.py

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Reservation(models.Model):
    """Rezervasyon Modeli"""
    
    class Status(models.TextChoices):
        AKTIF = 'AKTIF', 'Aktif Rezervasyon'
        SATISA_DONUSTU = 'SATISA_DONUSTU', 'Satışa Dönüştü'
        IPTAL_EDILDI = 'IPTAL_EDILDI', 'İptal Edildi'
    
    class PaymentMethod(models.TextChoices):
        NAKIT = 'NAKIT', 'Nakit'
        KREDI_KARTI = 'KREDI_KARTI', 'Kredi Kartı'
        DEKONT = 'DEKONT', 'Banka Havalesi/Dekont'
        CEK = 'CEK', 'Çek'
    
    # İlişkiler
    property = models.OneToOneField(
        'properties.Property',
        on_delete=models.PROTECT,
        related_name='reservation',
        verbose_name='Gayrimenkul'
    )
    
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.PROTECT,
        related_name='reservations',
        verbose_name='Müşteri'
    )
    
    sales_rep = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='reservations',
        limit_choices_to={'role': 'SATIS_TEMSILCISI'},
        verbose_name='Satış Temsilcisi'
    )
    
    payment_plan_selected = models.ForeignKey(
        'properties.PaymentPlan',
        on_delete=models.PROTECT,
        related_name='reservations',
        verbose_name='Seçilen Ödeme Planı'
    )
    
    # Kaparo Bilgileri
    deposit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Kaparo Bedeli (TL)'
    )
    
    deposit_payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        verbose_name='Kaparo Ödeme Yöntemi'
    )
    
    deposit_receipt_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Kaparo Makbuz/Dekont No'
    )
    
    # Durum ve Tarihler
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AKTIF,
        verbose_name='Rezervasyon Durumu'
    )
    
    reservation_date = models.DateTimeField(
        default=timezone.now,
        verbose_name='Rezervasyon Tarihi'
    )
    
    expiry_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='Son Geçerlilik Tarihi',
        help_text='Rezervasyonun geçerlilik süresi (opsiyonel)'
    )
    
    # Notlar
    notes = models.TextField(
        blank=True,
        verbose_name='Rezervasyon Notları'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_reservations',
        verbose_name='Kaydı Oluşturan'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')
    
    class Meta:
        verbose_name = 'Rezervasyon'
        verbose_name_plural = 'Rezervasyonlar'
        ordering = ['-reservation_date']
    
    def __str__(self):
        return f"REZ-{self.id} | {self.customer.full_name} - {self.property}"
    
    def save(self, *args, **kwargs):
        """
        Model kaydedildiğinde post_save sinyali otomatik olarak tetiklenir.
        Mülk durumu güncelleme mantığı sinyallere taşındığı için buradan kaldırılmıştır.
        Bu metot, gelecekteki olası save override'ları için bir yer tutucu olarak kalabilir.
        """
        super().save(*args, **kwargs)
    
    @transaction.atomic
    def convert_to_sale(self):
        """
        Rezervasyonu satışa dönüştür.
        Bu işlem sadece `status` alanını günceller.
        Mülkün durumunu güncelleme işi `post_save` sinyali tarafından yapılır.
        """
        try:
            if self.status != self.Status.AKTIF:
                logger.warning(f"Sadece aktif rezervasyonlar satışa dönüştürülebilir: {self.id}")
                return False, "Sadece aktif rezervasyonlar satışa dönüştürülebilir"
            
            self.status = self.Status.SATISA_DONUSTU
            self.save(update_fields=['status']) # Bu satır sinyali tetikleyecektir.
            
            logger.info(f"Rezervasyon satışa dönüştürüldü: {self.id}")
            
            return True, "Rezervasyon başarıyla satışa dönüştürüldü"
            
        except Exception as e:
            logger.error(f"Rezervasyon satışa dönüştürme hatası: {e}", exc_info=True)
            raise
    
    @transaction.atomic
    def cancel(self, reason=''):
        """
        Rezervasyonu iptal et.
        Bu işlem rezervasyon durumunu günceller ve bekleyen ödemeleri iptal eder.
        Mülkün durumunu 'SATILABILIR' yapma işi `post_save` sinyali tarafından yapılır.
        """
        try:
            if self.status != self.Status.AKTIF:
                logger.warning(f"Sadece aktif rezervasyonlar iptal edilebilir: {self.id}")
                return False, "Sadece aktif rezervasyonlar iptal edilebilir"
            
            paid_payments = self.payments.filter(status=Payment.Status.ALINDI)
            if paid_payments.exists():
                logger.warning(f"Ödeme alınmış rezervasyon iptal edilmeye çalışıldı: {self.id}")
                return False, "Ödeme alınmış rezervasyonlar iptal edilemez. Lütfen ödemeleri iade edin."
            
            signed_contracts = self.contracts.filter(status=Contract.Status.IMZALANDI)
            if signed_contracts.exists():
                logger.warning(f"İmzalı sözleşmeli rezervasyon iptal edilmeye çalışıldı: {self.id}")
                return False, "İmzalı sözleşmeli rezervasyonlar iptal edilemez."
            
            self.status = self.Status.IPTAL_EDILDI
            self.notes = f"{self.notes}\n\nİptal Nedeni: {reason}" if reason else self.notes
            self.save(update_fields=['status', 'notes']) # Bu satır sinyali tetikleyecektir.
            
            # Bekleyen ödemeleri iptal et
            self.payments.filter(status__in=[Payment.Status.BEKLENIYOR, Payment.Status.GECIKTI]).update(
                status=Payment.Status.IPTAL
            )
            
            logger.info(f"Rezervasyon iptal edildi: {self.id} - Neden: {reason}")
            
            return True, "Rezervasyon başarıyla iptal edildi"
            
        except Exception as e:
            logger.error(f"Rezervasyon iptal hatası: {e}", exc_info=True)
            raise
    
    def is_expired(self):
        """Rezervasyon süresi dolmuş mu?"""
        if self.expiry_date and self.status == self.Status.AKTIF:
            return timezone.now().date() > self.expiry_date
        return False
    
    def get_remaining_amount(self):
        """Kalan ödeme tutarı"""
        plan_details = self.payment_plan_selected.details
        
        if self.payment_plan_selected.plan_type == 'PESIN':
            total_price = plan_details.get('cash_price', 0)
        else:
            total_price = plan_details.get('installment_price', 0)
        
        return Decimal(str(total_price)) - self.deposit_amount


# --- Payment, Contract, SalesReport modelleri burada değişikliğe uğramadan devam eder ---
# (Kısaltılmaması adına bu modelleri de aşağıya ekliyorum)

class Payment(models.Model):
    """Ödeme Takibi Modeli"""
    
    class PaymentType(models.TextChoices):
        KAPARO = 'KAPARO', 'Kaparo'
        PESINAT = 'PESINAT', 'Peşinat'
        TAKSIT = 'TAKSIT', 'Taksit'
        KALAN_ODEME = 'KALAN_ODEME', 'Kalan Ödeme'
    
    class PaymentMethod(models.TextChoices):
        NAKIT = 'NAKIT', 'Nakit'
        KREDI_KARTI = 'KREDI_KARTI', 'Kredi Kartı'
        HAVALE = 'HAVALE', 'Banka Havalesi'
        CEK = 'CEK', 'Çek'
    
    class Status(models.TextChoices):
        BEKLENIYOR = 'BEKLENIYOR', 'Ödeme Bekleniyor'
        ALINDI = 'ALINDI', 'Ödeme Alındı'
        GECIKTI = 'GECIKTI', 'Ödeme Gecikti'
        IPTAL = 'IPTAL', 'İptal Edildi'
    
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Rezervasyon'
    )
    
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        verbose_name='Ödeme Tipi'
    )
    
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Tutar (TL)'
    )
    
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
        verbose_name='Ödeme Yöntemi'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.BEKLENIYOR,
        verbose_name='Durum'
    )
    
    due_date = models.DateField(
        verbose_name='Vade Tarihi'
    )
    
    payment_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='Ödeme Tarihi'
    )
    
    receipt_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Makbuz/Dekont No'
    )
    
    installment_number = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Taksit Numarası',
        help_text='Taksit ödemesi ise kaçıncı taksit'
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name='Notlar'
    )
    
    recorded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_payments',
        verbose_name='Kaydeden'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')
    
    class Meta:
        verbose_name = 'Ödeme'
        verbose_name_plural = 'Ödemeler'
        ordering = ['due_date']
    
    def __str__(self):
        return f"{self.reservation} - {self.get_payment_type_display()} - {self.amount} TL"
    
    def mark_as_paid(self, payment_date=None, payment_method=None, receipt_number=''):
        """Ödemeyi tahsil edildi olarak işaretle"""
        self.status = self.Status.ALINDI
        self.payment_date = payment_date or timezone.now().date()
        
        if payment_method:
            self.payment_method = payment_method
        
        if receipt_number:
            self.receipt_number = receipt_number
        
        self.save(update_fields=['status', 'payment_date', 'payment_method', 'receipt_number'])
    
    def is_overdue(self):
        """Ödeme gecikti mi?"""
        if self.status == self.Status.BEKLENIYOR:
            return timezone.now().date() > self.due_date
        return False


class Contract(models.Model):
    """Satış Sözleşmesi Modeli"""
    
    class ContractType(models.TextChoices):
        REZERVASYON = 'REZERVASYON', 'Rezervasyon Sözleşmesi'
        SATIS = 'SATIS', 'Satış Sözleşmesi'
        ON_SOZLESME = 'ON_SOZLESME', 'Ön Sözleşme'
    
    class Status(models.TextChoices):
        TASLAK = 'TASLAK', 'Taslak'
        ONAY_BEKLIYOR = 'ONAY_BEKLIYOR', 'Onay Bekliyor'
        IMZALANDI = 'IMZALANDI', 'İmzalandı'
        IPTAL = 'IPTAL', 'İptal Edildi'
    
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='contracts',
        verbose_name='Rezervasyon'
    )
    
    contract_type = models.CharField(
        max_length=20,
        choices=ContractType.choices,
        default=ContractType.REZERVASYON,
        verbose_name='Sözleşme Tipi'
    )
    
    contract_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Sözleşme No'
    )
    
    contract_file = models.FileField(
        upload_to='contracts/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Sözleşme Dosyası (PDF)'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TASLAK,
        verbose_name='Durum'
    )
    
    contract_date = models.DateField(
        default=timezone.now,
        verbose_name='Sözleşme Tarihi'
    )
    
    signed_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='İmza Tarihi'
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name='Notlar'
    )
    
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_contracts',
        verbose_name='Oluşturan'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')
    
    class Meta:
        verbose_name = 'Sözleşme'
        verbose_name_plural = 'Sözleşmeler'
        ordering = ['-contract_date']
    
    def __str__(self):
        return f"{self.contract_number} - {self.get_contract_type_display()}"
    
    def mark_as_signed(self, signed_date=None):
        """Sözleşmeyi imzalandı olarak işaretle"""
        self.status = self.Status.IMZALANDI
        self.signed_date = signed_date or timezone.now().date()
        self.save(update_fields=['status', 'signed_date'])


class SalesReport(models.Model):
    """Satış Raporu Modeli (Dönemsel raporlar için)"""
    
    class ReportType(models.TextChoices):
        GENEL_Ozet = 'GENEL_Ozet', 'Genel Satış Özeti'
        TEMSILCI_PERFORMANS = 'TEMSILCI_PERFORMANS', 'Temsilci Performans Raporu'
        MUSTERI_KAYNAK = 'MUSTERI_KAYNAK', 'Müşteri Kaynak Raporu'
        GUNLUK = 'GUNLUK', 'Günlük Rapor'
        HAFTALIK = 'HAFTALIK', 'Haftalık Rapor'
        AYLIK = 'AYLIK', 'Aylık Rapor'
        YILLIK = 'YILLIK', 'Yıllık Rapor'
    
    report_type = models.CharField(
        max_length=30,
        choices=ReportType.choices,
        verbose_name='Rapor Tipi'
    )
    
    start_date = models.DateField(verbose_name='Başlangıç Tarihi')
    end_date = models.DateField(verbose_name='Bitiş Tarihi')
    
    statistics = models.JSONField(
        default=dict,
        verbose_name='İstatistikler'
    )
    
    report_file = models.FileField(
        upload_to='reports/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Rapor Dosyası (PDF)'
    )
    
    generated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Oluşturan'
    )
    
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    
    class Meta:
        verbose_name = 'Satış Raporu'
        verbose_name_plural = 'Satış Raporları'
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.start_date} / {self.end_date}"
