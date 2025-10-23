# apps/properties/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser # <-- IsAdminUser eklendi
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
from apps.users.permissions import IsAdmin, IsSalesManager, IsSalesRep # <-- İzin sınıfları

# Özel hata sınıfı (Eğer projenizde yoksa bu şekilde tanımlayabilirsiniz)
class CsvImportError(Exception):
    def __init__(self, message, details=None):
        self.message = message
        self.details = details or []
        super().__init__(self.message)

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
    # permission_classes = [IsSalesManager] # get_permissions ile yönetiliyor
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
            permission_classes = [IsSalesManager] # IsAdmin, IsSalesManager'ı kapsar
        return [permission() for permission in permission_classes]

    # 🔥 YENİ: perform_create metodu eklendi (resimlerle proje oluşturma)
    def perform_create(self, serializer):
        project_image = self.request.FILES.get('project_image')
        site_plan_image = self.request.FILES.get('site_plan_image')
        serializer.save(
            project_image=project_image,
            site_plan_image=site_plan_image
            # created_by eklenmeli mi? Proje modelinde varsa ekleyin.
            # created_by=self.request.user
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
    ).order_by('-created_at') # Ordering burada tanımlandı
    serializer_class = PropertySerializer
    # 🔥 YENİ: Toplu yükleme için MultiPartParser ekleniyor
    parser_classes = [MultiPartParser, FormParser] # <-- Eklendi
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = {
        'status': ['exact'],
        'property_type': ['exact'],
        'room_count': ['icontains'],
        'cash_price': ['gte', 'lte'],
        'net_area_m2': ['gte', 'lte'],
        'project__id': ['exact'], # Proje ID'sine göre filtreleme
    }

    search_fields = ['project__name', 'block', 'unit_number', 'room_count', 'description']
    ordering_fields = ['created_at', 'cash_price', 'gross_area_m2', 'floor']
    # ordering = ['-created_at'] # Yukarıda queryset'e eklendi

    # Proje ID'sine göre filtreleme için get_queryset override edildi
    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project', None)
        if project_id is not None:
            queryset = queryset.filter(project__id=project_id)
        return queryset

    def get_permissions(self):
        # 🔥 YENİ: Yeni action'lar için izinler ekleniyor
        # Admin her şeyi yapabilir varsayımıyla (IsSalesManager IsAdmin'i içermiyor olabilir, ayrı kontrol daha güvenli)
        if self.action in ['create', 'update', 'partial_update', 'upload_images', 'upload_documents', 'create_payment_plan']:
             permission_classes = [IsSalesManager | IsAdmin] # SM veya Admin
        elif self.action in ['bulk_create_from_csv', 'export_sample_csv']:
            permission_classes = [IsAdmin] # Sadece Admin
        elif self.action == 'destroy':
            permission_classes = [IsAdmin] # Sadece Admin silebilir
        else: # list, retrieve, available, statistics
            permission_classes = [IsAuthenticated] # Tüm giriş yapmış kullanıcılar görebilir
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PropertyDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PropertyCreateUpdateSerializer
        # 🔥 YENİ: bulk_create_from_csv action'ı için serializer
        elif self.action == 'bulk_create_from_csv':
             # BulkPropertyCreateSerializer daha hafifse onu kullanmak daha iyi olabilir
             # return BulkPropertyCreateSerializer
             return PropertySerializer # Şimdilik bunu kullanıyoruz
        return PropertySerializer

    # create ve update metodları PropertyDetailSerializer ile yanıt vermek için override edildi
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Yanıt için detay serializer'ı kullan
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

        # Yanıt için detay serializer'ı kullan
        response_serializer = PropertyDetailSerializer(instance, context=self.get_serializer_context())
        return Response(response_serializer.data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Sadece satılabilir durumdaki mülkleri listeler."""
        available_properties = self.get_queryset().filter(
            status=Property.Status.SATILABILIR
        )
        # Mevcut filtreleri uygula (search vb.)
        filtered_qs = self.filter_queryset(available_properties)
        page = self.paginate_queryset(filtered_qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(filtered_qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Gayrimenkul istatistiklerini döndürür."""
        queryset = self.get_queryset() # Filtreleri de dikkate alabilir
        stats = {
            'total_properties': queryset.count(),
            'available': queryset.filter(status=Property.Status.SATILABILIR).count(),
            'reserved': queryset.filter(status=Property.Status.REZERVE).count(),
            'sold': queryset.filter(status=Property.Status.SATILDI).count(),
            'passive': queryset.filter(status=Property.Status.PASIF).count(),
            'by_type': queryset.values('property_type').annotate(count=Count('id')).order_by(),
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
        # 'by_type' sonucunu daha kullanışlı bir formata çevir
        stats['by_type'] = {item['property_type']: item['count'] for item in stats['by_type']}
        return Response(stats)

    # --- ÖRNEK CSV EXPORT ACTION ---
    @action(detail=False, methods=['get'], url_path='export-sample-csv', permission_classes=[IsAdmin]) # Sadece Admin
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

        # Başlık Satırı
        headers = [
            'project_name', 'block', 'floor', 'unit_number', 'property_type',
            'room_count', 'gross_area_m2', 'net_area_m2', 'cash_price',
            'installment_price', 'facade', 'status', 'description',
        ]
        writer.writerow(headers)

        # Örnek Veri Satırları
        sample_data = [
            ['RealtyFlow Towers', 'A', '5', '21', 'DAIRE', '2+1', '120.50', '95.00', '2500000.00', '2800000.00', 'GUNEY', 'SATILABILIR', 'Geniş ve ferah daire'],
            ['RealtyFlow Towers', 'A', '6', '25', 'DAIRE', '3+1', '155.00', '125.75', '3500000.00', '', 'DOGU', 'SATILABILIR', 'Deniz manzaralı'],
            ['Vadi Konakları', 'B', '1', '2', 'VILLA', '5+2', '450.00', '380.00', '12000000.00', '', 'BATI', 'SATILABILIR', 'Müstakil bahçeli lüks villa'],
        ]
        for row in sample_data:
            writer.writerow(row)

        logger.info(f"Örnek CSV şablonu indirildi - User: {request.user.username}")
        return response

    # =======================================================
    # 🔥 YENİ VE GÜNCELLENMİŞ TOPLU YÜKLEME APIView'I
    # =======================================================
    @action(detail=False, methods=['post'], url_path='bulk-create-from-csv', permission_classes=[IsAdmin]) # Sadece Admin
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
        # CSV'de olması gereken zorunlu başlıklar (serializer'a göre)
        required_headers = {
             'project_name', 'block', 'floor', 'unit_number', 'property_type',
             'room_count', 'gross_area_m2', 'net_area_m2', 'cash_price',
             'facade', 'status'
        }
        optional_headers = {'installment_price', 'description'}

        user = request.user if request.user.is_authenticated else None

        try:
            # 1. DOSYAYI OKU VE NEWLINE HATASINI ÇÖZ
            # UTF-8 ile dosyayı oku, BOM'u atla
            file_data = csv_file.read().decode('utf-8-sig')
            # io.StringIO ile bellek içi dosya oluştur
            csv_data = io.StringIO(file_data)
            # DictReader kullan (delimiter=';' Excel için)
            reader = csv.DictReader(csv_data, delimiter=';')

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

            # 3. SATIR SATIR VERİLERİ İŞLE VE VALIDASYON YAP
            for i, row in enumerate(reader):
                line_number = i + 2 # +1 header, +1 index 0'dan başladığı için
                property_data = {}
                is_valid_row = True # Satır geçerli mi kontrolü

                try:
                    # 1. Projeyi bul
                    project_name = row.get('project_name','').strip()
                    if not project_name:
                         raise ValueError("project_name boş olamaz.")
                    try:
                        project_instance = Project.objects.get(name__iexact=project_name)
                        property_data['project'] = project_instance.id
                    except Project.DoesNotExist:
                        raise ValueError(f"'{project_name}' isimli proje bulunamadı.")
                    except Project.MultipleObjectsReturned:
                        raise ValueError(f"'{project_name}' ismiyle birden fazla proje bulundu.")

                    # 2. Diğer alanları işle (veri tipi dönüşümleri ve temizlik)
                    property_data['block'] = row.get('block','').strip() or project_instance.block or '' # Blok boşsa projeden al, o da boşsa boş string
                    property_data['floor'] = int(row.get('floor','').strip() or 0)
                    property_data['unit_number'] = row.get('unit_number','').strip()
                    property_data['property_type'] = row.get('property_type','').strip().upper()
                    property_data['room_count'] = row.get('room_count','').strip()
                    property_data['gross_area_m2'] = float(row.get('gross_area_m2','').strip().replace(',', '.') or 0.0)
                    property_data['net_area_m2'] = float(row.get('net_area_m2','').strip().replace(',', '.') or 0.0)
                    property_data['cash_price'] = float(row.get('cash_price','').strip().replace(',', '.') or 0.0)
                    installment_price_str = row.get('installment_price','').strip().replace(',', '.')
                    property_data['installment_price'] = float(installment_price_str) if installment_price_str else None
                    property_data['facade'] = row.get('facade','').strip().upper() or 'GUNEY' # Varsayılan
                    property_data['status'] = row.get('status','').strip().upper() or 'SATILABILIR' # Varsayılan
                    property_data['description'] = row.get('description','').strip()

                    # Alanların geçerliliğini kontrol et (örnek)
                    if not property_data['unit_number']:
                        raise ValueError("unit_number boş olamaz.")
                    if property_data['cash_price'] <= 0:
                        raise ValueError("cash_price pozitif olmalıdır.")
                    if property_data['status'] not in [s[0] for s in Property.STATUS_CHOICES]:
                        raise ValueError(f"Geçersiz durum değeri: '{property_data['status']}'.")
                    if property_data['facade'] not in [f[0] for f in Property.FACADE_CHOICES]:
                        raise ValueError(f"Geçersiz cephe değeri: '{property_data['facade']}'.")

                    # 3. Serializer ile validasyon (burada daha kapsamlı kontrol yapılır)
                    serializer = PropertyCreateUpdateSerializer(data=property_data)
                    if serializer.is_valid():
                        # Geçerli ise kaydetmek üzere listeye ekle
                         created_property = serializer.save(created_by=request.user)
                         created_properties.append(created_property)
                    else:
                        # Serializer hatalarını topla
                        errors.append({
                            'line': line_number,
                            'errors': serializer.errors,
                            'data': row # Hatalı satır verisi
                        })
                        is_valid_row = False # Bu satırda hata var

                except (ValueError, TypeError, KeyError) as e:
                    errors.append({
                        'line': line_number,
                        'errors': f"Veri işleme hatası: {e}",
                        'data': row
                    })
                    is_valid_row = False
                except Exception as e: # Beklenmedik diğer hatalar
                     errors.append({
                        'line': line_number,
                        'errors': f"Beklenmedik hata: {e}",
                        'data': row
                    })
                     is_valid_row = False

            # 4. HATA RAPORU
            if errors:
                # transaction.set_rollback(True) # @transaction.atomic bunu otomatik yapar
                logger.error(f"CSV import sırasında {len(errors)} hata bulundu - User: {request.user.username}")
                return Response({
                    'error': f"CSV dosyasındaki {len(errors)} satırda hatalar bulundu. İşlem geri alındı.",
                    'details': errors
                }, status=status.HTTP_400_BAD_REQUEST)

            # 5. BAŞARILI YANIT
            logger.info(f"{len(created_properties)} adet mülk CSV'den başarıyla eklendi - User: {request.user.username}")
            return Response({
                'message': f'{len(created_properties)} mülk başarıyla eklendi.',
                 'created_count': len(created_properties),
                 # 'created_properties': PropertySerializer(created_properties, many=True).data # Opsiyonel
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
             # Genel dosya okuma veya CSV parse hatası
             logger.error(f"CSV import sırasında genel hata - User: {request.user.username} - Hata: {e}", exc_info=True)
             return Response({'error': f'CSV dosyası işlenirken hata oluştu: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # =======================================================
    # 🔥 GÜNCELLEME SONU
    # =======================================================


    # --- MEVCUT DİĞER ACTIONS ---
    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager | IsAdmin]) # İzin güncellendi
    def upload_images(self, request, pk=None):
        property_instance = self.get_object()
        images_data = request.FILES.getlist('images')
        if not images_data:
            return Response(
                {'error': 'En az bir görsel yüklemelisiniz'},
                status=status.HTTP_400_BAD_REQUEST
            )
        created_images = []
        # Mevcut en yüksek order değerini al
        last_order = PropertyImage.objects.filter(property=property_instance).aggregate(Max('order'))['order__max'] or -1

        for index, image_file in enumerate(images_data):
            # Form-data içinde image_type_{index} ve title_{index} bekleniyor
            image_type = request.data.get(f'image_type_{index}', PropertyImage.ImageType.INTERIOR)
            title = request.data.get(f'title_{index}', '')
            image = PropertyImage.objects.create(
                property=property_instance,
                image=image_file,
                image_type=image_type,
                title=title,
                order=last_order + 1 + index, # Sıralamayı devam ettir
                uploaded_by=request.user # Yükleyen kullanıcı
            )
            created_images.append(image)
        serializer = PropertyImageSerializer(created_images, many=True)
        return Response({
            'message': f'{len(created_images)} görsel başarıyla yüklendi',
            'images': serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager | IsAdmin]) # İzin güncellendi
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

    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager | IsAdmin]) # İzin güncellendi
    def create_payment_plan(self, request, pk=None):
        property_instance = self.get_object()
        # PaymentPlanCreateSerializer'ı kullanıyoruz
        serializer = PaymentPlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Serializer içindeki create_payment_plan metodunu çağır
        payment_plan = serializer.create_payment_plan(property_instance)
        return Response({
            'message': 'Ödeme planı başarıyla oluşturuldu',
            'payment_plan': PaymentPlanSerializer(payment_plan).data # Yanıt için ana serializer
        }, status=status.HTTP_201_CREATED)


class PropertyImageViewSet(viewsets.ModelViewSet):
    queryset = PropertyImage.objects.all().order_by('order') # order_by eklendi
    serializer_class = PropertyImageSerializer
    permission_classes = [IsSalesManager | IsAdmin] # İzin güncellendi
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        property_id = self.request.query_params.get('property_id')
        if property_id:
            return self.queryset.filter(property_id=property_id)
        # property_id olmadan tümünü getirmek yerine boş döndürmek daha güvenli olabilir
        # return PropertyImage.objects.none()
        return self.queryset # Veya tümünü döndür

    # perform_create eklenmeli mi? Belki upload_images action'ı yeterlidir.
    # def perform_create(self, serializer):
    #     serializer.save(uploaded_by=self.request.user)


class PropertyDocumentViewSet(viewsets.ModelViewSet):
    queryset = PropertyDocument.objects.all().order_by('-uploaded_at') # order_by eklendi
    serializer_class = PropertyDocumentSerializer
    permission_classes = [IsSalesManager | IsAdmin] # İzin güncellendi
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        property_id = self.request.query_params.get('property_id')
        if property_id:
            return self.queryset.filter(property_id=property_id)
        # return PropertyDocument.objects.none() # Daha güvenli
        return self.queryset # Veya tümünü döndür

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class PaymentPlanViewSet(viewsets.ModelViewSet):
    queryset = PaymentPlan.objects.select_related('property').filter(is_active=True) # Sadece aktif olanlar
    serializer_class = PaymentPlanSerializer
    # permission_classes = [IsAuthenticated] # get_permissions ile yönetiliyor

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'deactivate']:
            permission_classes = [IsSalesManager | IsAdmin] # İzin güncellendi
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        property_id = self.request.query_params.get('property_id')
        if property_id:
            return queryset.filter(property_id=property_id)
        # property_id olmadan tüm planları listelemek yerine boş döndürebiliriz
        # return PaymentPlan.objects.none()
        return queryset # Veya tüm aktif planları döndür

    # Yeni plan oluştururken create_payment_plan action'ı mı kullanılmalı?
    # Eğer bu ViewSet üzerinden de oluşturulacaksa:
    # def perform_create(self, serializer):
    #     property_id = self.request.data.get('property')
    #     if not property_id:
    #         raise serializers.ValidationError("Property ID gereklidir.")
    #     try:
    #         property_instance = Property.objects.get(pk=property_id)
    #     except Property.DoesNotExist:
    #         raise serializers.ValidationError("Geçersiz Property ID.")
    #     serializer.save(property=property_instance)


    @action(detail=True, methods=['post'], permission_classes=[IsSalesManager | IsAdmin]) # İzin güncellendi
    def deactivate(self, request, pk=None):
        """Ödeme planını pasif hale getirir."""
        payment_plan = self.get_object()
        payment_plan.is_active = False
        payment_plan.save(update_fields=['is_active'])
        logger.info(f"Payment plan {pk} deactivated by user {request.user.username}")
        return Response({'message': 'Ödeme planı başarıyla deaktif edildi.'}, status=status.HTTP_200_OK)
