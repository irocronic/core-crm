# apps/users/services.py

from django.db.models import Q, Count
from django.utils import timezone # Gerekli import eklendi
import logging

from .models import User
from fcm_django.models import FCMDevice

logger = logging.getLogger(__name__)

# Firebase Admin SDK imports
try:
    from firebase_admin import messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("Firebase Admin SDK bulunamadı. Push notification özellikleri devre dışı.")


class UserService:
    """Kullanıcı yönetimi iş mantığı"""

    @staticmethod
    def get_available_sales_reps(sales_manager=None):
        """
        Müşteri ataması için uygun satış temsilcilerini getir
        Eğer sales_manager verilirse, onun ekibinden getirir
        """
        queryset = User.objects.filter(
            role=User.Role.SATIS_TEMSILCISI,
            is_active_employee=True
        ) # [cite: 552]

        if sales_manager and sales_manager.is_sales_manager():
            queryset = queryset.filter(team=sales_manager)

        return queryset

    @staticmethod
    def get_user_statistics(user):
        """
        Kullanıcı istatistiklerini getir

        🔥 GÜNCELLEME: Bugünkü aktivite ve satış sayıları eklendi.
        🔥 YENİ GÜNCELLEME: 'todays_activities' ve 'todays_sales' artık TÜM kullanıcıların toplamını gösteriyor.
        """ # [cite: 553]
        # Lazy import to avoid circular dependency
        from apps.crm.models import Customer, Activity, Appointment
        from apps.sales.models import Reservation

        stats = {}
        today = timezone.now().date() # Bugünün tarihi alındı

        # ==========================================================
        # 🔥 TÜM KULLANICILAR İÇİN BUGÜNKÜ TOPLAM AKTİVİTE VE SATIŞLAR
        # ==========================================================
        todays_activities_count = Activity.objects.filter(
            created_at__date=today
        ).count() # [cite: 554]

        todays_sales_count = Reservation.objects.filter(
            status=Reservation.Status.SATISA_DONUSTU,
            updated_at__date=today # Satışa dönüştüğü tarih (güncellenme tarihi)
        ).count() # [cite: 555]
        # ==========================================================
        # 🔥 TOPLAM HESAPLAMA SONU
        # ==========================================================


        if user.is_sales_rep():
            # 🔥 DÜZELTME: assigned_to VE created_by kontrolü
            my_customers = Customer.objects.filter(
                Q(assigned_to=user) | Q(created_by=user)
            ).distinct() # [cite: 556]

            # Temsilcinin sadece KENDİSİNE ait bugünkü aktiviteleri ve satışları (loglama için)
            rep_todays_activities = Activity.objects.filter(
                created_by=user,
                created_at__date=today
            ).count() # [cite: 556]
            rep_todays_sales = Reservation.objects.filter(
                sales_rep=user,
                status=Reservation.Status.SATISA_DONUSTU,
                updated_at__date=today
            ).count() # [cite: 557]

            stats = {
                'total_customers': my_customers.count(), # [cite: 558]
                'total_activities': Activity.objects.filter(created_by=user).count(), # [cite: 558]
                'total_reservations': Reservation.objects.filter(
                    sales_rep=user,
                    status=Reservation.Status.AKTIF
                ).count(), # [cite: 558]
                'total_sales': Reservation.objects.filter(
                    sales_rep=user,
                    status=Reservation.Status.SATISA_DONUSTU
                ).count(), # [cite: 559]
                # 🔥 GÜNCELLEME: Genel toplam sayılar kullanılıyor
                'todays_activities': todays_activities_count,
                'todays_sales': todays_sales_count,
            }

            # 🔥 DEBUG LOG
            logger.info(
                f"📊 Sales Rep Stats - User: {user.username}, "
                f"Customers: {stats['total_customers']}, "
                f"Activities: {stats['total_activities']}, " # [cite: 561]
                f"Reservations: {stats['total_reservations']}, " # [cite: 561]
                f"Sales: {stats['total_sales']}, " # [cite: 561]
                f"Today Act (Self): {rep_todays_activities}, " # Kendi bugünkü aktivitesi (log için)
                f"Today Sales (Self): {rep_todays_sales}, " # Kendi bugünkü satışı (log için)
                f"Today Act (Total): {stats['todays_activities']}, " # Gösterilen Toplam
                f"Today Sales (Total): {stats['todays_sales']}" # Gösterilen Toplam
            ) # [cite: 562]

        elif user.is_sales_manager():
            team_members = user.get_team_members() # [cite: 562]

            # 🔥 DÜZELTME: Satış müdürünün kendisi de dahil
            all_team = list(team_members) + [user]

            # Müdürün sadece EKİBİNE ait bugünkü aktiviteleri ve satışları (loglama için)
            team_todays_activities = Activity.objects.filter(
                created_by__in=all_team,
                created_at__date=today
            ).count() # [cite: 563]
            team_todays_sales = Reservation.objects.filter(
                sales_rep__in=all_team,
                status=Reservation.Status.SATISA_DONUSTU,
                updated_at__date=today
            ).count() # [cite: 564]

            stats = {
                'team_size': team_members.count(), # [cite: 564]
                'team_total_customers': Customer.objects.filter(
                    Q(assigned_to__in=all_team) | Q(created_by__in=all_team)
                ).distinct().count(), # [cite: 565]
                'team_total_reservations': Reservation.objects.filter(
                    sales_rep__in=all_team,
                    status=Reservation.Status.AKTIF
                ).count(), # [cite: 565]
                'team_total_sales': Reservation.objects.filter(
                    sales_rep__in=all_team,
                    status=Reservation.Status.SATISA_DONUSTU
                ).count(), # [cite: 566]
                # 🔥 GÜNCELLEME: Genel toplam sayılar kullanılıyor
                'todays_activities': todays_activities_count,
                'todays_sales': todays_sales_count,
            }

            # 🔥 DEBUG LOG
            logger.info(
                f"📊 Sales Manager Stats - User: {user.username}, "
                f"Team Size: {stats['team_size']}, "
                f"Team Customers: {stats['team_total_customers']}, " # [cite: 568]
                f"Team Reservations: {stats['team_total_reservations']}, " # [cite: 568]
                f"Team Sales: {stats['team_total_sales']}, " # [cite: 568]
                f"Today Act (Team): {team_todays_activities}, " # Ekibin bugünkü aktivitesi (log için)
                f"Today Sales (Team): {team_todays_sales}, " # Ekibin bugünkü satışı (log için)
                f"Today Act (Total): {stats['todays_activities']}, " # Gösterilen Toplam
                f"Today Sales (Total): {stats['todays_sales']}" # Gösterilen Toplam
            ) # [cite: 569]

        elif user.is_assistant():
            stats = {
                'total_customers_created': Customer.objects.filter(created_by=user).count(), # [cite: 569]
                # 🔥 GÜNCELLEME: Genel toplam sayılar kullanılıyor (Zaten doğruydu)
                'todays_activities': todays_activities_count, # [cite: 569]
                'todays_sales': todays_sales_count, # [cite: 570]
            }

            # 🔥 DEBUG LOG
            logger.info(
                f"📊 Assistant Stats - User: {user.username}, "
                f"Created Customers: {stats['total_customers_created']}, "
                f"Today Act (Total): {stats['todays_activities']}, " # [cite: 571]
                f"Today Sales (Total): {stats['todays_sales']}" # [cite: 571]
            )

        elif user.is_admin():
            # 🔥 YENİ: Admin için genel istatistikler
            stats = {
                'total_users': User.objects.filter(is_active_employee=True).count(), # [cite: 571]
                'total_customers': Customer.objects.count(), # [cite: 572]
                'total_properties': 0,  # Property modeli import edilirse eklenebilir # [cite: 572]
                'total_reservations': Reservation.objects.filter(
                    status=Reservation.Status.AKTIF
                ).count(), # [cite: 572]
                'total_sales': Reservation.objects.filter(
                    status=Reservation.Status.SATISA_DONUSTU
                ).count(), # [cite: 573]
                # 🔥 GÜNCELLEME: Genel toplam sayılar kullanılıyor (Zaten doğruydu)
                'todays_activities': todays_activities_count, # [cite: 573]
                'todays_sales': todays_sales_count, # [cite: 574]
            }

            # Property sayısını güvenli şekilde al
            try:
                from apps.properties.models import Property
                stats['total_properties'] = Property.objects.count() # [cite: 574]
            except ImportError: # [cite: 575]
                pass # [cite: 575]

            # 🔥 DEBUG LOG
            logger.info(
                f"📊 Admin Stats - User: {user.username}, "
                f"Total Users: {stats['total_users']}, "
                f"Total Customers: {stats['total_customers']}, "
                f"Total Reservations: {stats['total_reservations']}, " # [cite: 576]
                f"Total Sales: {stats['total_sales']}, " # [cite: 576]
                f"Today Act (Total): {stats['todays_activities']}, " # [cite: 576]
                f"Today Sales (Total): {stats['todays_sales']}" # [cite: 576]
            )

        return stats

    @staticmethod
    def assign_customer_to_rep(customer, sales_rep, assigned_by):
        """
        Müşteriyi satış temsilcisine ata ve bildirim gönder
        """ # [cite: 577]
        from apps.crm.services import NotificationService

        customer.assigned_to = sales_rep
        customer.save(update_fields=['assigned_to'])

        # Bildirim gönder
        NotificationService.send_customer_assigned_notification(
            sales_rep=sales_rep,
            customer=customer, # [cite: 578]
            assigned_by=assigned_by # [cite: 578]
        )

        logger.info(f"Müşteri atandı: {customer.full_name} -> {sales_rep.get_full_name()}")

        return customer


class NotificationService:
    """Push notification gönderme servisi - Firebase Admin SDK kullanır"""

    @staticmethod
    def send_push_notification(user, title, body, data=None):
        """
        Kullanıcıya push notification gönder

        Args:
            user (User): Hedef kullanıcı
            title (str): Bildirim başlığı
            body (str): Bildirim içeriği
            data (dict, optional): Ek veri

        Returns:
            bool: Gönderim başarılı mı?
        """ # [cite: 579, 580]
        if not FIREBASE_AVAILABLE: # [cite: 580]
            logger.warning(f"Firebase SDK yok, bildirim gönderilemedi: {title}") # [cite: 580]
            return False # [cite: 580]

        # Kullanıcının aktif cihazlarını getir
        devices = FCMDevice.objects.filter(user=user, active=True) # [cite: 580]

        if not devices.exists(): # [cite: 580]
            logger.info(f"Kullanıcının aktif cihazı yok: {user.username}") # [cite: 580]
            return False # [cite: 581]

        # Notification objesi oluştur
        notification = messaging.Notification(
            title=title,
            body=body
        ) # [cite: 581]

        # Ek data
        data = data or {} # [cite: 581]
        data['title'] = title # [cite: 581]
        data['body'] = body # [cite: 581]

        success_count = 0 # [cite: 582]
        failed_tokens = [] # [cite: 582]

        for device in devices: # [cite: 582]
            try:
                # Message oluştur
                message = messaging.Message(
                    notification=notification, # [cite: 582]
                    data=data, # [cite: 583]
                    token=device.registration_id # [cite: 583]
                )

                # Gönder
                response = messaging.send(message) # [cite: 583]
                success_count += 1 # [cite: 584]

                logger.info(f"Push notification gönderildi: {user.username} - {title}") # [cite: 584]

            except messaging.UnregisteredError: # [cite: 584]
                # Token geçersiz, cihazı deaktif et
                logger.warning(f"Geçersiz FCM token, cihaz deaktif ediliyor: {device.name}") # [cite: 584]
                failed_tokens.append(device.registration_id) # [cite: 584]
                device.active = False # [cite: 585]
                device.save() # [cite: 585]

            except Exception as e: # [cite: 585]
                logger.error(f"FCM gönderim hatası: {e} - User: {user.username}") # [cite: 585]
                continue # [cite: 585]

        return success_count > 0 # [cite: 585]

    @staticmethod
    def send_bulk_notification(users, title, body, data=None):
        """
        Birden fazla kullanıcıya toplu bildirim gönder

        Args:
            users (QuerySet|list): Kullanıcı listesi
            title (str): Bildirim başlığı
            body (str): Bildirim içeriği
            data (dict, optional): Ek veri

        Returns:
            int: Başarılı gönderim sayısı
        """ # [cite: 586, 587]
        success_count = 0 # [cite: 587]

        for user in users: # [cite: 587]
            if NotificationService.send_push_notification(user, title, body, data): # [cite: 587]
                success_count += 1 # [cite: 587]

        logger.info(f"Toplu bildirim gönderildi: {success_count}/{len(users)} başarılı") # [cite: 587]

        return success_count # [cite: 588]

    @staticmethod
    def send_to_topic(topic, title, body, data=None):
        """
        Belirli bir topic'e abone olan tüm cihazlara bildirim gönder

        Args:
            topic (str): Firebase topic adı
            title (str): Bildirim başlığı
            body (str): Bildirim içeriği
            data (dict, optional): Ek veri

        Returns:
            bool: Gönderim başarılı mı?
        """ # [cite: 588, 589, 590]
        if not FIREBASE_AVAILABLE: # [cite: 590]
            logger.warning(f"Firebase SDK yok, topic bildirimi gönderilemedi: {topic}") # [cite: 590]
            return False # [cite: 590]

        try:
            notification = messaging.Notification(
                title=title,
                body=body
            ) # [cite: 590, 591]

            data = data or {} # [cite: 591]

            message = messaging.Message(
                notification=notification, # [cite: 591]
                data=data, # [cite: 591]
                topic=topic # [cite: 591]
            )

            response = messaging.send(message) # [cite: 592]
            logger.info(f"Topic bildirimi gönderildi: {topic} - {title}") # [cite: 592]

            return True # [cite: 592]

        except Exception as e: # [cite: 592]
            logger.error(f"Topic bildirim hatası: {e}") # [cite: 592]
            return False # [cite: 592]
