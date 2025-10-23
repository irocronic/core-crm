# apps/crm/models.py

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
# YENİ IMPORT
from django.db.models import F, Q # Q importunu kontrol et, yoksa ekle


class Customer(models.Model): # Customer modeli olduğu gibi kalır...
    """Müşteri (Lead) Modeli"""

    class Source(models.TextChoices): #
        REFERANS = 'REFERANS', 'Referans' #
        WEB_SITESI = 'WEB_SITESI', 'Web Sitesi' #
        SOSYAL_MEDYA = 'SOSYAL_MEDYA', 'Sosyal Medya' #
        TABELA = 'TABELA', 'Tabela' #
        OFIS_ZIYARETI = 'OFIS_ZIYARETI', 'Ofis Ziyareti' #
        FUAR = 'FUAR', 'Fuar' #
        DIGER = 'DIGER', 'Diğer' #

    full_name = models.CharField( #
        max_length=255, #
        verbose_name='Ad Soyad' #
    )

    phone_regex = RegexValidator( #
        regex=r'^\+?1?\d{9,15}$', #
        message="Telefon numarası '+999999999' formatında olmalıdır." #
    )

    phone_number = models.CharField( #
        validators=[phone_regex], #
        max_length=17, #
        unique=True, #
        verbose_name='Telefon Numarası' #
    )

    email = models.EmailField( #
        blank=True, #
        null=True, #
        verbose_name='E-posta' #
    )

    assigned_to = models.ForeignKey( #
        'users.User', #
        on_delete=models.SET_NULL, #
        null=True, #
        related_name='assigned_customers', #
        limit_choices_to={'role': 'SATIS_TEMSILCISI'}, #
        verbose_name='Atandığı Satış Temsilcisi' #
    )

    source = models.CharField( #
        max_length=20, #
        choices=Source.choices, #
        default=Source.DIGER, #
        verbose_name='Müşteri Kaynağı' #
    )

    interested_in = models.CharField( #
        max_length=255, #
        blank=True, #
        verbose_name='İlgilendiği Daire Tipleri', #
        help_text='Örn: 2+1, 3+1' #
    )

    budget_min = models.DecimalField( #
        max_digits=15, #
        decimal_places=2, #
        blank=True, #
        null=True, #
        verbose_name='Minimum Bütçe (TL)' #
    )

    budget_max = models.DecimalField( #
        max_digits=15, #
        decimal_places=2, #
        blank=True, #
        null=True, #
        verbose_name='Maksimum Bütçe (TL)' #
    )

    notes = models.TextField( #
        blank=True, #
        verbose_name='Genel Notlar' #
    )

    created_by = models.ForeignKey( #
        'users.User', #
        on_delete=models.SET_NULL, #
        null=True, #
        related_name='created_customers', #
        verbose_name='Kaydı Oluşturan' #
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi') #
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi') #

    class Meta: #
        verbose_name = 'Müşteri' #
        verbose_name_plural = 'Müşteriler' #
        ordering = ['-created_at'] #

    def __str__(self): #
        return f"{self.full_name} - {self.phone_number}" #

    def get_latest_activity(self): #
        """En son aktiviteyi getir""" #
        return self.activities.order_by('-created_at').first() #

    def get_win_probability(self): #
        """En son aktiviteye göre kazanma olasılığını getir""" #
        latest = self.get_latest_activity() #
        return latest.outcome_score if latest else 0 #

    def has_appointment_today(self): #
        """Bugün randevusu var mı?""" #
        today = timezone.now().date() #
        return self.appointments.filter( #
            appointment_date__date=today, #
            status=Appointment.Status.PLANLANDI #
        ).exists() #


class Activity(models.Model): #
    """Müşteri Aktivitesi (Görüşme, Arama vb.) Modeli""" #

    class ActivityType(models.TextChoices): #
        GORUSME = 'GORUSME', 'Yüz Yüze Görüşme' #
        TELEFON = 'TELEFON', 'Telefon Görüşmesi' #
        EMAIL = 'EMAIL', 'E-posta' #
        RANDEVU = 'RANDEVU', 'Randevu' #
        WHATSAPP = 'WHATSAPP', 'WhatsApp' #

    # **** YENİ: Alt Tür Seçenekleri ****
    class SubType(models.TextChoices):
        ILK_GELEN = 'ILK_GELEN', 'İlk Gelen'
        ARA_GELEN = 'ARA_GELEN', 'Ara Gelen'
        # Gelecekte başka alt türler eklenebilir
    # **** YENİ SONU ****

    customer = models.ForeignKey( #
        Customer, #
        on_delete=models.CASCADE, #
        related_name='activities', #
        verbose_name='Müşteri' #
    )

    activity_type = models.CharField( #
        max_length=20, #
        choices=ActivityType.choices, #
        verbose_name='Aktivite Tipi' #
    )

    # **** YENİ ALAN ****
    sub_type = models.CharField(
        max_length=20,
        choices=SubType.choices,
        blank=True, # Boş olabilir (her aktivitenin alt türü olmayabilir)
        null=True,  # Veritabanında NULL olabilir
        verbose_name='Alt Tür',
        help_text="Aktivitenin alt kategorisi (örn: İlk Gelen, Ara Gelen)"
    )
    # **** YENİ ALAN SONU ****

    notes = models.TextField( #
        verbose_name='Görüşme Notları' #
    )

    outcome_score = models.IntegerField( #
        choices=[ #
            (10, '%10 - Düşük İlgi'), #
            (25, '%25 - Az İlgili'), #
            (50, '%50 - Orta Düzey İlgi'), #
            (75, '%75 - Yüksek İlgi'), #
            (100, '%100 - Çok Yakın'), #
        ], #
        default=50, #
        verbose_name='Kazanma Olasılığı' #
    )

    next_follow_up_date = models.DateTimeField( #
        blank=True, #
        null=True, #
        verbose_name='Sonraki Takip Tarihi' #
    )

    created_by = models.ForeignKey( #
        'users.User', #
        on_delete=models.SET_NULL, #
        null=True, #
        related_name='created_activities', #
        verbose_name='Oluşturan' #
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi') #

    class Meta: #
        verbose_name = 'Aktivite' #
        verbose_name_plural = 'Aktiviteler' #
        ordering = ['-created_at'] #

    def __str__(self): #
        # Alt tür varsa onu da göster
        sub_type_str = f" ({self.get_sub_type_display()})" if self.sub_type else ""
        return f"{self.customer.full_name} - {self.get_activity_type_display()}{sub_type_str} - {self.created_at.strftime('%d.%m.%Y')}" #


class Appointment(models.Model): # Appointment modeli olduğu gibi kalır...
    """Randevu Modeli"""

    class Status(models.TextChoices):
        PLANLANDI = 'PLANLANDI', 'Planlandı'
        TAMAMLANDI = 'TAMAMLANDI', 'Tamamlandı'
        IPTAL_EDILDI = 'IPTAL_EDILDI', 'İptal Edildi'
        GELMEDI = 'GELMEDI', 'Gelmedi'

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='appointments',
        verbose_name='Müşteri' #
    )

    sales_rep = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='appointments',
        limit_choices_to={'role': 'SATIS_TEMSILCISI'},
        verbose_name='Satış Temsilcisi' #
    )

    appointment_date = models.DateTimeField(
        verbose_name='Randevu Tarihi ve Saati' #
    )

    location = models.CharField( #
        max_length=255, #
        blank=True, #
        verbose_name='Randevu Yeri', #
        help_text='Örn: Satış Ofisi, Şantiye' #
    )

    status = models.CharField( #
        max_length=20, #
        choices=Status.choices, #
        default=Status.PLANLANDI, #
        verbose_name='Durum' #
    )

    notes = models.TextField( #
        blank=True, #
        verbose_name='Notlar' #
    )

    reminder_sent = models.BooleanField( #
        default=False, #
        verbose_name='Hatırlatma Gönderildi mi?' #
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi') #
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi') #

    class Meta: #
        verbose_name = 'Randevu' #
        verbose_name_plural = 'Randevular' #
        ordering = ['appointment_date'] #

    def __str__(self): #
        return f"{self.customer.full_name} - {self.appointment_date.strftime('%d.%m.%Y %H:%M')}" #

    def is_upcoming(self): #
        """Gelecekte bir randevu mu?""" #
        return self.appointment_date > timezone.now() and self.status == self.Status.PLANLANDI #

    def is_today(self): #
        """Bugün mü?""" #
        return self.appointment_date.date() == timezone.now().date() #

    def time_until_appointment(self): #
        """Randevuya kalan süre (dakika)""" #
        if self.appointment_date > timezone.now(): #
            delta = self.appointment_date - timezone.now() #
            return int(delta.total_seconds() / 60) #
        return 0 #


class Note(models.Model): # Note modeli olduğu gibi kalır...
    """Genel Not Modeli (Müşteri bazlı ekstra notlar)"""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE, #
        related_name='extra_notes', #
        verbose_name='Müşteri' #
    )

    content = models.TextField( #
        verbose_name='Not İçeriği' #
    )

    is_important = models.BooleanField( #
        default=False, #
        verbose_name='Önemli Not' #
    )

    created_by = models.ForeignKey( #
        'users.User', #
        on_delete=models.SET_NULL, #
        null=True, #
        verbose_name='Oluşturan' #
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi') #

    class Meta: #
        verbose_name = 'Not' #
        verbose_name_plural = 'Notlar' #
        ordering = ['-created_at'] #

    def __str__(self): #
        return f"{self.customer.full_name} - Not ({self.created_at.strftime('%d.%m.%Y')})" #
