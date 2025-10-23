# apps/sales/views.py

from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
import logging

from .models import Reservation, Payment, Contract, SalesReport
from .serializers import (
    ReservationSerializer, ReservationDetailSerializer, ReservationCreateSerializer,
    ReservationCancelSerializer, PaymentSerializer, PaymentCreateSerializer,
    ContractSerializer, SalesReportSerializer, SalesReportCreateSerializer
)
from .filters import ReservationFilter, PaymentFilter
from .services import ReservationService, PaymentService, ContractService, ReportService
from apps.users.permissions import IsAdmin, IsSalesManager, IsSalesRep

logger = logging.getLogger(__name__)


class ReservationViewSet(viewsets.ModelViewSet):
    """
    Rezervasyon yönetimi ViewSet
    
    list: Tüm rezervasyonları listele
    retrieve: Rezervasyon detayı
    create: Yeni rezervasyon oluştur (Satış Temsilcisi)
    update: Rezervasyon güncelle
    delete: Rezervasyon sil (Admin)
    """
    
    queryset = Reservation.objects.select_related(
        'property', 'customer', 'sales_rep', 'payment_plan_selected', 'created_by'
    ).prefetch_related('payments', 'contracts')
    
    serializer_class = ReservationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ReservationFilter
    search_fields = ['customer__full_name', 'customer__phone_number', 'property__project__name']
    ordering_fields = ['reservation_date', 'created_at']
    ordering = ['-reservation_date']
    
    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [IsSalesRep]
        elif self.action == 'destroy':
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ReservationDetailSerializer
        elif self.action == 'create':
            return ReservationCreateSerializer
        elif self.action == 'cancel':
            return ReservationCancelSerializer
        return ReservationSerializer
    
    def get_queryset(self):
        """
        Kullanıcının rolüne ve isteğe göre queryset'i filtreler.
        Eğer 'customer_id' ile bir filtreleme yapılıyorsa, kullanıcının
        o müşterinin tüm satışlarını görmesine izin verilir.
        """
        user = self.request.user
        customer_id_filter = self.request.query_params.get('customer_id')

        # Admin, Satış Müdürü veya belirli bir müşteri için sorgu yapılıyorsa tüm rezervasyonları getir.
        # Filtreleme işlemini DjangoFilterBackend halledecektir.
        if user.is_admin() or user.is_sales_manager() or customer_id_filter:
            return Reservation.objects.all()
        
        # Satış temsilcisi, genel rezervasyon listesini görüntülüyorsa sadece kendi kayıtlarını görsün.
        if user.is_sales_rep():
            return Reservation.objects.filter(sales_rep=user)
        
        # Diğer tüm durumlar için boş queryset döndür.
        return Reservation.objects.none()
    
    # **** GÜNCELLEME BAŞLANGICI ****
    def perform_create(self, serializer):
        """
        Yeni bir rezervasyon oluşturulurken, 'created_by' alanını ve
        gerekirse 'sales_rep' alanını otomatik olarak doldurur.
        """
        # Eğer frontend'den bir satış temsilcisi gönderilmediyse veya boş gönderildiyse,
        # işlemi yapan kullanıcıyı varsayılan satış temsilcisi olarak ata.
        sales_rep = serializer.validated_data.get('sales_rep')
        if not sales_rep:
            serializer.save(created_by=self.request.user, sales_rep=self.request.user)
        else:
            # Frontend'den bir satış temsilcisi zaten seçilmişse, sadece 'created_by' alanını ekle.
            serializer.save(created_by=self.request.user)
    # **** GÜNCELLEME SONU ****

    def create(self, request, *args, **kwargs):
        """
        Yeni rezervasyon oluşturur ve yanıt olarak tam detaylı veriyi döner.
        """
        create_serializer = self.get_serializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        self.perform_create(create_serializer)

        instance = create_serializer.instance

        response_serializer = ReservationDetailSerializer(instance, context=self.get_serializer_context())
        
        headers = self.get_success_headers(response_serializer.data)
        
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Aktif rezervasyonlar
        GET /api/v1/sales/reservations/active/
        """
        active_reservations = self.get_queryset().filter(
            status=Reservation.Status.AKTIF
        )
        
        filtered_qs = self.filter_queryset(active_reservations)
        page = self.paginate_queryset(filtered_qs)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(filtered_qs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_sales(self, request):
        """
        Giriş yapan satış temsilcisinin veya satış müdürünün kendi satışları
        GET /api/v1/sales/reservations/my_sales/
        """
        if not (request.user.is_sales_rep() or request.user.is_sales_manager()):
            return Response(
                {'error': 'Bu endpoint sadece satış personeli içindir'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        my_reservations = Reservation.objects.filter(sales_rep=request.user)
        filtered_qs = self.filter_queryset(my_reservations)
        
        page = self.paginate_queryset(filtered_qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(filtered_qs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsSalesRep])
    def convert_to_sale(self, request, pk=None):
        """
        Rezervasyonu satışa dönüştür
        POST /api/v1/sales/reservations/{id}/convert_to_sale/
        """
        reservation = self.get_object()
        
        success, message = reservation.convert_to_sale()
        
        if success:
            return Response({
                'message': message,
                'reservation': ReservationDetailSerializer(reservation).data
            })
        else:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def cancel(self, request, pk=None):
        """
        Rezervasyonu iptal et
        POST /api/v1/sales/reservations/{id}/cancel/
        Body: {"reason": "İptal nedeni"}
        """
        reservation = self.get_object()
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        reason = serializer.validated_data['reason']
        success, message = reservation.cancel(reason=reason)
        
        if success:
            return Response({
                'message': message,
                'reservation': ReservationDetailSerializer(reservation).data
            })
        else:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Rezervasyon istatistikleri
        GET /api/v1/sales/reservations/statistics/
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_reservations': queryset.count(),
            'active': queryset.filter(status=Reservation.Status.AKTIF).count(),
            'converted_to_sales': queryset.filter(status=Reservation.Status.SATISA_DONUSTU).count(),
            'cancelled': queryset.filter(status=Reservation.Status.IPTAL_EDILDI).count(),
            
            'total_deposit_amount': queryset.aggregate(
                total=Sum('deposit_amount')
            )['total'] or 0,
            
            'avg_deposit_amount': queryset.aggregate(
                avg=Avg('deposit_amount')
            )['avg'] or 0,
            
            'by_payment_method': {},
        }
        
        for method in Reservation.PaymentMethod:
            count = queryset.filter(deposit_payment_method=method.value).count()
            if count > 0:
                stats['by_payment_method'][method.label] = count
        
        return Response(stats)


class PaymentViewSet(viewsets.ModelViewSet):
    """Ödeme yönetimi ViewSet"""
    
    queryset = Payment.objects.select_related('reservation', 'recorded_by')
    serializer_class = PaymentSerializer
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = PaymentFilter
    ordering_fields = ['due_date', 'payment_date']
    ordering = ['due_date']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsSalesRep]
        else:
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PaymentCreateSerializer
        
        return PaymentSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_admin():
            return Payment.objects.all()
        
        if user.is_sales_manager():
            team_members = user.get_team_members()
            return Payment.objects.filter(
                Q(reservation__sales_rep__in=team_members) | Q(reservation__sales_rep=user)
            )
        
        if user.is_sales_rep():
            return Payment.objects.filter(reservation__sales_rep=user)
        
        return Payment.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """
        Bekleyen ödemeler
        GET /api/v1/sales/payments/pending/
        """
        pending_payments = self.get_queryset().filter(
            status=Payment.Status.BEKLENIYOR
        )
        
        serializer = self.get_serializer(pending_payments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Gecikmiş ödemeler
        GET /api/v1/sales/payments/overdue/
        """
        today = timezone.now().date()
        
        overdue_payments = self.get_queryset().filter(
            status=Payment.Status.BEKLENIYOR,
            due_date__lt=today
        )
        
        serializer = self.get_serializer(overdue_payments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        """
        Ödemeyi tahsil edildi olarak işaretle
        POST /api/v1/sales/payments/{id}/mark_as_paid/
        Body: {
            "payment_date": "2025-10-15",
            "payment_method": "NAKIT",
            "receipt_number": "12345"
        }
        """
        payment = self.get_object()
        
        payment_date = request.data.get('payment_date')
        payment_method = request.data.get('payment_method')
        receipt_number = request.data.get('receipt_number', '')
        
        if not payment_method:
            return Response(
                {'error': 'payment_method gerekli'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment.mark_as_paid(
            payment_date=payment_date,
            payment_method=payment_method,
            receipt_number=receipt_number
        )
        
        return Response({
            'message': 'Ödeme başarıyla tahsil edildi olarak işaretlendi',
            'payment': PaymentSerializer(payment).data
        })


class ContractViewSet(viewsets.ModelViewSet):
    """Sözleşme yönetimi ViewSet"""
    
    queryset = Contract.objects.select_related('reservation', 'created_by')
    serializer_class = ContractSerializer
    
    permission_classes = [IsSalesRep]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['reservation', 'contract_type', 'status']
    ordering = ['-contract_date']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_admin():
            return Contract.objects.all()
        
        if user.is_sales_manager():
            team_members = user.get_team_members()
            return Contract.objects.filter(
                Q(reservation__sales_rep__in=team_members) | Q(reservation__sales_rep=user)
            )
        
        if user.is_sales_rep():
            return Contract.objects.filter(reservation__sales_rep=user)
        
        return Contract.objects.none()
    
    def perform_create(self, serializer):
        """
        Yeni sözleşme oluştururken otomatik olarak:
        1. Sözleşme numarasını oluşturur.
        2. Oluşturan kullanıcıyı atar.
        3. Durumu 'Taslak' olarak belirler.
        4. PDF dosyasını oluşturur ve kaydeder.
        """
        contract_type = serializer.validated_data.get('contract_type')
        contract_number = ContractService.generate_contract_number(contract_type)
        
        contract = serializer.save(
            created_by=self.request.user,
            contract_number=contract_number,
            status=Contract.Status.TASLAK
        )
        
        pdf_file = ContractService.generate_contract_pdf(contract)
        if pdf_file:
            contract.contract_file = pdf_file
            contract.save(update_fields=['contract_file'])
    
    @action(detail=True, methods=['post'])
    def mark_as_signed(self, request, pk=None):
        """
        Sözleşmeyi imzalandı olarak işaretle
        POST /api/v1/sales/contracts/{id}/mark_as_signed/
        Body: {"signed_date": "2025-10-15"}
        """
        contract = self.get_object()
        
        signed_date = request.data.get('signed_date')
        contract.mark_as_signed(signed_date=signed_date)
        
        return Response({
            'message': 'Sözleşme imzalandı olarak işaretlendi',
            'contract': ContractSerializer(contract).data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def cancel(self, request, pk=None):
        """
        Sözleşmeyi iptal et
        POST /api/v1/sales/contracts/{id}/cancel/
        Body: {"cancellation_reason": "İptal nedeni"}
        """
        contract = self.get_object()
        reason = request.data.get('cancellation_reason')

        if not reason:
            return Response(
                {'error': 'İptal nedeni gereklidir.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if contract.status == Contract.Status.IMZALANDI:
            return Response(
                {'error': 'İmzalanmış sözleşmeler iptal edilemez.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if contract.status == Contract.Status.IPTAL:
            return Response(
                {'error': 'Bu sözleşme zaten iptal edilmiş.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        contract.status = Contract.Status.IPTAL
        contract.notes = f"{contract.notes or ''}\n\nİptal Nedeni: {reason}".strip()
        contract.save(update_fields=['status', 'notes'])

        return Response({
            'message': 'Sözleşme başarıyla iptal edildi',
            'contract': self.get_serializer(contract).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsSalesRep])
    def generate_pdf(self, request, pk=None):
        """
        Sözleşme PDF oluştur
        POST /api/v1/sales/contracts/{id}/generate_pdf/
        """
        contract = self.get_object()
        
        pdf_file = ContractService.generate_contract_pdf(contract)
        
        if pdf_file:
            contract.contract_file = pdf_file
            contract.save(update_fields=['contract_file'])
            
            return Response({
                'message': 'Sözleşme PDF başarıyla oluşturuldu',
                'contract': ContractSerializer(contract).data
            })
        else:
            return Response(
                {'error': 'PDF oluşturulamadı'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SalesReportViewSet(viewsets.ModelViewSet):
    """
    Satış raporu ViewSet
    """
    queryset = SalesReport.objects.select_related('generated_by')
    serializer_class = SalesReportSerializer
    permission_classes = [IsSalesManager]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-generated_at']

    def get_permissions(self):
        if self.action in ['generate']:
            permission_classes = [IsSalesManager]
        else:
            permission_classes = [IsSalesManager]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'generate':
            return SalesReportCreateSerializer
        return SalesReportSerializer

    @action(detail=False, methods=['post'], permission_classes=[IsSalesManager])
    def generate(self, request):
        """
        Yeni bir satış raporu oluşturur.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            report = ReportService.generate_sales_report(
                report_type=serializer.validated_data['report_type'],
                start_date=serializer.validated_data['start_date'],
                end_date=serializer.validated_data['end_date'],
                generated_by=request.user,
            )
            response_serializer = SalesReportSerializer(report)
            
            logger.info(
                f"✅ Rapor oluşturuldu: {report.id} - "
                f"Type: {report.report_type} - "
                f"User: {request.user.username}"
            )
            
            return Response(
                {'message': 'Rapor başarıyla oluşturuldu', 'report': response_serializer.data},
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"❌ Satış raporu oluşturma hatası: {e}", exc_info=True)
            return Response(
                {'error': f'Rapor oluşturulamadı: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
