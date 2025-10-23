# apps/sales/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from .models import Reservation
from apps.properties.models import Property

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Reservation)
def sync_property_status_on_reservation_change(sender, instance, created, **kwargs):
    """
    Bir Rezervasyon kaydedildiğinde veya güncellendiğinde,
    ilişkili Gayrimenkul'ün durumunu otomatik olarak senkronize eder.

    Bu sinyal, veri tutarlılığını sağlamak için kritik öneme sahiptir.
    - Yeni bir rezervasyon 'AKTIF' ise, mülkü 'REZERVE' yapar.
    - Bir rezervasyon 'SATISA_DONUSTU' olarak güncellenirse, mülkü 'SATILDI' yapar.
    - Bir rezervasyon 'IPTAL_EDILDI' olarak güncellenirse, mülkü tekrar 'SATILABILIR' yapar.
    """
    try:
        # Transaction içinde olduğumuzdan emin olmak için mülkü kilitleyerek alıyoruz.
        # Bu, race condition (yarış durumu) riskini azaltır.
        property_obj = Property.objects.select_for_update().get(id=instance.property.id)
        reservation_status = instance.status

        # Durumlar arasında senkronizasyon mantığı
        if reservation_status == Reservation.Status.AKTIF and property_obj.status != Property.Status.REZERVE:
            property_obj.status = Property.Status.REZERVE
            property_obj.save(update_fields=['status'])
            logger.info(f"Signal: Rezervasyon {instance.id} aktif olduğu için Mülk {property_obj.id} REZERVE edildi.")

        elif reservation_status == Reservation.Status.SATISA_DONUSTU and property_obj.status != Property.Status.SATILDI:
            property_obj.status = Property.Status.SATILDI
            property_obj.save(update_fields=['status'])
            logger.info(f"Signal: Rezervasyon {instance.id} satışa dönüştüğü için Mülk {property_obj.id} SATILDI olarak işaretlendi.")

        elif reservation_status == Reservation.Status.IPTAL_EDILDI and property_obj.status != Property.Status.SATILABILIR:
            # Sadece 'REZERVE' durumundaki bir mülk tekrar 'SATILABILIR' hale gelmelidir.
            # 'SATILDI' durumundaki bir mülk, rezervasyon iptaliyle tekrar satılabilir olmamalıdır.
            if property_obj.status == Property.Status.REZERVE:
                property_obj.status = Property.Status.SATILABILIR
                property_obj.save(update_fields=['status'])
                logger.info(f"Signal: Rezervasyon {instance.id} iptal edildiği için Mülk {property_obj.id} SATILABILIR yapıldı.")
            else:
                logger.warning(f"Signal: İptal edilen rezervasyon {instance.id} için mülk {property_obj.id} durumu ({property_obj.status}) değiştirilmedi.")

    except Property.DoesNotExist:
        logger.warning(f"Signal: Rezervasyon {instance.id} için ilişkili mülk bulunamadı.")
    except Exception as e:
        # Herhangi bir hata durumunda loglama yap, transaction'ın geri alınmasını sağla.
        logger.error(f"Signal Hatası (sync_property_status): Rezervasyon ID {instance.id} işlenirken hata oluştu: {e}", exc_info=True)
        # Hatanın tekrar yükseltilmesi, işlemin geri alınmasını sağlar.
        raise
