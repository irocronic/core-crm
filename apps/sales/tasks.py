# apps/sales/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Payment, Reservation
from .services import PaymentService, ReportService, NotificationService


@shared_task
def send_payment_reminders():
    """
    Yaklaşan ödemeler için hatırlatma gönder
    3 gün içinde vadesi dolacak ödemeler için
    """
    today = timezone.now().date()
    reminder_date = today + timedelta(days=3)
    
    upcoming_payments = Payment.objects.filter(
        status=Payment.Status.BEKLENIYOR,
        due_date=reminder_date
    ).select_related('reservation', 'reservation__sales_rep')
    
    sent_count = 0
    
    for payment in upcoming_payments:
        success = NotificationService.send_payment_reminder(payment)
        if success:
            sent_count += 1
    
    return f"{sent_count} ödeme hatırlatması gönderildi"


@shared_task
def check_overdue_payments():
    """
    Gecikmiş ödemeleri kontrol et ve bildirim gönder
    Her gün çalışır
    """
    overdue_payments = PaymentService.get_overdue_payments()
    
    sent_count = 0
    
    for payment in overdue_payments:
        # Durumu GECIKTI olarak güncelle
        if payment.status == Payment.Status.BEKLENIYOR:
            payment.status = Payment.Status.GECIKTI
            payment.save(update_fields=['status'])
        
        # Bildirim gönder
        success = NotificationService.send_overdue_payment_notification(payment)
        if success:
            sent_count += 1
    
    return f"{sent_count} gecikmiş ödeme bildirimi gönderildi"


@shared_task
def check_expired_reservations():
    """
    Süresi dolmuş rezervasyonları kontrol et
    Her gün çalışır
    """
    today = timezone.now().date()
    
    expired_reservations = Reservation.objects.filter(
        status=Reservation.Status.AKTIF,
        expiry_date__lt=today
    )
    
    expired_count = 0
    
    for reservation in expired_reservations:
        # Rezervasyonu iptal et
        success, message = reservation.cancel(reason="Rezervasyon süresi doldu (otomatik iptal)")
        if success:
            expired_count += 1
    
    return f"{expired_count} rezervasyon otomatik olarak iptal edildi"


@shared_task
def send_daily_sales_summary():
    """
    Günlük satış özeti raporu oluştur ve gönder
    Her gün saat 18:00'de çalışır
    """
    report = ReportService.generate_daily_report()
    
    if report:
        # Raporu satış müdürlerine gönder
        from apps.users.models import User
        from apps.users.services import NotificationService as BaseNotificationService
        
        sales_managers = User.objects.filter(
            role=User.Role.SATIS_MUDUR,
            is_active_employee=True
        )
        
        title = "Günlük Satış Raporu"
        body = f"Bugünün satış raporu hazır. {report.statistics['reservations']['total']} rezervasyon."
        
        data = {
            'type': 'daily_report',
            'report_id': str(report.id),
        }
        
        sent_count = 0
        for manager in sales_managers:
            success = BaseNotificationService.send_push_notification(
                user=manager,
                title=title,
                body=body,
                data=data
            )
            if success:
                sent_count += 1
        
        return f"Günlük rapor oluşturuldu ve {sent_count} satış müdürüne gönderildi"
    
    return "Günlük rapor oluşturulamadı"


@shared_task
def generate_weekly_report():
    """
    Haftalık satış raporu oluştur
    Her Pazartesi sabahı çalışır
    """
    today = timezone.now().date()
    start_date = today - timedelta(days=7)
    
    from apps.users.models import User
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    
    report = ReportService.generate_sales_report(
        report_type='HAFTALIK',
        start_date=start_date,
        end_date=today,
        generated_by=admin_user
    )
    
    return f"Haftalık rapor oluşturuldu: {report.id}"


@shared_task
def generate_monthly_report():
    """
    Aylık satış raporu oluştur
    Her ayın 1'inde çalışır
    """
    today = timezone.now().date()
    # Geçen ayın ilk ve son günü
    first_day_last_month = today.replace(day=1) - timedelta(days=1)
    first_day_last_month = first_day_last_month.replace(day=1)
    last_day_last_month = today.replace(day=1) - timedelta(days=1)
    
    from apps.users.models import User
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    
    report = ReportService.generate_sales_report(
        report_type='AYLIK',
        start_date=first_day_last_month,
        end_date=last_day_last_month,
        generated_by=admin_user
    )
    
    return f"Aylık rapor oluşturuldu: {report.id}"