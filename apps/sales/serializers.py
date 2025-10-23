# apps/sales/serializers.py

from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from .models import Reservation, Payment, Contract, SalesReport
from apps.properties.serializers import PropertySerializer, PaymentPlanSerializer
from apps.crm.serializers import CustomerSerializer
# YENİ IMPORT: Ödeme planı ve Mülk modellerini import ediyoruz.
from apps.properties.models import PaymentPlan, Property
# **** GÜNCELLEME BAŞLANGICI ****
from apps.users.models import User # User modelini import ediyoruz
# **** GÜNCELLEME SONU ****
import logging

logger = logging.getLogger(__name__)


class PaymentSerializer(serializers.ModelSerializer):
    """Ödeme serializeri"""
    
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'reservation', 'payment_type', 'payment_type_display',
            'amount', 'payment_method', 'payment_method_display',
            'status', 'status_display', 'due_date', 'payment_date',
            'receipt_number', 'installment_number', 'notes',
            'recorded_by', 'recorded_by_name', 'is_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'recorded_by', 'created_at', 'updated_at']


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Ödeme kayıt serializeri"""
    
    class Meta:
        model = Payment
        fields = [
            'reservation', 'payment_type', 'amount', 'payment_method',
            'status', 'due_date', 'payment_date', 'receipt_number',
            'installment_number', 'notes'
        ]
    
    def validate(self, attrs):
        # Ödeme alındı ise ödeme tarihi ve yöntemi zorunlu
        if attrs.get('status') == Payment.Status.ALINDI:
            if not attrs.get('payment_date'):
                raise serializers.ValidationError({
                    'payment_date': 'Ödeme alındı ise ödeme tarihi gereklidir'
                })
            if not attrs.get('payment_method'):
                raise serializers.ValidationError({
                    'payment_method': 'Ödeme alındı ise ödeme yöntemi gereklidir'
                })
        
        return attrs


class ContractSerializer(serializers.ModelSerializer):
    """Sözleşme serializeri"""
    
    contract_type_display = serializers.CharField(source='get_contract_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Contract
        fields = [
            'id', 'reservation', 'contract_type', 'contract_type_display',
            'contract_number', 'contract_file', 'status', 'status_display',
            'contract_date', 'signed_date', 'notes',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'contract_number', 'created_by', 'created_at', 'updated_at']


class ReservationSerializer(serializers.ModelSerializer):
    """Rezervasyon liste serializeri"""
    
    property_info = PropertySerializer(source='property', read_only=True)
    customer_info = CustomerSerializer(source='customer', read_only=True)
    sales_rep_name = serializers.CharField(source='sales_rep.get_full_name', read_only=True)
    payment_plan_info = PaymentPlanSerializer(source='payment_plan_selected', read_only=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    deposit_payment_method_display = serializers.CharField(
        source='get_deposit_payment_method_display',
        read_only=True
    )
    
    remaining_amount = serializers.DecimalField(
        source='get_remaining_amount',
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    
    is_expired = serializers.BooleanField(read_only=True)
    
    payments_count = serializers.IntegerField(source='payments.count', read_only=True)
    contracts_count = serializers.IntegerField(source='contracts.count', read_only=True)
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'property', 'property_info', 'customer', 'customer_info',
            'sales_rep', 'sales_rep_name', 'payment_plan_selected',
            'payment_plan_info', 'deposit_amount', 'deposit_payment_method',
            'deposit_payment_method_display', 'deposit_receipt_number',
            'status', 'status_display', 'reservation_date', 'expiry_date',
            'notes', 'remaining_amount', 'is_expired',
            'payments_count', 'contracts_count',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class ReservationDetailSerializer(serializers.ModelSerializer):
    """Rezervasyon detay serializeri"""
    
    property_info = PropertySerializer(source='property', read_only=True)
    customer_info = CustomerSerializer(source='customer', read_only=True)
    sales_rep_name = serializers.CharField(source='sales_rep.get_full_name', read_only=True)
    payment_plan_info = PaymentPlanSerializer(source='payment_plan_selected', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    deposit_payment_method_display = serializers.CharField(
        source='get_deposit_payment_method_display',
        read_only=True
    )
    
    remaining_amount = serializers.DecimalField(
        source='get_remaining_amount',
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    
    is_expired = serializers.BooleanField(read_only=True)
    
    # İlişkili veriler
    payments = PaymentSerializer(many=True, read_only=True)
    contracts = ContractSerializer(many=True, read_only=True)
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'property', 'property_info', 'customer', 'customer_info',
            'sales_rep', 'sales_rep_name', 'payment_plan_selected',
            'payment_plan_info', 'deposit_amount', 'deposit_payment_method',
            'deposit_payment_method_display', 'deposit_receipt_number',
            'status', 'status_display', 'reservation_date', 'expiry_date',
            'notes', 'remaining_amount', 'is_expired',
            'payments', 'contracts',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class ReservationCreateSerializer(serializers.ModelSerializer):
    """Rezervasyon oluşturma serializeri"""

    # **** GÜNCELLEME BAŞLANGICI ****
    # sales_rep alanını opsiyonel hale getiriyoruz.
    # Bu, backend'in bu alan boş geldiğinde varsayılan kullanıcıyı atamasını sağlar.
    sales_rep = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role__in=[User.Role.SATIS_TEMSILCISI, User.Role.SATIS_MUDUR, User.Role.ADMIN]),
        required=False, # Bu alan zorunlu değil
        allow_null=True # Null değerlere izin ver
    )
    payment_plan_selected = serializers.IntegerField(write_only=True)
    # **** GÜNCELLEME SONU ****
    
    class Meta:
        model = Reservation
        fields = [
            'property', 'customer', 'sales_rep', 'payment_plan_selected',
            'deposit_amount', 'deposit_payment_method', 'deposit_receipt_number',
            'expiry_date', 'notes'
        ]
    
    def validate_property(self, value):
        """Mülk satılabilir durumda olmalı"""
        if not value.is_available():
            raise serializers.ValidationError('Bu mülk satılabilir durumda değil')
        return value
    
    def validate(self, attrs):
        property_instance = attrs['property']
        payment_plan_id = attrs['payment_plan_selected']

        # Gerçek bir ödeme planı ID'si geldiyse, mülke ait olup olmadığını kontrol et.
        if payment_plan_id > 0:
            try:
                payment_plan = PaymentPlan.objects.get(id=payment_plan_id)
                if payment_plan.property != property_instance:
                    raise serializers.ValidationError({
                        'payment_plan_selected': 'Seçilen ödeme planı bu mülke ait değil'
                    })
            except PaymentPlan.DoesNotExist:
                 raise serializers.ValidationError({
                        'payment_plan_selected': 'Seçilen ödeme planı bulunamadı'
                    })

        # Peşin ödeme (-1) seçildiyse, kaparo tutarının mülkün peşin fiyatına eşit olup olmadığını kontrol et.
        if payment_plan_id == -1:
            expected_amount = property_instance.cash_price
            if attrs['deposit_amount'] != expected_amount:
                raise serializers.ValidationError({
                    'deposit_amount': f'Peşin ödemede kaparo tutarı {expected_amount} TL olmalıdır'
                })
        
        # Son geçerlilik tarihi geçmişte olamaz
        if attrs.get('expiry_date'):
            if attrs['expiry_date'] < timezone.now().date():
                raise serializers.ValidationError({
                    'expiry_date': 'Son geçerlilik tarihi geçmişte olamaz'
                })
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """
        Rezervasyon oluştur ve ödeme planını otomatik oluştur
        Transaction ile wrap edildi: Hata olursa tüm işlemler geri alınır
        """
        
        payment_plan_id = validated_data.pop('payment_plan_selected')
        property_instance = validated_data.get('property')
        payment_plan_obj = None

        if payment_plan_id == -1: # Peşin ödeme planı oluştur
            payment_plan_obj = PaymentPlan.objects.create(
                property=property_instance,
                plan_type=PaymentPlan.PlanType.PESIN,
                name='Peşin Ödeme (Otomatik)',
                details={'cash_price': float(property_instance.cash_price)},
                is_active=True
            )
        elif payment_plan_id == -2: # Temel vadeli plan oluştur
            payment_plan_obj = PaymentPlan.objects.create(
                property=property_instance,
                plan_type=PaymentPlan.PlanType.VADELI,
                name='Vadeli Ödeme (Otomatik)',
                details={'installment_price': float(property_instance.installment_price or property_instance.cash_price)},
                is_active=True
            )
        else: # Mevcut planı al
            try:
                payment_plan_obj = PaymentPlan.objects.get(pk=payment_plan_id)
            except PaymentPlan.DoesNotExist:
                raise serializers.ValidationError({'payment_plan_selected': 'Geçersiz ödeme planı ID\'si.'})

        try:
            # 🔒 Mülkü kilitle (pessimistic locking)
            property_to_update = Property.objects.select_for_update().get(
                id=property_instance.id
            )
            
            # Tekrar kontrol et (race condition önlemi)
            if not property_to_update.is_available():
                raise serializers.ValidationError({
                    'property': 'Bu mülk artık satılabilir durumda değil'
                })
            
            # Reservation nesnesini manuel oluşturuyoruz
            reservation = Reservation.objects.create(
                payment_plan_selected=payment_plan_obj,
                **validated_data
            )
            logger.info(f"Rezervasyon oluşturuldu: {reservation.id}")
            
            # Mülkü rezerve et
            property_to_update.reserve()
            logger.info(f"Mülk rezerve edildi: {property_to_update}")
            
            # Eğer vadeli ödeme planı seçildiyse, taksit ödeme planını oluştur
            if payment_plan_obj.plan_type == 'VADELI' and payment_plan_obj.details.get('installment_count'):
                self._create_installment_payments(reservation, payment_plan_obj)
                logger.info(f"Taksit ödeme planı oluşturuldu: {reservation.id}")
            
            return reservation
            
        except Exception as e:
            logger.error(f"Rezervasyon oluşturma hatası: {e}", exc_info=True)
            raise serializers.ValidationError(str(e)) # Hatanın API yanıtında görünmesini sağla
    
    def _create_installment_payments(self, reservation, payment_plan):
        """Taksit ödeme planını oluştur"""
        details = payment_plan.details
        
        installment_count = details.get('installment_count', 0)
        monthly_installment = Decimal(str(details.get('monthly_installment', 0)))
        
        # İlk taksit tarihi (rezervasyon tarihinden 1 ay sonra)
        first_payment_date = reservation.reservation_date.date() + timezone.timedelta(days=30)
        
        for i in range(1, installment_count + 1):
            due_date = first_payment_date + timezone.timedelta(days=30 * (i - 1))
            
            Payment.objects.create(
                reservation=reservation,
                payment_type=Payment.PaymentType.TAKSIT,
                amount=monthly_installment,
                status=Payment.Status.BEKLENIYOR,
                due_date=due_date,
                installment_number=i,
                recorded_by=reservation.created_by
            )
        
        logger.info(f"{installment_count} adet taksit kaydedildi")


class ReservationCancelSerializer(serializers.Serializer):
    """Rezervasyon iptal serializeri"""
    
    reason = serializers.CharField(
        required=True,
        max_length=500,
        help_text='İptal nedeni'
    )

class SalesReportSerializer(serializers.ModelSerializer):
    """
    Satış Raporu Serializer'ı.
    Bu serializer, SalesReport modelindeki veriyi olduğu gibi sunar.
    'statistics' alanı JSON olarak döner ve Flutter tarafında işlenir.
    """
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True)

    class Meta:
        model = SalesReport
        fields = [
            'id',
            'report_type',
            'report_type_display',
            'start_date',
            'end_date',
            'statistics', # JSON alanını doğrudan döndür
            'generated_by',
            'generated_by_name',
            'generated_at'
        ]

class SalesReportCreateSerializer(serializers.Serializer):
    """Rapor oluşturma verilerini doğrulama serializer'ı."""
    report_type = serializers.ChoiceField(choices=SalesReport.ReportType.choices)
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("Başlangıç tarihi bitiş tarihinden sonra olamaz.")
        return data
