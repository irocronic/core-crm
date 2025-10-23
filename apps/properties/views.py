# apps/properties/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg, Min, Max

from .models import Property, PropertyImage, PropertyDocument, PaymentPlan, Project
from .serializers import (
    PropertySerializer, PropertyDetailSerializer, PropertyCreateUpdateSerializer,
    PropertyImageSerializer, PropertyDocumentSerializer, PaymentPlanSerializer,
    PaymentPlanCreateSerializer, BulkPropertyCreateSerializer, ProjectSerializer
)
from .filters import PropertyFilter
from apps.users.permissions import IsAdmin, IsSalesManager, IsSalesRep


class ProjectViewSet(viewsets.ModelViewSet):
    """
    Proje yönetimi ViewSet
    
    list: Tüm projeleri istatistiklerle listele
    retrieve: Proje detayı
    create: Yeni proje oluştur
    update: Proje güncelle
    delete: Proje sil
    """
    queryset = Project.objects.annotate(
        property_count=Count('properties'),
        available_count=Count('properties', filter=Q(properties__status=Property.Status.SATILABILIR))
    )
    serializer_class = ProjectSerializer
    permission_classes = [IsSalesManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'location']
    ordering_fields = ['name', 'created_at', 'property_count']
    ordering = ['name']
    
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsSalesManager]
        return [permission() for permission in permission_classes]


class PropertyViewSet(viewsets.ModelViewSet):
    """
    Gayrimenkul (Mülk) yönetimi ViewSet
    
    list: Tüm mülkleri listele
    retrieve: Mülk detayı
    create: Yeni mülk ekle (Admin, Satış Müdürü)
    update: Mülk güncelle (Admin, Satış Müdürü)
    delete: Mülk sil (Admin)
    """
    
    queryset = Property.objects.select_related('created_by', 'project').prefetch_related(
        'images', 'documents', 'payment_plans'
    )
    serializer_class = PropertySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = {
        'status': ['exact'],
        'property_type': ['exact'],
        'room_count': ['icontains'],
        'cash_price': ['gte', 'lte'],
        'net_area_m2': ['gte', 'lte'],
        'project__id': ['exact'],
    }

    search_fields = ['project__name', 'block', 'unit_number', 'room_count', 'description']
    ordering_fields = ['created_at', 'cash_price', 'gross_area_m2', 'floor']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project', None)
        if project_id is not None:
            queryset = queryset.filter(project__id=project_id)
        return queryset

    def get_permissions(self):
        if self.action in ['create', 'bulk_create']:
            permission_classes = [IsSalesManager]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsSalesManager]
        elif self.action == 'destroy':
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PropertyDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PropertyCreateUpdateSerializer
        elif self.action == 'bulk_create':
            return BulkPropertyCreateSerializer
        return PropertySerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        self.perform_create(serializer)
        
        response_serializer = PropertyDetailSerializer(serializer.instance, context=self.get_serializer_context())
        
        headers = self.get_success_headers(response_serializer.data)
        
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        update_serializer = self.get_serializer(instance, data=request.data, partial=partial)
        update_serializer.is_valid(raise_exception=True)
        self.perform_update(update_serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        response_serializer = PropertyDetailSerializer(instance, context=self.get_serializer_context())
        
        return Response(response_serializer.data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        available_properties = self.get_queryset().filter(
            status=Property.Status.SATILABILIR
        )
        
        filtered_qs = self.filter_queryset(available_properties)
        
        page = self.paginate_queryset(filtered_qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(filtered_qs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        queryset = self.get_queryset()
        
        stats = {
            'total_properties': queryset.count(),
            'available': queryset.filter(status=Property.Status.SATILABILIR).count(),
            'reserved': queryset.filter(status=Property.Status.REZERVE).count(),
            'sold': queryset.filter(status=Property.Status.SATILDI).count(),
            'passive': queryset.filter(status=Property.Status.PASIF).count(),
            
            'by_type': {
                'daire': queryset.filter(property_type=Property.PropertyType.DAIRE).count(),
                'villa': queryset.filter(property_type=Property.PropertyType.VILLA).count(),
                'ofis': queryset.filter(property_type=Property.PropertyType.OFIS).count(),
            },
            
            'price_stats': queryset.aggregate(
                avg_cash_price=Avg('cash_price'),
                min_cash_price=Min('cash_price'),
                max_cash_price=Max('cash_price'),
            ),
            
            'area_stats': queryset.aggregate(
                avg_gross_area=Avg('gross_area_m2'),
                avg_net_area=Avg('net_area_m2'),
            ),
        }
        
        return Response(stats)
    
    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def upload_images(self, request, pk=None):
        property_instance = self.get_object()
        
        images_data = request.FILES.getlist('images')
        if not images_data:
            return Response(
                {'error': 'En az bir görsel yüklemelisiniz'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_images = []
        for index, image_file in enumerate(images_data):
            image_type = request.data.get(f'image_type_{index}', PropertyImage.ImageType.INTERIOR)
            title = request.data.get(f'title_{index}', '')
            
            image = PropertyImage.objects.create(
                property=property_instance,
                image=image_file,
                image_type=image_type,
                title=title,
                order=index
            )
            created_images.append(image)
        
        serializer = PropertyImageSerializer(created_images, many=True)
        return Response({
            'message': f'{len(created_images)} görsel başarıyla yüklendi',
            'images': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def upload_documents(self, request, pk=None):
        property_instance = self.get_object()
        
        document_file = request.FILES.get('document')
        if not document_file:
            return Response(
                {'error': 'Belge dosyası gerekli'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        document_type = request.data.get('document_type')
        title = request.data.get('title')
        
        if not document_type or not title:
            return Response(
                {'error': 'Belge tipi ve başlık gerekli'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        document = PropertyDocument.objects.create(
            property=property_instance,
            document=document_file,
            document_type=document_type,
            title=title,
            uploaded_by=request.user
        )
        
        serializer = PropertyDocumentSerializer(document)
        return Response({
            'message': 'Belge başarıyla yüklendi',
            'document': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def create_payment_plan(self, request, pk=None):
        property_instance = self.get_object()
        
        serializer = PaymentPlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        payment_plan = serializer.create_payment_plan(property_instance)
        
        return Response({
            'message': 'Ödeme planı başarıyla oluşturuldu',
            'payment_plan': PaymentPlanSerializer(payment_plan).data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        created_properties = serializer.save()
        
        return Response({
            'message': f'{len(created_properties)} mülk başarıyla eklendi',
            'properties': PropertySerializer(created_properties, many=True).data
        }, status=status.HTTP_201_CREATED)

class PropertyImageViewSet(viewsets.ModelViewSet):
    queryset = PropertyImage.objects.all()
    serializer_class = PropertyImageSerializer
    permission_classes = [IsSalesManager]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        property_id = self.request.query_params.get('property_id')
        if property_id:
            return self.queryset.filter(property_id=property_id)
        return self.queryset


class PropertyDocumentViewSet(viewsets.ModelViewSet):
    queryset = PropertyDocument.objects.all()
    serializer_class = PropertyDocumentSerializer
    permission_classes = [IsSalesManager]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        property_id = self.request.query_params.get('property_id')
        if property_id:
            return self.queryset.filter(property_id=property_id)
        return self.queryset
    
    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class PaymentPlanViewSet(viewsets.ModelViewSet):
    queryset = PaymentPlan.objects.select_related('property')
    serializer_class = PaymentPlanSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsSalesManager]
        else:
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        property_id = self.request.query_params.get('property_id')
        if property_id:
            return self.queryset.filter(property_id=property_id, is_active=True)
        return self.queryset.filter(is_active=True)
    
    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def deactivate(self, request, pk=None):
        payment_plan = self.get_object()
        payment_plan.is_active = False
        payment_plan.save(update_fields=['is_active'])
        
        return Response({'message': 'Ödeme planı deaktif edildi'})
