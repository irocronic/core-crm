# apps/properties/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser # <-- Eklendi
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg, Min, Max
from django.http import HttpResponse # <-- Eklendi
from django.db import transaction # <-- Eklendi
import csv # <-- Eklendi
import io # <-- Eklendi
import logging # <-- Eklendi

from .models import Property, PropertyImage, PropertyDocument, PaymentPlan, Project
from .serializers import (
    PropertySerializer, PropertyDetailSerializer, PropertyCreateUpdateSerializer,
    PropertyImageSerializer, PropertyDocumentSerializer, PaymentPlanSerializer,
    PaymentPlanCreateSerializer, BulkPropertyCreateSerializer, ProjectSerializer
)
from .filters import PropertyFilter
from apps.users.permissions import IsAdmin, IsSalesManager, IsSalesRep

logger = logging.getLogger(__name__) # <-- Eklendi


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

    # 🔥 GÜNCELLEME: Proje eklerken MultiPartParser ekliyoruz (resim yükleme için)
    parser_classes = [MultiPartParser, FormParser] # <-- Eklendi

    # 🔥 YENİ: pagination_class = None kaldırıldı, gerekirse eklenir.
    # pagination_class = None #

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            # Sadece Admin ve Satış Müdürü proje oluşturabilir/güncelleyebilir/silebilir
            permission_classes = [IsSalesManager] # Değişiklik yok ama teyit edelim
        return [permission() for permission in permission_classes]

    # 🔥 YENİ: perform_create metodu eklendi (resimlerle proje oluşturma)
    def perform_create(self, serializer):
        project_image = self.request.FILES.get('project_image')
        site_plan_image = self.request.FILES.get('site_plan_image')
        serializer.save(
            project_image=project_image,
            site_plan_image=site_plan_image
        )


class PropertyViewSet(viewsets.ModelViewSet):
    """
    Gayrimenkul (Mülk) yönetimi ViewSet
    
    list: Tüm mülkleri listele
    retrieve: Mülk detayı
    create: Yeni mülk ekle (Admin, Satış Müdürü)
    update: Mülk güncelle (Admin, Satış Müdürü)
    delete: Mülk sil (Admin)

    --- YENİ ACTIONS ---
    export_sample_csv: Örnek CSV şablonunu indirir.
    bulk_create_from_csv: CSV dosyasından toplu mülk oluşturur.
    """

    queryset = Property.objects.select_related('created_by', 'project').prefetch_related(
        'images', 'documents', 'payment_plans'
    )
    serializer_class = PropertySerializer
    # 🔥 YENİ: Toplu yükleme için MultiPartParser ekleniyor
    parser_classes = [MultiPartParser, FormParser] # <-- Eklendi
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = {
        'status': ['exact'],
        'property_type': ['exact'],
        'room_count': ['icontains'], #
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
        if project_id is not None: #
            queryset = queryset.filter(project__id=project_id) #
        return queryset

    def get_permissions(self):
        # 🔥 YENİ: Yeni action'lar için izinler ekleniyor
        if self.action in ['create', 'bulk_create_from_csv', 'export_sample_csv']: # 'bulk_create' -> 'bulk_create_from_csv' olarak değiştirildi
            permission_classes = [IsSalesManager] # Sadece SM ve Admin
        elif self.action in ['update', 'partial_update', 'upload_images', 'upload_documents', 'create_payment_plan']: # Mevcut action'lar
             permission_classes = [IsSalesManager] # Sadece SM ve Admin
        elif self.action == 'destroy':
            permission_classes = [IsAdmin] # Sadece Admin silebilir
        else: # list, retrieve, available, statistics
            permission_classes = [IsAuthenticated] # Tüm giriş yapmış kullanıcılar görebilir
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PropertyDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']: #
            return PropertyCreateUpdateSerializer #
        # 🔥 YENİ: bulk_create_from_csv action'ı için serializer (zaten vardı)
        elif self.action == 'bulk_create_from_csv': # 'bulk_create' -> 'bulk_create_from_csv' olarak değiştirildi
            return BulkPropertyCreateSerializer #
        return PropertySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        response_serializer = PropertyDetailSerializer(serializer.instance, context=self.get_serializer_context()) #
        headers = self.get_success_headers(response_serializer.data) #
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers) #

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        update_serializer = self.get_serializer(instance, data=request.data, partial=partial) #
        update_serializer.is_valid(raise_exception=True) #
        self.perform_update(update_serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        response_serializer = PropertyDetailSerializer(instance, context=self.get_serializer_context()) #
        return Response(response_serializer.data) #

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def available(self, request):
        available_properties = self.get_queryset().filter( #
            status=Property.Status.SATILABILIR #
        )
        filtered_qs = self.filter_queryset(available_properties) #
        page = self.paginate_queryset(filtered_qs)
        if page is not None: #
            serializer = self.get_serializer(page, many=True) #
            return self.get_paginated_response(serializer.data) #
        serializer = self.get_serializer(filtered_qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        queryset = self.get_queryset()
        stats = {
            'total_properties': queryset.count(),
            'available': queryset.filter(status=Property.Status.SATILABILIR).count(),
            'reserved': queryset.filter(status=Property.Status.REZERVE).count(), #
            'sold': queryset.filter(status=Property.Status.SATILDI).count(), #
            'passive': queryset.filter(status=Property.Status.PASIF).count(), #
            'by_type': {
                'daire': queryset.filter(property_type=Property.PropertyType.DAIRE).count(),
                'villa': queryset.filter(property_type=Property.PropertyType.VILLA).count(),
                'ofis': queryset.filter(property_type=Property.PropertyType.OFIS).count(), #
            },
            'price_stats': queryset.aggregate( #
                avg_cash_price=Avg('cash_price'),
                min_cash_price=Min('cash_price'),
                max_cash_price=Max('cash_price'),
            ), #
            'area_stats': queryset.aggregate( #
                avg_gross_area=Avg('gross_area_m2'),
                avg_net_area=Avg('net_area_m2'),
            ), #
        }
        return Response(stats) #

    # --- ÖRNEK CSV EXPORT ACTION ---
    @action(detail=False, methods=['get'], url_path='export-sample-csv')
    def export_sample_csv(self, request):
        """
        Kullanıcının doldurması için örnek bir CSV şablonu oluşturur ve indirir.
        """
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="ornek_mulk_sablonu.csv"'

        # CSV Writer oluştur
        # Excel'in Türkçe karakterleri doğru görmesi için utf-8-sig kullan
        response.write(u'\ufeff'.encode('utf8')) # BOM ekle
        writer = csv.writer(response, delimiter=';') # Excel genellikle ';' kullanır

        # Başlık Satırı (Serializer field'ları + project_name)
        # Dikkat: Serializer'daki 'project' alanı yerine kullanıcı dostu 'project_name' kullanıyoruz.
        # Import sırasında bu 'project_name'i ID'ye çevireceğiz.
        headers = [
            'project_name', 'block', 'floor', 'unit_number', 'property_type',
            'room_count', 'gross_area_m2', 'net_area_m2', 'cash_price',
            'installment_price', 'facade', 'status', 'description',
            # 'island', 'parcel' # Bunlar artık Proje modelinde, opsiyonel olarak eklenebilir
        ]
        writer.writerow(headers)

        # Örnek Veri Satırları (Opsiyonel ama kullanıcıya yardımcı olur)
        sample_data = [
            ['RealtyFlow Towers', 'A', '5', '21', 'DAIRE', '2+1', '120.50', '95.00', '2500000.00', '2800000.00', 'GUNEY', 'SATILABILIR', 'Geniş ve ferah daire'],
            ['RealtyFlow Towers', 'A', '6', '25', 'DAIRE', '3+1', '155.00', '125.75', '3500000.00', '', 'DOGU', 'SATILABILIR', 'Deniz manzaralı'], # Vadeli fiyat boş olabilir
            ['Vadi Konakları', 'B', '1', '2', 'VILLA', '5+2', '450.00', '380.00', '12000000.00', '', 'BATI', 'SATILABILIR', 'Müstakil bahçeli lüks villa'],
        ]
        for row in sample_data:
            writer.writerow(row)

        logger.info(f"Örnek CSV şablonu indirildi - User: {request.user.username}")
        return response

    # --- TOPLU CSV IMPORT ACTION ---
    @action(detail=False, methods=['post'], url_path='bulk-create-from-csv')
    @transaction.atomic # Tüm işlemler başarılı olursa kaydet, hata olursa geri al
    def bulk_create_from_csv(self, request):
        """
        Yüklenen CSV dosyasından toplu olarak Property (Gayrimenkul) oluşturur.
        CSV'de 'project_name' alanı olmalı ve bu isimde bir Proje veritabanında bulunmalıdır.
        """
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'error': 'CSV dosyası bulunamadı.'}, status=status.HTTP_400_BAD_REQUEST)

        # Dosya CSV mi kontrol et (basit kontrol)
        if not csv_file.name.lower().endswith('.csv'):
            return Response({'error': 'Lütfen geçerli bir CSV dosyası yükleyin.'}, status=status.HTTP_400_BAD_REQUEST)

        created_properties = []
        errors = []
        required_headers = { # CSV'de olması gereken zorunlu başlıklar (serializer'a göre)
             'project_name', 'block', 'floor', 'unit_number', 'property_type',
             'room_count', 'gross_area_m2', 'net_area_m2', 'cash_price',
             'facade', 'status'
        }
        optional_headers = {'installment_price', 'description'}

        try:
            # UTF-8 ile dosyayı oku
            # io.TextIOWrapper kullanarak encoding belirtiyoruz
            data_set = csv_file.read().decode('utf-8-sig') # BOM'u atla
            io_string = io.StringIO(data_set)
            # DictReader kullanarak başlıklarla eşleştir
            reader = csv.DictReader(io_string, delimiter=';') # Excel genellikle ';' kullanır

            headers_from_file = set(reader.fieldnames or [])

            # --- Başlık Kontrolü ---
            missing_headers = required_headers - headers_from_file
            if missing_headers:
                 return Response(
                     {'error': f'CSV dosyasında eksik başlıklar var: {", ".join(missing_headers)}'},
                     status=status.HTTP_400_BAD_REQUEST
                 )

            unknown_headers = headers_from_file - required_headers - optional_headers
            if unknown_headers:
                 logger.warning(f"CSV dosyasında bilinmeyen başlıklar bulundu (görmezden gelinecek): {', '.join(unknown_headers)}")
            # --- Başlık Kontrolü Sonu ---


            for i, row in enumerate(reader):
                line_number = i + 2 # +1 header, +1 index 0'dan başladığı için
                property_data = {}
                try:
                    # 1. Projeyi bul
                    project_name = row.get('project_name','').strip()
                    if not project_name:
                         raise ValueError("project_name boş olamaz.")
                    try:
                        project_instance = Project.objects.get(name__iexact=project_name) # Büyük/küçük harf duyarsız ara
                        property_data['project'] = project_instance.id # Serializer'a ID gönder
                    except Project.DoesNotExist:
                        raise ValueError(f"'{project_name}' isimli proje bulunamadı.")
                    except Project.MultipleObjectsReturned:
                        raise ValueError(f"'{project_name}' ismiyle birden fazla proje bulundu. Lütfen kontrol edin.")

                    # 2. Diğer alanları işle (veri tipi dönüşümleri ve temizlik)
                    property_data['block'] = row.get('block','').strip() or project_instance.block # Blok boşsa projeden al
                    property_data['floor'] = int(row.get('floor','').strip())
                    property_data['unit_number'] = row.get('unit_number','').strip()
                    property_data['property_type'] = row.get('property_type','').strip().upper() # Seçeneklerle eşleşmesi için
                    property_data['room_count'] = row.get('room_count','').strip()
                    property_data['gross_area_m2'] = float(row.get('gross_area_m2','').strip().replace(',', '.'))
                    property_data['net_area_m2'] = float(row.get('net_area_m2','').strip().replace(',', '.'))
                    property_data['cash_price'] = float(row.get('cash_price','').strip().replace(',', '.'))
                    installment_price_str = row.get('installment_price','').strip().replace(',', '.')
                    property_data['installment_price'] = float(installment_price_str) if installment_price_str else None
                    property_data['facade'] = row.get('facade','').strip().upper() # Seçeneklerle eşleşmesi için
                    property_data['status'] = row.get('status','').strip().upper() # Seçeneklerle eşleşmesi için
                    property_data['description'] = row.get('description','').strip()

                    # 3. Serializer ile validasyon
                    serializer = PropertyCreateUpdateSerializer(data=property_data)
                    if serializer.is_valid():
                        # Geçerli ise kaydetmek üzere listeye ekle (created_by daha sonra eklenecek)
                        # .save() burada çağrılmıyor, transaction sonunda toplu yapılacak
                         created_property = serializer.save(created_by=request.user) # created_by'ı burada ekle
                         created_properties.append(created_property)
                    else:
                        # Hataları topla
                        errors.append({
                            'line': line_number,
                            'errors': serializer.errors,
                            'data': row # Hatalı satır verisi
                        })

                except (ValueError, TypeError, KeyError) as e:
                    errors.append({
                        'line': line_number,
                        'errors': f"Veri işleme hatası: {e}",
                        'data': row
                    })
                except Exception as e: # Beklenmedik diğer hatalar
                     errors.append({
                        'line': line_number,
                        'errors': f"Beklenmedik hata: {e}",
                        'data': row
                    })

            # Eğer hata varsa, transaction'ı geri al ve hataları döndür
            if errors:
                # transaction.set_rollback(True) # @transaction.atomic bunu otomatik yapar
                logger.error(f"CSV import sırasında {len(errors)} hata bulundu - User: {request.user.username}")
                return Response({
                    'error': 'CSV dosyasındaki bazı satırlarda hatalar bulundu.',
                    'details': errors
                }, status=status.HTTP_400_BAD_REQUEST)

            # Hata yoksa, transaction commit edilir (buraya gelirse otomatik commit)
            logger.info(f"{len(created_properties)} adet mülk CSV'den başarıyla eklendi - User: {request.user.username}")
            # Başarılı yanıtı, oluşturulan mülklerin özet bilgisiyle döndür
            # (İsterseniz tam PropertySerializer(many=True) ile de döndürebilirsiniz)
            return Response({
                'message': f'{len(created_properties)} mülk başarıyla eklendi.',
                 'created_count': len(created_properties),
                 # 'created_properties': PropertySerializer(created_properties, many=True).data # Opsiyonel
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
             # Genel dosya okuma veya CSV parse hatası
             logger.error(f"CSV import sırasında genel hata - User: {request.user.username} - Hata: {e}", exc_info=True)
             return Response({'error': f'CSV dosyası işlenirken hata oluştu: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # --- MEVCUT DİĞER ACTIONS ---
    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def upload_images(self, request, pk=None):
        property_instance = self.get_object() #
        images_data = request.FILES.getlist('images') #
        if not images_data: #
            return Response( #
                {'error': 'En az bir görsel yüklemelisiniz'}, #
                status=status.HTTP_400_BAD_REQUEST #
            )
        created_images = [] #
        for index, image_file in enumerate(images_data): #
            image_type = request.data.get(f'image_type_{index}', PropertyImage.ImageType.INTERIOR) #
            title = request.data.get(f'title_{index}', '') #
            image = PropertyImage.objects.create( #
                property=property_instance, #
                image=image_file, #
                image_type=image_type, #
                title=title, #
                order=index #
            )
            created_images.append(image) #
        serializer = PropertyImageSerializer(created_images, many=True) #
        return Response({ #
            'message': f'{len(created_images)} görsel başarıyla yüklendi', #
            'images': serializer.data #
        }, status=status.HTTP_201_CREATED) #

    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def upload_documents(self, request, pk=None):
        property_instance = self.get_object() #
        document_file = request.FILES.get('document') #
        if not document_file: #
            return Response( #
                {'error': 'Belge dosyası gerekli'}, #
                status=status.HTTP_400_BAD_REQUEST #
            )
        document_type = request.data.get('document_type') #
        title = request.data.get('title') #
        if not document_type or not title: #
            return Response( #
                {'error': 'Belge tipi ve başlık gerekli'}, #
                status=status.HTTP_400_BAD_REQUEST #
            ) #
        document = PropertyDocument.objects.create( #
            property=property_instance, #
            document=document_file, #
            document_type=document_type, #
            title=title, #
            uploaded_by=request.user #
        )
        serializer = PropertyDocumentSerializer(document) #
        return Response({ #
            'message': 'Belge başarıyla yüklendi', #
            'document': serializer.data #
        }, status=status.HTTP_201_CREATED) #

    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def create_payment_plan(self, request, pk=None):
        property_instance = self.get_object() #
        serializer = PaymentPlanCreateSerializer(data=request.data) #
        serializer.is_valid(raise_exception=True) #
        payment_plan = serializer.create_payment_plan(property_instance) #
        return Response({ #
            'message': 'Ödeme planı başarıyla oluşturuldu', #
            'payment_plan': PaymentPlanSerializer(payment_plan).data #
        }, status=status.HTTP_201_CREATED) #

    # bulk_create action'ı yukarıda bulk_create_from_csv ile değiştirildi.
    # Eğer eski bulk_create (JSON ile çalışan) kalacaksa:
    # @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    # def bulk_create(self, request):
    #     serializer = self.get_serializer(data=request.data, context={'request': request})
    #     serializer.is_valid(raise_exception=True)
    #     created_properties = serializer.save()
    #     return Response({
    #         'message': f'{len(created_properties)} mülk başarıyla eklendi',
    #         'properties': PropertySerializer(created_properties, many=True).data
    #     }, status=status.HTTP_201_CREATED)


class PropertyImageViewSet(viewsets.ModelViewSet):
    queryset = PropertyImage.objects.all()
    serializer_class = PropertyImageSerializer #
    permission_classes = [IsSalesManager] #
    parser_classes = [MultiPartParser, FormParser] #

    def get_queryset(self):
        property_id = self.request.query_params.get('property_id') #
        if property_id: #
            return self.queryset.filter(property_id=property_id) #
        return self.queryset #


class PropertyDocumentViewSet(viewsets.ModelViewSet):
    queryset = PropertyDocument.objects.all() #
    serializer_class = PropertyDocumentSerializer #
    permission_classes = [IsSalesManager] #
    parser_classes = [MultiPartParser, FormParser] #

    def get_queryset(self):
        property_id = self.request.query_params.get('property_id') #
        if property_id: #
            return self.queryset.filter(property_id=property_id) #
        return self.queryset #

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user) #


class PaymentPlanViewSet(viewsets.ModelViewSet):
    queryset = PaymentPlan.objects.select_related('property') #
    serializer_class = PaymentPlanSerializer #
    permission_classes = [IsAuthenticated] #

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']: #
            permission_classes = [IsSalesManager] #
        else: #
            permission_classes = [IsAuthenticated] #
        return [permission() for permission in permission_classes] #

    def get_queryset(self):
        property_id = self.request.query_params.get('property_id') #
        if property_id: #
            return self.queryset.filter(property_id=property_id, is_active=True) #
        return self.queryset.filter(is_active=True) #

    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager])
    def deactivate(self, request, pk=None):
        payment_plan = self.get_object() #
        payment_plan.is_active = False #
        payment_plan.save(update_fields=['is_active']) #
        return Response({'message': 'Ödeme planı deaktif edildi'}) #
