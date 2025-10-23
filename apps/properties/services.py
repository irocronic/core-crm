# apps/properties/services.py

from django.db.models import Q, Count, Sum, Avg
from django.db import transaction
from decimal import Decimal
import logging

from .models import Property, PaymentPlan

logger = logging.getLogger(__name__)


class PropertyService:
    """Gayrimenkul iş mantığı servisi"""
    
    @staticmethod
    def get_available_properties(filters=None):
        """Satılabilir mülkleri getir"""
        queryset = Property.objects.filter(status=Property.Status.SATILABILIR)
        
        if filters:
            if filters.get('property_type'):
                queryset = queryset.filter(property_type=filters['property_type'])
            
            if filters.get('min_price'):
                queryset = queryset.filter(cash_price__gte=filters['min_price'])
            
            if filters.get('max_price'):
                queryset = queryset.filter(cash_price__lte=filters['max_price'])
            
            if filters.get('room_count'):
                queryset = queryset.filter(room_count__icontains=filters['room_count'])
            
            if filters.get('project_name'):
                queryset = queryset.filter(project_name__icontains=filters['project_name'])
        
        return queryset
    
    # ==========================================
    # 🔥 TRANSACTION MANAGEMENT EKLENDI
    # ==========================================
    @staticmethod
    @transaction.atomic
    def reserve_property(property_instance):
        """
        Mülkü rezerve et
        
        Transaction ile wrap edildi: Hata olursa tüm işlemler geri alınır
        
        Args:
            property_instance (Property): Property instance
            
        Returns:
            tuple: (bool, str) - (Başarılı mı?, Mesaj)
        """
        try:
            # 🔒 Satır kilitleme (pessimistic locking)
            property_obj = Property.objects.select_for_update().get(
                id=property_instance.id
            )
            
            if not property_obj.is_available():
                logger.warning(f"Mülk satılabilir durumda değil: {property_obj}")
                return False, "Bu mülk satılabilir durumda değil"
            
            property_obj.reserve()
            logger.info(f"Mülk rezerve edildi: {property_obj}")
            
            return True, "Mülk başarıyla rezerve edildi"
            
        except Exception as e:
            logger.error(f"Mülk rezerve etme hatası: {e}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic
    def cancel_reservation(property_instance):
        """
        Rezervasyonu iptal et
        
        Transaction ile wrap edildi: Hata olursa tüm işlemler geri alınır
        
        Args:
            property_instance (Property): Property instance
            
        Returns:
            tuple: (bool, str) - (Başarılı mı?, Mesaj)
        """
        try:
            # 🔒 Satır kilitleme (pessimistic locking)
            property_obj = Property.objects.select_for_update().get(
                id=property_instance.id
            )
            
            if property_obj.status != Property.Status.REZERVE:
                logger.warning(f"Mülk rezerve durumunda değil: {property_obj}")
                return False, "Bu mülk rezerve durumunda değil"
            
            property_obj.cancel_reservation()
            logger.info(f"Rezervasyon iptal edildi: {property_obj}")
            
            return True, "Rezervasyon başarıyla iptal edildi"
            
        except Exception as e:
            logger.error(f"Rezervasyon iptal hatası: {e}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic
    def mark_as_sold(property_instance):
        """
        Mülkü satıldı olarak işaretle
        
        Transaction ile wrap edildi: Hata olursa tüm işlemler geri alınır
        
        Args:
            property_instance (Property): Property instance
            
        Returns:
            tuple: (bool, str) - (Başarılı mı?, Mesaj)
        """
        try:
            # 🔒 Satır kilitleme (pessimistic locking)
            property_obj = Property.objects.select_for_update().get(
                id=property_instance.id
            )
            
            if property_obj.status != Property.Status.REZERVE:
                logger.warning(f"Sadece rezerve mülkler satıldı olarak işaretlenebilir: {property_obj}")
                return False, "Sadece rezerve edilmiş mülkler satıldı olarak işaretlenebilir"
            
            property_obj.mark_as_sold()
            logger.info(f"Mülk satıldı olarak işaretlendi: {property_obj}")
            
            return True, "Mülk satıldı olarak işaretlendi"
            
        except Exception as e:
            logger.error(f"Mülk satış işaretleme hatası: {e}", exc_info=True)
            raise
    
    @staticmethod
    def calculate_payment_plan(property_instance, down_payment_percent, installment_count, interest_rate=0):
        """
        Ödeme planını hesapla
        
        Args:
            property_instance (Property): Property objesi
            down_payment_percent (float): Peşinat yüzdesi
            installment_count (int): Taksit sayısı
            interest_rate (float): Vade farkı oranı
        
        Returns:
            dict: Hesaplanan ödeme planı detayları
        """
        installment_price = float(property_instance.installment_price or property_instance.cash_price)
        down_payment_percent = float(down_payment_percent)
        interest_rate = float(interest_rate)
        
        # Peşinat tutarı
        down_payment_amount = installment_price * (down_payment_percent / 100)
        
        # Kalan tutar
        remaining_amount = installment_price - down_payment_amount
        
        # Vade farkı hesaplama
        if interest_rate > 0:
            total_with_interest = remaining_amount * (1 + interest_rate / 100)
            monthly_installment = total_with_interest / installment_count
        else:
            total_with_interest = remaining_amount
            monthly_installment = remaining_amount / installment_count
        
        return {
            'installment_price': round(installment_price, 2),
            'down_payment_percent': down_payment_percent,
            'down_payment_amount': round(down_payment_amount, 2),
            'remaining_amount': round(remaining_amount, 2),
            'interest_rate': interest_rate,
            'total_with_interest': round(total_with_interest, 2),
            'installment_count': installment_count,
            'monthly_installment': round(monthly_installment, 2),
        }
    
    @staticmethod
    def get_property_statistics():
        """Genel mülk istatistikleri"""
        total = Property.objects.count()
        
        if total == 0:
            return {
                'total': 0,
                'available': 0,
                'reserved': 0,
                'sold': 0,
                'available_percentage': 0,
                'sold_percentage': 0,
            }
        
        available = Property.objects.filter(status=Property.Status.SATILABILIR).count()
        reserved = Property.objects.filter(status=Property.Status.REZERVE).count()
        sold = Property.objects.filter(status=Property.Status.SATILDI).count()
        
        return {
            'total': total,
            'available': available,
            'reserved': reserved,
            'sold': sold,
            'available_percentage': round((available / total) * 100, 2),
            'sold_percentage': round((sold / total) * 100, 2),
        }
    
    @staticmethod
    def get_project_statistics(project_name):
        """
        Belirli bir proje için istatistikler
        
        Args:
            project_name (str): Proje adı
            
        Returns:
            dict: Proje istatistikleri
        """
        properties = Property.objects.filter(project_name=project_name)
        
        return {
            'project_name': project_name,
            'total_properties': properties.count(),
            'available': properties.filter(status=Property.Status.SATILABILIR).count(),
            'reserved': properties.filter(status=Property.Status.REZERVE).count(),
            'sold': properties.filter(status=Property.Status.SATILDI).count(),
            'avg_price': properties.aggregate(Avg('cash_price'))['cash_price__avg'],
            'total_value': properties.aggregate(Sum('cash_price'))['cash_price__sum'],
        }
