# apps/crm/tasks.py

from celery import shared_task
from django.utils import timezone
from .models import Appointment
from .services import NotificationService


@shared_task
def send_appointment_reminders():
    """
    15 dakika sonraki randevular için hatırlatma gönder
    Her 5 dakikada bir çalışır (celery beat ile)
    """
    now = timezone.now()
    reminder_time = now + timezone.timedelta(minutes=15)
    
    # 15 dakika sonraki randevuları bul (±2 dakika tolerans)
    appointments = Appointment.objects.filter(
        appointment_date__gte=reminder_time - timezone.timedelta(minutes=2),
        appointment_date__lte=reminder_time + timezone.timedelta(minutes=2),
        status=Appointment.Status.PLANLANDI,
        reminder_sent=False
    )
    
    sent_count = 0
    
    for appointment in appointments:
        success = NotificationService.send_appointment_reminder(appointment)
        
        if success:
            appointment.reminder_sent = True
            appointment.save(update_fields=['reminder_sent'])
            sent_count += 1
    
    return f"{sent_count} randevu hatırlatması gönderildi"


@shared_task
def check_follow_up_reminders():
    """
    Takip tarihi gelen müşteriler için hatırlatma gönder
    """
    from .models import Activity
    
    now = timezone.now()
    today = now.date()
    
    # Bugün takip edilmesi gereken aktiviteler
    activities = Activity.objects.filter(
        next_follow_up_date__date=today,
        next_follow_up_date__lte=now
    ).select_related('customer', 'created_by')
    
    sent_count = 0
    
    for activity in activities:
        title = "Müşteri Takip Hatırlatması"
        body = f"{activity.customer.full_name} ile görüşme zamanı geldi."
        
        data = {
            'type': 'follow_up_reminder',
            'customer_id': str(activity.customer.id),
            'customer_name': activity.customer.full_name,
            'activity_id': str(activity.id)
        }
        
        success = NotificationService.send_push_notification(
            user=activity.created_by,
            title=title,
            body=body,
            data=data
        )
        
        if success:
            sent_count += 1
    
    return f"{sent_count} takip hatırlatması gönderildi"