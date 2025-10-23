# apps/sales/services.py

from django.db.models import Sum, Count, Avg, Q, F, Case, When, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta, datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics # YENİ EKLENDİ
from reportlab.pdfbase.ttfonts import TTFont # YENİ EKLENDİ
from django.core.files.base import ContentFile
import logging
import os # YENİ EKLENDİ

from .models import Reservation, Payment, Contract, SalesReport
# Gerekli importlar
from apps.users.models import User
from apps.crm.models import Activity, Customer

logger = logging.getLogger(__name__)


class ReservationService:
    """Rezervasyon iş mantığı servisi"""
    
    # ==========================================
    # 🔥 TRANSACTION MANAGEMENT EKLENDI
    # ==========================================
    @staticmethod
    @transaction.atomic  # 🔥 Transaction decorator
    def create_reservation_with_payments(reservation_data, created_by):
        """
        Rezervasyon oluştur ve ödeme planını otomatik oluştur
        
        Transaction ile wrap edildi: Hata olursa tüm işlemler geri alınır
        
        Args:
            reservation_data (dict): Rezervasyon bilgileri
            created_by (User): Rezervasyonu oluşturan kullanıcı
            
        Returns:
            tuple: (Reservation|None, str) - (Rezervasyon instance veya None, mesaj)
        """
        from apps.properties.models import Property
        
        try:
            property_instance = reservation_data['property']
            
            # Mülk müsait mi kontrol et
            if not property_instance.is_available():
                logger.warning(f"Mülk satılabilir durumda değil: {property_instance}")
                return None, "Bu mülk satılabilir durumda değil"
            
            # Rezervasyon oluştur
            reservation = Reservation.objects.create(
                **reservation_data,
                created_by=created_by
            )
            
            logger.info(f"Rezervasyon oluşturuldu: {reservation.id} - Müşteri: {reservation.customer.full_name}")
            
            # Ödeme planı vadeli ise taksitleri oluştur
            payment_plan = reservation.payment_plan_selected
            
            if payment_plan.plan_type == 'VADELI':
                ReservationService._create_installment_schedule(
                    reservation,
                    payment_plan,
                    created_by
                )
                logger.info(f"Ödeme planı oluşturuldu: {reservation.id} - {payment_plan.name}")
            
            return reservation, "Rezervasyon başarıyla oluşturuldu"
            
        except Exception as e:
            logger.error(f"Rezervasyon oluşturma hatası: {e}", exc_info=True)
            # Transaction otomatik olarak rollback olacak
            return None, f"Rezervasyon oluşturulamadı: {str(e)}"
    
    @staticmethod
    def _create_installment_schedule(reservation, payment_plan, created_by):
        """
        Taksit ödeme planını oluştur
        
        Bu fonksiyon zaten create_reservation_with_payments içinde
        transaction context'inde çalışır
        """
        details = payment_plan.details
        
        # Peşinat kaydı
        down_payment_amount = Decimal(str(details.get('down_payment_amount', 0)))
        
        if down_payment_amount > 0:
            Payment.objects.create(
                reservation=reservation,
                payment_type=Payment.PaymentType.PESINAT,
                amount=down_payment_amount,
                status=Payment.Status.ALINDI,
                due_date=reservation.reservation_date.date(),
                payment_date=reservation.reservation_date.date(),
                payment_method=reservation.deposit_payment_method,
                receipt_number=reservation.deposit_receipt_number,
                recorded_by=created_by
            )
            logger.info(f"Peşinat ödemesi kaydedildi: {down_payment_amount} TL")
        
        # Taksit planı
        installment_count = details.get('installment_count', 0)
        monthly_installment = Decimal(str(details.get('monthly_installment', 0)))
        
        first_installment_date = reservation.reservation_date.date() + timedelta(days=30)
        
        for i in range(1, installment_count + 1):
            due_date = first_installment_date + timedelta(days=30 * (i - 1))
            
            Payment.objects.create(
                reservation=reservation,
                payment_type=Payment.PaymentType.TAKSIT,
                amount=monthly_installment,
                status=Payment.Status.BEKLENIYOR,
                due_date=due_date,
                installment_number=i,
                recorded_by=created_by
            )
        
        logger.info(f"{installment_count} adet taksit kaydedildi")
    
    @staticmethod
    def get_reservation_summary(reservation):
        """Rezervasyon özet bilgileri"""
        payments = reservation.payments.all()
        
        total_paid = payments.filter(status=Payment.Status.ALINDI).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        total_pending = payments.filter(status=Payment.Status.BEKLENIYOR).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        overdue_payments = payments.filter(
            status=Payment.Status.BEKLENIYOR,
            due_date__lt=timezone.now().date()
        )
        
        return {
            'reservation_id': reservation.id,
            'customer_name': reservation.customer.full_name,
            'property': str(reservation.property),
            'total_amount': reservation.payment_plan_selected.details.get('installment_price', 0),
            'deposit_amount': float(reservation.deposit_amount),
            'total_paid': float(total_paid),
            'total_pending': float(total_pending),
            'remaining_amount': float(reservation.get_remaining_amount()),
            'payment_count': payments.count(),
            'paid_payment_count': payments.filter(status=Payment.Status.ALINDI).count(),
            'overdue_payment_count': overdue_payments.count(),
            'status': reservation.status,
        }
    
    @staticmethod
    def get_sales_rep_performance(sales_rep, start_date=None, end_date=None):
        """Satış temsilcisinin performans istatistikleri"""
        queryset = Reservation.objects.filter(sales_rep=sales_rep)
        
        if start_date:
            queryset = queryset.filter(reservation_date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(reservation_date__lte=end_date)
        
        total_reservations = queryset.count()
        active_reservations = queryset.filter(status=Reservation.Status.AKTIF).count()
        converted_sales = queryset.filter(status=Reservation.Status.SATISA_DONUSTU).count()
        
        total_revenue = queryset.filter(
            status=Reservation.Status.SATISA_DONUSTU
        ).aggregate(
            total=Sum('deposit_amount')
        )['total'] or Decimal('0')
        
        conversion_rate = 0
        if total_reservations > 0:
            conversion_rate = (converted_sales / total_reservations) * 100
        
        return {
            'sales_rep': sales_rep.get_full_name(),
            'total_reservations': total_reservations,
            'active_reservations': active_reservations,
            'converted_sales': converted_sales,
            'cancelled_reservations': queryset.filter(status=Reservation.Status.IPTAL_EDILDI).count(),
            'conversion_rate': round(conversion_rate, 2),
            'total_revenue': float(total_revenue),
        }


class PaymentService:
    """Ödeme iş mantığı servisi"""
    
    @staticmethod
    def get_overdue_payments(sales_rep=None):
        """Gecikmiş ödemeleri getir"""
        today = timezone.now().date()
        
        queryset = Payment.objects.filter(
            status=Payment.Status.BEKLENIYOR,
            due_date__lt=today
        ).select_related('reservation', 'reservation__customer')
        
        if sales_rep:
            queryset = queryset.filter(reservation__sales_rep=sales_rep)
        
        return queryset
    
    @staticmethod
    def get_upcoming_payments(sales_rep=None, days=7):
        """Yaklaşan ödemeler (varsayılan 7 gün)"""
        today = timezone.now().date()
        future_date = today + timedelta(days=days)
        
        queryset = Payment.objects.filter(
            status=Payment.Status.BEKLENIYOR,
            due_date__range=(today, future_date)
        ).select_related('reservation', 'reservation__customer')
        
        if sales_rep:
            queryset = queryset.filter(reservation__sales_rep=sales_rep)
        
        return queryset.order_by('due_date')
    
    @staticmethod
    def calculate_collection_rate(sales_rep=None, start_date=None, end_date=None):
        """Tahsilat oranını hesapla"""
        queryset = Payment.objects.all()
        
        if sales_rep:
            queryset = queryset.filter(reservation__sales_rep=sales_rep)
        
        if start_date:
            queryset = queryset.filter(due_date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(due_date__lte=end_date)
        
        total_expected = queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_collected = queryset.filter(status=Payment.Status.ALINDI).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        collection_rate = 0
        if total_expected > 0:
            collection_rate = (total_collected / total_expected) * 100
        
        return {
            'total_expected': float(total_expected),
            'total_collected': float(total_collected),
            'collection_rate': round(collection_rate, 2),
            'total_pending': float(total_expected - total_collected),
        }
    
    # ==========================================
    # 🔥 TRANSACTION MANAGEMENT EKLENDI
    # ==========================================
    @staticmethod
    @transaction.atomic  # 🔥 Transaction decorator
    def auto_update_overdue_payments():
        """
        Gecikmiş ödemeleri otomatik olarak işaretle (Celery task)
        
        Returns:
            int: Güncellenen ödeme sayısı
        """
        today = timezone.now().date()
        
        try:
            overdue_payments = Payment.objects.filter(
                status=Payment.Status.BEKLENIYOR,
                due_date__lt=today
            )
            
            updated_count = overdue_payments.update(status=Payment.Status.GECIKTI)
            
            logger.info(f"Gecikmiş ödemeler güncellendi: {updated_count} adet")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Gecikmiş ödeme güncelleme hatası: {e}", exc_info=True)
            raise


class ContractService:
    """Sözleşme iş mantığı servisi"""
    
    @staticmethod
    def generate_contract_number(contract_type):
        """Benzersiz sözleşme numarası oluştur"""
        from django.utils.crypto import get_random_string
        
        year = timezone.now().year
        
        if contract_type == Contract.ContractType.REZERVASYON:
            prefix = "REZ"
        elif contract_type == Contract.ContractType.SATIS:
            prefix = "SAT"
        else:
            prefix = "ON"
        
        # Son sözleşme numarasını al
        last_contract = Contract.objects.filter(
            contract_number__startswith=f"{prefix}-{year}"
        ).order_by('-id').first()
        
        if last_contract:
            # Son numarayı al ve 1 artır
            last_number = int(last_contract.contract_number.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f"{prefix}-{year}-{new_number:05d}"
    
    @staticmethod
    def generate_contract_pdf(contract):
        """
        Sözleşme PDF oluştur
        ReportLab kullanarak basit bir sözleşme PDF'i oluşturur
        
        Args:
            contract (Contract): Sözleşme instance
            
        Returns:
            ContentFile|None: PDF dosyası veya None
        """
        try:
            # --- YENİ EKLENDİ: Türkçe Karakter Desteği İçin Font Tanımlaması ---
            # Projenizin ana dizininde static/fonts/DejaVuSans.ttf dosyasının bulunduğundan emin olun.
            font_path = os.path.join('static', 'fonts', 'DejaVuSans.ttf')
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
            # --- YENİ EKLENDİ SONU ---

            buffer = io.BytesIO()
            
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            # --- GÜNCELLEŞTİRİLDİ: Başlık ve Stili ---
            title_style = styles['Title']
            title_style.fontName = 'DejaVuSans' # Fontu ayarla
            title = Paragraph(f"SATIŞ SÖZLEŞMESİ", title_style)
            elements.append(title)
            elements.append(Spacer(1, 20))
            
            # Sözleşme Bilgileri
            data = [
                ['Sözleşme No:', contract.contract_number],
                ['Sözleşme Tipi:', contract.get_contract_type_display()],
                ['Sözleşme Tarihi:', contract.contract_date.strftime('%d.%m.%Y')],
                ['', ''],
                ['MÜŞTERİ BİLGİLERİ', ''],
                ['Ad Soyad:', contract.reservation.customer.full_name],
                ['Telefon:', contract.reservation.customer.phone_number],
                ['E-posta:', contract.reservation.customer.email or '-'],
                ['', ''],
                ['GAYRİMENKUL BİLGİLERİ', ''],
                ['Proje:', contract.reservation.property.project.name],
                ['Blok:', contract.reservation.property.block],
                ['Kat:', str(contract.reservation.property.floor)],
                ['Daire No:', contract.reservation.property.unit_number],
                ['Tip:', contract.reservation.property.get_property_type_display()],
                ['Oda Sayısı:', contract.reservation.property.room_count],
                ['Net Alan:', f"{contract.reservation.property.net_area_m2} m²"],
                ['', ''],
                ['FİYAT BİLGİLERİ', ''],
                ['Ödeme Planı:', contract.reservation.payment_plan_selected.name],
            ]
            
            # Fiyat detayları
            plan_details = contract.reservation.payment_plan_selected.details
            
            if contract.reservation.payment_plan_selected.plan_type == 'PESIN':
                data.append(['Peşin Fiyat:', f"{plan_details.get('cash_price', 0):,.2f} TL"])
            else:
                data.append(['Vadeli Fiyat:', f"{plan_details.get('installment_price', 0):,.2f} TL"])
                data.append(['Peşinat:', f"{plan_details.get('down_payment_amount', 0):,.2f} TL"])
                data.append(['Taksit Sayısı:', f"{plan_details.get('installment_count', 0)} Ay"])
                data.append(['Aylık Taksit:', f"{plan_details.get('monthly_installment', 0):,.2f} TL"])
            
            data.append(['', ''])
            data.append(['Kaparo Bedeli:', f"{contract.reservation.deposit_amount:,.2f} TL"])
            data.append(['Kaparo Ödeme Yöntemi:', contract.reservation.get_deposit_payment_method_display()])
            
            # Tablo oluştur
            table = Table(data, colWidths=[200, 300])
            # --- GÜNCELLEŞTİRİLDİ: Tablo Stili Fontu ---
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'), # Helvetica -> DejaVuSans
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 30))
            
            # İmza Alanları
            signature_data = [
                ['', '', ''],
                ['_________________', '_________________', '_________________'],
                ['Müşteri İmzası', 'Satış Temsilcisi', 'Şirket Yetkilisi'],
            ]
            
            signature_table = Table(signature_data, colWidths=[150, 150, 150])
            # --- GÜNCELLEŞTİRİLDİ: İmza Tablosu Stili Fontu ---
            signature_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'), # Helvetica -> DejaVuSans
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            
            elements.append(signature_table)
            
            # PDF oluştur
            doc.build(elements)
            
            # Dosyayı kaydet
            buffer.seek(0)
            filename = f"sozlesme_{contract.contract_number}.pdf"
            
            logger.info(f"Sözleşme PDF oluşturuldu: {filename}")
            
            return ContentFile(buffer.read(), name=filename)
            
        except Exception as e:
            logger.error(f"Sözleşme PDF oluşturma hatası: {e}", exc_info=True)
        
        return None
    
    # ==========================================
    # 🔥 TRANSACTION MANAGEMENT EKLENDI
    # ==========================================
    @staticmethod
    @transaction.atomic  # 🔥 Transaction decorator
    def create_contract_for_reservation(reservation, contract_type, created_by):
        """
        Rezervasyon için otomatik sözleşme oluştur
        
        Args:
            reservation (Reservation): Rezervasyon instance
            contract_type (str): Sözleşme tipi
            created_by (User): Sözleşmeyi oluşturan kullanıcı
            
        Returns:
            Contract: Oluşturulan sözleşme instance
        """
        try:
            contract_number = ContractService.generate_contract_number(contract_type)
            
            contract = Contract.objects.create(
                reservation=reservation,
                contract_type=contract_type,
                contract_number=contract_number,
                status=Contract.Status.TASLAK,
                created_by=created_by
            )
            
            logger.info(f"Sözleşme oluşturuldu: {contract.contract_number}")
            
            # PDF oluştur
            pdf_file = ContractService.generate_contract_pdf(contract)
            if pdf_file:
                contract.contract_file = pdf_file
                contract.save(update_fields=['contract_file'])
                logger.info(f"Sözleşme PDF'i kaydedildi: {contract.contract_number}")
            else:
                logger.warning(f"Sözleşme PDF oluşturulamadı: {contract.contract_number}")
            
            return contract
            
        except Exception as e:
            logger.error(f"Sözleşme oluşturma hatası: {e}", exc_info=True)
            raise


class ReportService:
    """Rapor oluşturma servisi"""

    @staticmethod
    def _generate_sales_summary(start_date, end_date):
        """Mevcut Genel Satış Özeti raporunu oluşturur."""
        reservations = Reservation.objects.filter(
            reservation_date__date__range=(start_date, end_date)
        )
        payments = Payment.objects.filter(
            payment_date__range=(start_date, end_date),
            status=Payment.Status.ALINDI
        )
        
        statistics = {
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'generated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
            'reservations': {
                'total': reservations.count(),
                'active': reservations.filter(status=Reservation.Status.AKTIF).count(),
                'converted': reservations.filter(status=Reservation.Status.SATISA_DONUSTU).count(),
                'cancelled': reservations.filter(status=Reservation.Status.IPTAL_EDILDI).count(),
                'total_deposit': float(reservations.aggregate(Sum('deposit_amount'))['deposit_amount__sum'] or 0),
            },
            'payments': {
                'total_collected': float(payments.aggregate(Sum('amount'))['amount__sum'] or 0),
                'payment_count': payments.count(),
                'by_method': {},
            },
        }
        for method in Payment.PaymentMethod:
            amount = payments.filter(payment_method=method.value).aggregate(
                total=Sum('amount')
            )['total'] or 0
            if amount > 0:
                statistics['payments']['by_method'][method.label] = float(amount)
        
        return statistics

    @staticmethod
    def _generate_rep_performance_report(start_date, end_date):
        """Temsilci Bazında Satış Performans Raporu oluşturur."""
        sales_reps = User.objects.filter(role=User.Role.SATIS_TEMSILCISI, is_active_employee=True)
        
        report_data = []
        total_revenue = Decimal(0)
        total_sales_count = 0
        total_activity_count = 0

        for rep in sales_reps:
            # Temsilcinin aktiviteleri (görüşmeleri)
            activities = Activity.objects.filter(
                created_by=rep,
                created_at__date__range=(start_date, end_date)
            )
            activity_count = activities.count()

            # Temsilcinin satışları (satışa dönüşmüş rezervasyonlar)
            sales = Reservation.objects.filter(
                sales_rep=rep,
                status=Reservation.Status.SATISA_DONUSTU,
                # Satışa dönüşme tarihi `updated_at` üzerinden takip edilebilir
                updated_at__date__range=(start_date, end_date)
            ).select_related('property', 'payment_plan_selected')
            
            sales_count = sales.count()
            
            # Ciro hesaplama (Peşin/Vadeli fiyata göre)
            revenue = sales.aggregate(
                total_revenue=Coalesce(Sum(
                    Case(
                        When(payment_plan_selected__plan_type='PESIN', then=F('property__cash_price')),
                        When(payment_plan_selected__plan_type='VADELI', then=F('property__installment_price')),
                        default=F('property__cash_price'),
                        output_field=DecimalField()
                    )
                ), Decimal(0))
            )['total_revenue']

            # Performans (Görüşmeyi satışa çevirme) oranı
            conversion_rate = (sales_count / activity_count * 100) if activity_count > 0 else 0

            report_data.append({
                'rep_id': rep.id,
                'rep_name': rep.get_full_name(),
                'activity_count': activity_count,
                'sales_count': sales_count,
                'total_revenue': float(revenue),
                'conversion_rate': round(conversion_rate, 2),
            })

            total_revenue += revenue
            total_sales_count += sales_count
            total_activity_count += activity_count

        return {
            "rep_performance": report_data,
            "performance_summary": {
                "total_sales_reps": sales_reps.count(),
                "total_activity_count": total_activity_count,
                "total_sales_count": total_sales_count,
                "total_revenue": float(total_revenue),
            }
        }

    @staticmethod
    def _generate_customer_source_report(start_date, end_date):
        """Satışa Dönen Müşterilerin Kaynak Raporunu oluşturur."""
        # Belirtilen tarih aralığında satışa dönüşmüş rezervasyonlar
        sales = Reservation.objects.filter(
            status=Reservation.Status.SATISA_DONUSTU,
            updated_at__date__range=(start_date, end_date)
        ).select_related('customer')

        # Müşteri kaynaklarına göre gruplayıp sayım yap
        source_counts = sales.values('customer__source').annotate(count=Count('id')).order_by('-count')

        # `Customer` modelindeki `Source` enum'ının etiketlerini alalım
        source_labels = dict(Customer.Source.choices)
        
        report_data = []
        for item in source_counts:
            source_key = item['customer__source']
            report_data.append({
                'source': source_labels.get(source_key, source_key), # Etiketi al, yoksa anahtarı kullan
                'count': item['count'],
            })
            
        total_customers = sales.count()
        most_common = report_data[0] if report_data else None

        return {
            "source_data": report_data,
            "source_summary": {
                "total_customers": total_customers,
                "most_common_source": most_common['source'] if most_common else "N/A",
                "most_common_source_count": most_common['count'] if most_common else 0,
            }
        }


    @staticmethod
    @transaction.atomic  # 🔥 Transaction decorator
    def generate_sales_report(report_type, start_date, end_date, generated_by):
        """
        Satış raporu oluştur (GÜNCELLENDİ)
        
        Args:
            report_type (str): Rapor tipi
            start_date (date|str): Başlangıç tarihi
            end_date (date|str): Bitiş tarihi
            generated_by (User): Raporu oluşturan kullanıcı
            
        Returns:
            SalesReport: Oluşturulan rapor instance
        """
        try:
            # Tarih dönüşümü
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            logger.info(f"Satış raporu oluşturuluyor: {report_type} - {start_date} / {end_date}")
            
            statistics = {}
            # Rapor türüne göre ilgili fonksiyonu çağır
            if report_type in [SalesReport.ReportType.GUNLUK, SalesReport.ReportType.HAFTALIK, SalesReport.ReportType.AYLIK, SalesReport.ReportType.YILLIK, SalesReport.ReportType.GENEL_Ozet]:
                statistics = ReportService._generate_sales_summary(start_date, end_date)
            elif report_type == SalesReport.ReportType.TEMSILCI_PERFORMANS:
                statistics = ReportService._generate_rep_performance_report(start_date, end_date)
            elif report_type == SalesReport.ReportType.MUSTERI_KAYNAK:
                statistics = ReportService._generate_customer_source_report(start_date, end_date)
            else:
                raise ValueError(f"Geçersiz rapor türü: {report_type}")

            # Raporu kaydet
            report = SalesReport.objects.create(
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                statistics=statistics,
                generated_by=generated_by
            )
            
            logger.info(f"Satış raporu oluşturuldu: {report.id}")
            
            return report
            
        except Exception as e:
            logger.error(f"Satış raporu oluşturma hatası: {e}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic  # 🔥 Transaction decorator
    def generate_daily_report():
        """
        Günlük rapor oluştur (Celery task için)
        
        Returns:
            SalesReport: Oluşturulan rapor instance
        """
        today = timezone.now().date()
        
        from apps.users.models import User
        admin_user = User.objects.filter(role=User.Role.ADMIN).first()
        
        if not admin_user:
            logger.error("Admin kullanıcı bulunamadı, günlük rapor oluşturulamadı")
            return None
        
        # Günlük rapor artık genel özeti oluşturacak
        return ReportService.generate_sales_report(
            report_type=SalesReport.ReportType.GUNLUK,
            start_date=today,
            end_date=today,
            generated_by=admin_user
        )


class NotificationService:
    """Satış bildirimleri servisi"""
    
    @staticmethod
    def send_payment_reminder(payment):
        """
        Ödeme hatırlatması gönder
        
        Args:
            payment (Payment): Payment instance
            
        Returns:
            bool: Gönderim başarılı mı?
        """
        from apps.users.services import NotificationService as BaseNotificationService
        
        title = "Ödeme Hatırlatması"
        body = f"{payment.reservation.customer.full_name} - {payment.amount} TL ödeme vadesi yaklaşıyor."
        data = {
            'type': 'payment_reminder',
            'payment_id': str(payment.id),
            'reservation_id': str(payment.reservation.id),
            'amount': str(payment.amount),
            'due_date': payment.due_date.isoformat()
        }
        
        success = BaseNotificationService.send_push_notification(
            user=payment.reservation.sales_rep,
            title=title,
            body=body,
            data=data
        )
        
        if success:
            logger.info(f"Ödeme hatırlatması gönderildi: Payment ID {payment.id}")
        else:
            logger.warning(f"Ödeme hatırlatması gönderilemedi: Payment ID {payment.id}")
        
        return success
    
    @staticmethod
    def send_overdue_payment_notification(payment):
        """
        Gecikmiş ödeme bildirimi
        
        Args:
            payment (Payment): Payment instance
            
        Returns:
            bool: Gönderim başarılı mı?
        """
        from apps.users.services import NotificationService as BaseNotificationService
        
        days_overdue = (timezone.now().date() - payment.due_date).days
        
        title = "Gecikmiş Ödeme"
        body = f"{payment.reservation.customer.full_name} - {payment.amount} TL ödeme {days_overdue} gün gecikti!"
        data = {
            'type': 'overdue_payment',
            'payment_id': str(payment.id),
            'reservation_id': str(payment.reservation.id),
            'amount': str(payment.amount),
            'due_date': payment.due_date.isoformat(),
            'days_overdue': days_overdue
        }
        
        success = BaseNotificationService.send_push_notification(
            user=payment.reservation.sales_rep,
            title=title,
            body=body,
            data=data
        )
        
        if success:
            logger.info(f"Gecikmiş ödeme bildirimi gönderildi: Payment ID {payment.id}")
        else:
            logger.warning(f"Gecikmiş ödeme bildirimi gönderilemedi: Payment ID {payment.id}")
        
        return success
