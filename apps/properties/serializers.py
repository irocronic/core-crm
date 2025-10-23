# apps/properties/serializers.py

from rest_framework import serializers
from decimal import Decimal
from .models import Property, PropertyImage, PropertyDocument, PaymentPlan, Project


class ProjectSerializer(serializers.ModelSerializer):
    """Proje serializeri"""
    property_count = serializers.IntegerField(read_only=True) #
    available_count = serializers.IntegerField(read_only=True) #

    class Meta:
        model = Project #
        fields = [ #
            'id', 'name', 'location', 'description', 'island', 'parcel', 'block', #
            'property_count', 'available_count', 'project_image', 'site_plan_image' #
        ]


class PropertyImageSerializer(serializers.ModelSerializer):
    """Gayrimenkul görsel serializeri"""

    class Meta:
        model = PropertyImage #
        fields = ['id', 'image', 'image_type', 'title', 'order', 'uploaded_at'] #
        read_only_fields = ['id', 'uploaded_at'] #


class PropertyDocumentSerializer(serializers.ModelSerializer):
    """Gayrimenkul belge serializeri"""

    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True) #

    class Meta:
        model = PropertyDocument #
        fields = ['id', 'document', 'document_type', 'title', 'uploaded_by', 'uploaded_by_name', 'uploaded_at'] #
        read_only_fields = ['id', 'uploaded_by', 'uploaded_at'] #


class PaymentPlanSerializer(serializers.ModelSerializer):
    """Ödeme planı serializeri"""

    details_display = serializers.CharField(source='get_details_display', read_only=True) #

    class Meta:
        model = PaymentPlan #
        fields = ['id', 'plan_type', 'name', 'details', 'details_display', 'is_active', 'created_at'] #
        read_only_fields = ['id', 'created_at'] #


class PaymentPlanCreateSerializer(serializers.Serializer):
    """Ödeme planı oluşturma sihirbazı serializeri"""

    plan_type = serializers.ChoiceField(choices=PaymentPlan.PlanType.choices) #
    name = serializers.CharField(max_length=255, required=False) #

    # Vadeli plan için gerekli alanlar
    down_payment_percent = serializers.DecimalField( #
        max_digits=5, #
        decimal_places=2, #
        required=False, #
        min_value=Decimal('0'), #
        max_value=Decimal('100') #
    )
    installment_count = serializers.IntegerField(required=False, min_value=1) #
    interest_rate = serializers.DecimalField( #
        max_digits=5, #
        decimal_places=2, #
        required=False, #
        min_value=Decimal('0'), #
        default=Decimal('0') #
    )

    def validate(self, attrs):
        if attrs['plan_type'] == PaymentPlan.PlanType.VADELI: #
            if not attrs.get('down_payment_percent'): #
                raise serializers.ValidationError({ #
                    'down_payment_percent': 'Vadeli plan için peşinat yüzdesi gereklidir' #
                })
            if not attrs.get('installment_count'): #
                raise serializers.ValidationError({ #
                    'installment_count': 'Vadeli plan için taksit sayısı gereklidir' #
                }) #
        return attrs #

    def create_payment_plan(self, property_instance):
        """Ödeme planını hesapla ve oluştur"""
        plan_type = self.validated_data['plan_type'] #

        if plan_type == PaymentPlan.PlanType.PESIN: #
            details = { #
                 'cash_price': float(property_instance.cash_price) #
            }
            name = self.validated_data.get('name', 'Peşin Ödeme') #

        else:  # VADELI
            installment_price = float(property_instance.installment_price or property_instance.cash_price) #
            down_payment_percent = float(self.validated_data['down_payment_percent']) #
            installment_count = self.validated_data['installment_count'] #
            interest_rate = float(self.validated_data.get('interest_rate', 0)) #

            # Hesaplamalar
            down_payment_amount = installment_price * (down_payment_percent / 100) #
            remaining_amount = installment_price - down_payment_amount #

            # Vade farkı varsa hesapla
            if interest_rate > 0: #
                total_with_interest = remaining_amount * (1 + interest_rate / 100) #
                monthly_installment = total_with_interest / installment_count #
            else: #
                monthly_installment = remaining_amount / installment_count #

            details = { #
                'installment_price': installment_price, #
                'down_payment_percent': down_payment_percent, #
                'down_payment_amount': round(down_payment_amount, 2), #
                'installment_count': installment_count, #
                 'interest_rate': interest_rate, #
                'remaining_amount': round(remaining_amount, 2), #
                'monthly_installment': round(monthly_installment, 2), #
            }

            name = self.validated_data.get( #
                'name', #
                 f"%{int(down_payment_percent)} Peşin, {installment_count} Ay Vade" #
            )

        payment_plan = PaymentPlan.objects.create( #
            property=property_instance, #
            plan_type=plan_type, #
            name=name, #
            details=details #
        ) #

        return payment_plan #


class PropertySerializer(serializers.ModelSerializer):
    """Gayrimenkul liste serializeri"""

    project = ProjectSerializer(read_only=True) #

    property_type_display = serializers.CharField(source='get_property_type_display', read_only=True) #
    status_display = serializers.CharField(source='get_status_display', read_only=True) #
    facade_display = serializers.CharField(source='get_facade_display', read_only=True) #
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True) #

    # İlk görsel
    thumbnail = serializers.SerializerMethodField() #

    # Ödeme planı sayısı
    payment_plans_count = serializers.IntegerField( #
        source='payment_plans.count', #
        read_only=True #
    )

    class Meta:
        model = Property #
        fields = [ #
            'id', #
            'project', #
            'block', 'floor', #
             'unit_number', 'facade', 'facade_display', 'property_type', #
            'property_type_display', 'room_count', 'gross_area_m2', #
            'net_area_m2', 'cash_price', 'installment_price', #
            'status', 'status_display', 'description', #
            'created_by', 'created_by_name', 'created_at', 'updated_at', #
            'thumbnail', 'payment_plans_count' #
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at'] #

    def get_thumbnail(self, obj): #
        """
        Firebase Storage zaten tam URL döndürdüğü için
        'request.build_absolute_uri' kaldırıldı.
        """
        first_image = obj.images.first() #
        if first_image and first_image.image: #
            # .url özelliği artık tam Firebase URL'sini içerecek
            return first_image.image.url #
        return None #


class PropertyDetailSerializer(serializers.ModelSerializer):
    """Gayrimenkul detay serializeri"""

    project = ProjectSerializer(read_only=True) #
    property_type_display = serializers.CharField(source='get_property_type_display', read_only=True) #
    status_display = serializers.CharField(source='get_status_display', read_only=True) #
    facade_display = serializers.CharField(source='get_facade_display', read_only=True) #
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True) #

    images = PropertyImageSerializer(many=True, read_only=True) #
    documents = PropertyDocumentSerializer(many=True, read_only=True) #
    payment_plans = PaymentPlanSerializer(many=True, read_only=True) #

    class Meta:
        model = Property #
        fields = [ #
            'id', 'project', 'block', 'floor', #
            'unit_number', 'facade', 'facade_display', 'property_type', #
             'property_type_display', 'room_count', 'gross_area_m2', #
            'net_area_m2', 'cash_price', 'installment_price', #
            'status', 'status_display', 'description', #
            'created_by', 'created_by_name', 'created_at', 'updated_at', #
            'images', 'documents', 'payment_plans' #
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at'] #


class PropertyCreateUpdateSerializer(serializers.ModelSerializer):
    """Gayrimenkul oluşturma ve güncelleme serializeri""" #

    # 🔥 YENİ: Proje ID'sini yazılabilir hale getiriyoruz (ForeignKey için)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())

    class Meta:
        model = Property #
        fields = [ #
            'project', # 'project_name' yerine 'project' ID'si kullanılacak
            'block', 'floor', #
            'unit_number', 'facade', 'property_type', 'room_count', #
            'gross_area_m2', 'net_area_m2', 'cash_price', #
            'installment_price', 'status', 'description' #
        ] #

    def validate(self, attrs):
        # Vadeli fiyat kontrolü (Değişiklik yok)
        if attrs.get('installment_price') and attrs.get('cash_price'): #
            if attrs['installment_price'] < attrs['cash_price']: #
                raise serializers.ValidationError({ #
                    'installment_price': 'Vadeli fiyat, peşin fiyattan düşük olamaz' #
                })
        # Alan kontrolü (Değişiklik yok)
        if attrs.get('net_area_m2') and attrs.get('gross_area_m2'): #
             if attrs['net_area_m2'] > attrs['gross_area_m2']: #
                raise serializers.ValidationError({ #
                    'net_area_m2': 'Net alan, brüt alandan büyük olamaz' #
                })
        return attrs #


class BulkPropertyCreateSerializer(serializers.Serializer):
    """Toplu gayrimenkul ekleme serializeri (Excel import için)"""

    # Bu serializer direkt listeyi alır, PropertyCreateUpdateSerializer'ı kullanır
    properties = PropertyCreateUpdateSerializer(many=True) #

    def create(self, validated_data):
        properties_data = validated_data['properties'] #
        created_properties = [] #
        user = self.context['request'].user # İstekten kullanıcıyı al

        for property_data in properties_data: #
            property_data['created_by'] = user # Her birine kullanıcıyı ekle
            property_instance = Property.objects.create(**property_data) #
            created_properties.append(property_instance) #

        return created_properties #


class PropertyFilterSerializer(serializers.Serializer):
    """Gayrimenkul filtreleme için yardımcı serializer"""

    project_name = serializers.CharField(required=False) #
    property_type = serializers.ChoiceField(choices=Property.PropertyType.choices, required=False) #
    room_count = serializers.CharField(required=False) #
    status = serializers.ChoiceField(choices=Property.Status.choices, required=False) #
    min_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=False) #
    max_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=False) #
    min_area = serializers.DecimalField(max_digits=10, decimal_places=2, required=False) #
    max_area = serializers.DecimalField(max_digits=10, decimal_places=2, required=False) #

    block = serializers.CharField(required=False) #
    floor = serializers.IntegerField(required=False) #
