# apps/crm/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg
from django.utils import timezone
import logging

from .models import Customer, Activity, Appointment, Note
from .serializers import (
    CustomerSerializer, CustomerDetailSerializer, CustomerCreateSerializer,
    CustomerUpdateSerializer, ActivitySerializer, ActivityCreateSerializer,
    AppointmentSerializer, AppointmentCreateSerializer, NoteSerializer,
    CustomerAssignSerializer, TimelineEventSerializer
)
# **** ActivityFilter import edildi ****
from .filters import CustomerFilter, AppointmentFilter, ActivityFilter
from .services import NotificationService, CustomerService
from apps.users.permissions import IsAdmin, IsSalesManager, IsSalesRep, IsAssistant

logger = logging.getLogger(__name__)


class CustomerViewSet(viewsets.ModelViewSet):
    """
    Müşteri yönetimi ViewSet

    list: Tüm müşterileri listele
    retrieve: Müşteri detayı
    create: Yeni müşteri ekle
    update: Müşteri güncelle
    delete: Müşteri sil (Admin)
    """

    queryset = Customer.objects.select_related('assigned_to', 'created_by').prefetch_related(
        'activities', 'appointments', 'extra_notes'
    )
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CustomerFilter
    search_fields = ['full_name', 'phone_number', 'email', 'interested_in']
    ordering_fields = ['created_at', 'full_name']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [IsAuthenticated]
        elif self.action == 'destroy':
            permission_classes = [IsAdmin]
        elif self.action in ['assign_customers']:
            permission_classes = [IsSalesManager]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CustomerDetailSerializer
        elif self.action == 'create':
            return CustomerCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CustomerUpdateSerializer
        elif self.action == 'assign_customers':
            return CustomerAssignSerializer
        elif self.action == 'timeline':
            return TimelineEventSerializer
        return CustomerSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_admin() or user.is_sales_manager():
            return Customer.objects.all()

        if user.is_sales_rep():
            return Customer.objects.filter(
                Q(assigned_to=user) | Q(created_by=user)
            ).distinct()

        if user.is_assistant():
            return Customer.objects.filter(created_by=user)

        return Customer.objects.none()

    def perform_create(self, serializer):
        customer = serializer.save(created_by=self.request.user)

        if customer.assigned_to:
            NotificationService.send_customer_assigned_notification(
                sales_rep=customer.assigned_to,
                customer=customer,
                assigned_by=self.request.user
            )

        logger.info(f"Yeni müşteri eklendi: {customer.full_name} (Ekleyen: {self.request.user.username})")

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """
        Bir müşterinin tüm aktivite ve randevularını kronolojik olarak listeler.
        GET /api/v1/crm/customers/{id}/timeline/
        """
        customer = self.get_object()
        timeline_data = CustomerService.get_customer_timeline(customer)

        serializer = self.get_serializer(timeline_data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_customers(self, request):
        """
        Giriş yapan kullanıcının müşterileri
        GET /api/v1/crm/customers/my_customers/
        """
        user = request.user

        if user.is_admin() or user.is_sales_manager():
            customers = Customer.objects.all()
        elif user.is_sales_rep():
            customers = Customer.objects.filter(
                Q(assigned_to=user) | Q(created_by=user)
            ).distinct()
        elif user.is_assistant():
            customers = Customer.objects.filter(created_by=user)
        else:
            customers = Customer.objects.none()

        filtered_qs = self.filter_queryset(customers)
        page = self.paginate_queryset(filtered_qs)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(filtered_qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def hot_leads(self, request):
        """
        Sıcak müşteriler (outcome_score >= 75)
        GET /api/v1/crm/customers/hot_leads/
        """
        customers = self.get_queryset()

        hot_customers_ids = [
            customer.id for customer in customers if customer.get_win_probability() >= 75
        ]
        hot_customers_queryset = Customer.objects.filter(id__in=hot_customers_ids)

        page = self.paginate_queryset(hot_customers_queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(hot_customers_queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsSalesManager])
    def assign_customers(self, request):
        """
        Toplu müşteri atama
        POST /api/v1/crm/customers/assign_customers/
        Body: {
            "customer_ids": [1, 2, 3],
            "sales_rep_id": 5
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer_ids = serializer.validated_data['customer_ids']
        sales_rep_id = serializer.validated_data['sales_rep_id']

        from apps.users.models import User
        sales_rep = User.objects.get(id=sales_rep_id)

        customers = Customer.objects.filter(id__in=customer_ids)
        updated_count = 0

        for customer in customers:
            customer.assigned_to = sales_rep
            customer.save(update_fields=['assigned_to'])

            NotificationService.send_customer_assigned_notification(
                sales_rep=sales_rep,
                customer=customer,
                assigned_by=request.user
            )

            updated_count += 1

        return Response({
            'message': f'{updated_count} müşteri başarıyla atandı',
            'assigned_to': sales_rep.get_full_name()
        })

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        """
        Müşteriyi başka bir satış temsilcisine transfer et
        POST /api/v1/crm/customers/{id}/transfer/
        Body: {"sales_rep_id": 5}
        """
        customer = self.get_object()
        sales_rep_id = request.data.get('sales_rep_id')

        if not sales_rep_id:
            return Response(
                {'error': 'sales_rep_id gerekli'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.users.models import User
        try:
            new_sales_rep = User.objects.get(id=sales_rep_id, role=User.Role.SATIS_TEMSILCISI)
        except User.DoesNotExist:
            return Response(
                {'error': 'Satış temsilcisi bulunamadı'},
                status=status.HTTP_404_NOT_FOUND
            )

        old_sales_rep = customer.assigned_to
        customer.assigned_to = new_sales_rep
        customer.save(update_fields=['assigned_to'])

        NotificationService.send_customer_transferred_notification(
            new_sales_rep=new_sales_rep,
            old_sales_rep=old_sales_rep,
            customer=customer,
            transferred_by=request.user
        )

        return Response({
            'message': 'Müşteri başarıyla transfer edildi',
            'transferred_to': new_sales_rep.get_full_name()
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Müşteri istatistikleri
        GET /api/v1/crm/customers/statistics/
        """
        queryset = self.get_queryset()

        stats = {
            'total_customers': queryset.count(),
            'by_source': {},
            'hot_leads': 0,
            'with_appointments_today': 0,
        }

        for source in Customer.Source:
            count = queryset.filter(source=source.value).count()
            if count > 0:
                stats['by_source'][source.label] = count

        for customer in queryset:
            if customer.get_win_probability() >= 75:
                stats['hot_leads'] += 1
            if customer.has_appointment_today():
                stats['with_appointments_today'] += 1

        return Response(stats)


class ActivityViewSet(viewsets.ModelViewSet):
    """Aktivite (Görüşme) yönetimi ViewSet"""

    queryset = Activity.objects.select_related('customer', 'created_by')
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
    # **** GÜNCELLEME: filterset_class, search_fields, ordering_fields ****
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ActivityFilter # Yeni filter sınıfı
    search_fields = ['customer__full_name', 'notes', 'created_by__username']
    ordering_fields = ['created_at', 'next_follow_up_date', 'outcome_score']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return ActivityCreateSerializer
        return ActivitySerializer

    def get_queryset(self):
        user = self.request.user

        # Admin ve Satış Müdürü tüm aktiviteleri görebilir (filtreler daha sonra uygulanır)
        if user.is_admin() or user.is_sales_manager():
            return Activity.objects.all()

        # Satış temsilcisi sadece kendi oluşturduğu veya müşterisiyle ilgili olanları görür
        # (Bu kısım isteğe bağlı olarak sadece created_by=user da olabilir)
        if user.is_sales_rep():
            # Müşterilerini al
            customer_ids = Customer.objects.filter(assigned_to=user).values_list('id', flat=True)
            return Activity.objects.filter(
                Q(created_by=user) | Q(customer_id__in=list(customer_ids))
            ).distinct()

        # Asistan sadece kendi oluşturduklarını görür
        if user.is_assistant():
            return Activity.objects.filter(created_by=user)

        return Activity.objects.none()

    def perform_create(self, serializer):
        activity = serializer.save(created_by=self.request.user)

        # Takip tarihi ayarlandıysa (ileride bildirim vb. için kullanılabilir)
        if activity.next_follow_up_date:
            pass

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def upcoming_followups(self, request):
        """
        Giriş yapan kullanıcının yaklaşan takip aktivitelerini listeler.
        GET /api/v1/crm/activities/upcoming_followups/
        """
        today = timezone.now()

        # Kullanıcının yetkisi dahilindeki aktiviteleri al
        user_activities = self.get_queryset()

        # Takip tarihi bugünden büyük veya eşit olanları filtrele
        upcoming = user_activities.filter(
            next_follow_up_date__isnull=False,
            next_follow_up_date__gte=today
        ).order_by('next_follow_up_date')

        # Sayfalama olmadan tüm sonuçları döndür
        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)


class AppointmentViewSet(viewsets.ModelViewSet):
    """Randevu yönetimi ViewSet"""

    queryset = Appointment.objects.select_related('customer', 'sales_rep')
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = AppointmentFilter
    ordering_fields = ['appointment_date']
    ordering = ['appointment_date']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AppointmentCreateSerializer
        return AppointmentSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_admin():
            return Appointment.objects.all()

        if user.is_sales_manager():
            team_members = user.get_team_members()
            return Appointment.objects.filter(
                Q(sales_rep__in=team_members) | Q(sales_rep=user)
            )

        if user.is_sales_rep():
            return Appointment.objects.filter(sales_rep=user)

        return Appointment.objects.none()

    @action(detail=False, methods=['get'])
    def today(self, request):
        """
        Bugünkü randevular
        GET /api/v1/crm/appointments/today/
        """
        today = timezone.now().date()
        appointments = self.get_queryset().filter(
            appointment_date__date=today,
            status=Appointment.Status.PLANLANDI
        )

        serializer = self.get_serializer(appointments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Yaklaşan randevular (gelecek 7 gün)
        GET /api/v1/crm/appointments/upcoming/
        """
        today = timezone.now()
        next_week = today + timezone.timedelta(days=7)

        appointments = self.get_queryset().filter(
            appointment_date__range=(today, next_week),
            status=Appointment.Status.PLANLANDI
        ).order_by('appointment_date')

        serializer = self.get_serializer(appointments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Randevuyu tamamla
        POST /api/v1/crm/appointments/{id}/complete/
        """
        appointment = self.get_object()

        if appointment.status != Appointment.Status.PLANLANDI:
            return Response(
                {'error': 'Sadece planlanmış randevular tamamlanabilir'},
                status=status.HTTP_400_BAD_REQUEST
            )

        appointment.status = Appointment.Status.TAMAMLANDI
        appointment.save(update_fields=['status'])

        return Response({
            'message': 'Randevu tamamlandı olarak işaretlendi',
            'appointment': AppointmentSerializer(appointment).data
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Randevuyu iptal et
        POST /api/v1/crm/appointments/{id}/cancel/
        """
        appointment = self.get_object()

        if appointment.status != Appointment.Status.PLANLANDI:
            return Response(
                {'error': 'Sadece planlanmış randevular iptal edilebilir'},
                status=status.HTTP_400_BAD_REQUEST
            )

        appointment.status = Appointment.Status.IPTAL_EDILDI
        appointment.save(update_fields=['status'])

        return Response({
            'message': 'Randevu iptal edildi',
            'appointment': AppointmentSerializer(appointment).data
        })


class NoteViewSet(viewsets.ModelViewSet):
    """Müşteri notu yönetimi ViewSet"""

    queryset = Note.objects.select_related('customer', 'created_by')
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['customer', 'is_important']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        # Filtreleme için customer ID'sini al
        customer_id = self.request.query_params.get('customer') # 'customer_id' yerine 'customer'

        queryset = Note.objects.none() # Varsayılan olarak boş

        if user.is_admin() or user.is_sales_manager():
            queryset = Note.objects.all()
        elif user.is_sales_rep():
            # Temsilci kendi notlarını ve atanan müşterilerin notlarını görebilir
            customer_ids = Customer.objects.filter(assigned_to=user).values_list('id', flat=True)
            queryset = Note.objects.filter(
                Q(created_by=user) | Q(customer_id__in=list(customer_ids))
            ).distinct()
        elif user.is_assistant():
            queryset = Note.objects.filter(created_by=user)

        # Eğer customer ID ile filtreleme yapılıyorsa, onu uygula
        if customer_id:
            try:
                # Gelen customer ID'nin kullanıcının görmeye yetkili olduğu
                # müşterilerden biri olup olmadığını kontrol etmeye gerek yok
                # çünkü ilk queryset zaten yetkiye göre filtrelenmişti.
                queryset = queryset.filter(customer_id=int(customer_id))
            except ValueError:
                # Geçersiz customer ID ise boş döndür
                queryset = Note.objects.none()

        return queryset.select_related('customer', 'created_by') # İlişkili verileri çek

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
