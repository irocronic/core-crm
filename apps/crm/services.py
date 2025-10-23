# apps/crm/services.py

from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.db import transaction
from .models import Customer, Activity, Appointment
from apps.users.services import NotificationService as BaseNotificationService
import logging

logger = logging.getLogger(__name__)


class CustomerService:
    """Müşteri iş mantığı servisi"""
    
    # ==========================================
    # 🔥 TRANSACTION MANAGEMENT EKLENDI
    # ==========================================
    @staticmethod
    @transaction.atomic
    def create_customer_with_activity(customer_data, activity_data, created_by):
        """
        Müşteri oluştur ve ilk aktiviteyi kaydet
        
        Transaction ile wrap edildi: Hata olursa tüm işlemler geri alınır
        
        Args:
            customer_data (dict): Müşteri bilgileri
            activity_data (dict): İlk aktivite bilgileri
            created_by (User): Oluşturan kullanıcı
            
        Returns:
            Customer: Oluşturulan müşteri instance
        """
        try:
            customer = Customer.objects.create(
                **customer_data,
                created_by=created_by
            )
            
            logger.info(f"Müşteri oluşturuldu: {customer.full_name}")
            
            if activity_data:
                Activity.objects.create(
                    customer=customer,
                    created_by=created_by,
                    **activity_data
                )
                logger.info(f"İlk aktivite kaydedildi: {customer.full_name}")
            
            # Eğer atandığı satış temsilcisi varsa bildirim gönder
            if customer.assigned_to:
                NotificationService.send_customer_assigned_notification(
                    sales_rep=customer.assigned_to,
                    customer=customer,
                    assigned_by=created_by
                )
            
            return customer
            
        except Exception as e:
            logger.error(f"Müşteri oluşturma hatası: {e}", exc_info=True)
            raise
    
    @staticmethod
    def get_customer_timeline(customer):
        """
        Müşterinin tüm aktivite ve randevu geçmişini kronolojik sırala
        """
        activities = list(customer.activities.all())
        appointments = list(customer.appointments.all())
        
        # Birleştir ve tarihe göre sırala
        timeline = []
        
        for activity in activities:
            timeline.append({
                'type': 'activity',
                'date': activity.created_at,
                'data': activity
            })
        
        for appointment in appointments:
            timeline.append({
                'type': 'appointment',
                'date': appointment.appointment_date,
                'data': appointment
            })
        
        timeline.sort(key=lambda x: x['date'], reverse=True)
        return timeline
    
    @staticmethod
    def get_sales_rep_statistics(sales_rep):
        """Satış temsilcisinin müşteri istatistikleri"""
        customers = Customer.objects.filter(assigned_to=sales_rep)
        
        stats = {
            'total_customers': customers.count(),
            'hot_leads': 0,
            'total_activities': Activity.objects.filter(created_by=sales_rep).count(),
            'upcoming_appointments': Appointment.objects.filter(
                sales_rep=sales_rep,
                appointment_date__gte=timezone.now(),
                status=Appointment.Status.PLANLANDI
            ).count(),
            'appointments_today': Appointment.objects.filter(
                sales_rep=sales_rep,
                appointment_date__date=timezone.now().date(),
                status=Appointment.Status.PLANLANDI
            ).count(),
        }
        
        # Sıcak müşteriler
        for customer in customers:
            if customer.get_win_probability() >= 75:
                stats['hot_leads'] += 1
        
        return stats


class NotificationService(BaseNotificationService):
    """CRM bildirimleri servisi"""
    
    @staticmethod
    def send_customer_assigned_notification(sales_rep, customer, assigned_by):
        """Müşteri atandığında bildirim gönder"""
        title = "Yeni Müşteri Atandı"
        body = f"{customer.full_name} adlı müşteri size atandı."
        
        data = {
            'type': 'customer_assigned',
            'customer_id': str(customer.id),
            'customer_name': customer.full_name,
            'assigned_by': assigned_by.get_full_name()
        }
        
        success = NotificationService.send_push_notification(
            user=sales_rep,
            title=title,
            body=body,
            data=data
        )
        
        if success:
            logger.info(f"Müşteri atama bildirimi gönderildi: {customer.full_name} -> {sales_rep.get_full_name()}")
        
        return success
    
    @staticmethod
    def send_customer_transferred_notification(new_sales_rep, old_sales_rep, customer, transferred_by):
        """Müşteri transfer edildiğinde bildirim gönder"""
        title = "Müşteri Transfer Edildi"
        body = f"{customer.full_name} adlı müşteri size transfer edildi."
        
        data = {
            'type': 'customer_transferred',
            'customer_id': str(customer.id),
            'customer_name': customer.full_name,
            'transferred_by': transferred_by.get_full_name()
        }
        
        return NotificationService.send_push_notification(
            user=new_sales_rep,
            title=title,
            body=body,
            data=data
        )
    
    @staticmethod
    def send_appointment_reminder(appointment, minutes_before=15):
        """Randevu hatırlatması gönder"""
        title = "Randevu Hatırlatması"
        body = f"{appointment.customer.full_name} ile {minutes_before} dakika sonra randevunuz var."
        
        data = {
            'type': 'appointment_reminder',
            'appointment_id': str(appointment.id),
            'customer_name': appointment.customer.full_name,
            'appointment_date': appointment.appointment_date.isoformat()
        }
        
        return NotificationService.send_push_notification(
            user=appointment.sales_rep,
            title=title,
            body=body,
            data=data
        )