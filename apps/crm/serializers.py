# apps/crm/serializers.py

from rest_framework import serializers #
from django.utils import timezone #
from .models import Customer, Activity, Appointment, Note #
from apps.users.serializers import UserSerializer #


class ActivitySerializer(serializers.ModelSerializer): #
    """Aktivite serializeri""" #

    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True) #
    outcome_score_display = serializers.CharField(source='get_outcome_score_display', read_only=True) #
    # **** YENİ ALAN ****
    sub_type_display = serializers.CharField(source='get_sub_type_display', read_only=True, allow_null=True)
    # **** YENİ ALAN SONU ****
    created_by_name = serializers.SerializerMethodField() #
    customer_name = serializers.CharField(source='customer.full_name', read_only=True) #

    class Meta: #
        model = Activity # [cite: 2222]
        fields = [ #
            'id', 'customer', 'customer_name', 'activity_type', 'activity_type_display',
            # **** YENİ ALAN EKLENDİ ****
            'sub_type', 'sub_type_display',
            # **** YENİ ALAN SONU ****
            'notes', 'outcome_score', 'outcome_score_display', #
            'next_follow_up_date', 'created_by', 'created_by_name', 'created_at' # [cite: 2223]
        ] #
        read_only_fields = ['id', 'created_by', 'created_at'] #

    def get_created_by_name(self, obj): #
        """created_by_name güvenli döndür""" #
        if obj.created_by is None: #
            return None #
        full_name = obj.created_by.get_full_name() #
        return full_name if full_name.strip() else None # [cite: 2224]


class ActivityCreateSerializer(serializers.ModelSerializer): #
    """Aktivite oluşturma serializeri""" #

    class Meta: #
        model = Activity #
        fields = [ #
            'customer', 'activity_type', 'notes', 'outcome_score', 'next_follow_up_date' #
        ] #
        # **** YENİ: sub_type backend'de set edileceği için read_only ****
        # read_only_fields = ['sub_type'] # <-- Bu satırı kaldırıyoruz, create içinde set edeceğiz
        # **** YENİ SONU ****

    def validate(self, attrs): #
        if attrs.get('next_follow_up_date'): #
            if attrs['next_follow_up_date'] < timezone.now(): #
                raise serializers.ValidationError({ #
                    'next_follow_up_date': 'Takip tarihi geçmişte olamaz' #
                }) #
        return attrs # [cite: 2226]

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # YENİ EKLENEN KOD BAŞLANGICI
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def create(self, validated_data):
        customer = validated_data.get('customer')
        activity_type = validated_data.get('activity_type')
        sub_type_to_set = None # Başlangıçta alt tür yok

        # Eğer aktivite tipi 'Yüz Yüze Görüşme' ise kontrol yap
        if activity_type == Activity.ActivityType.GORUSME and customer:
            # Müşterinin daha önce 'Yüz Yüze Görüşme' aktivitesi var mı?
            has_previous_meeting = Activity.objects.filter(
                customer=customer,
                activity_type=Activity.ActivityType.GORUSME
            ).exists()

            if has_previous_meeting:
                sub_type_to_set = Activity.SubType.ARA_GELEN # Ara gelen
            else:
                sub_type_to_set = Activity.SubType.ILK_GELEN # İlk gelen

        # validated_data içine hesaplanan alt türü ekle (veya null bırak)
        validated_data['sub_type'] = sub_type_to_set

        # Normal create işlemini çağır
        return super().create(validated_data)
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # YENİ EKLENEN KOD SONU
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def to_representation(self, instance): #
        """Create sonrası tam veriyi döndür""" #
        return ActivitySerializer(instance, context=self.context).data #


# Diğer Serializer'lar (AppointmentSerializer, NoteSerializer, CustomerSerializer vb.) olduğu gibi kalır...
class AppointmentSerializer(serializers.ModelSerializer): #
    """Randevu serializeri"""

    status_display = serializers.CharField(source='get_status_display', read_only=True) #
    customer_name = serializers.CharField(source='customer.full_name', read_only=True) #
    customer_phone = serializers.CharField(source='customer.phone_number', read_only=True) #
    sales_rep_name = serializers.CharField(source='sales_rep.get_full_name', read_only=True) #
    is_upcoming = serializers.BooleanField(read_only=True) #
    is_today = serializers.BooleanField(read_only=True) # [cite: 2227]
    time_until = serializers.SerializerMethodField() #

    class Meta: #
        model = Appointment #
        fields = [ #
            'id', 'customer', 'customer_name', 'customer_phone', #
            'sales_rep', 'sales_rep_name', 'appointment_date', #
            'location', 'status', 'status_display', 'notes', #
            'reminder_sent', 'is_upcoming', 'is_today', 'time_until', #
            'created_at', 'updated_at' # [cite: 2228]
        ] #
        read_only_fields = ['id', 'reminder_sent', 'created_at', 'updated_at'] #

    def get_time_until(self, obj): #
        return obj.time_until_appointment() #


class AppointmentCreateSerializer(serializers.ModelSerializer): #
    """Randevu oluşturma serializeri"""

    class Meta: #
        model = Appointment #
        fields = ['customer', 'sales_rep', 'appointment_date', 'location', 'notes'] #

    def validate_appointment_date(self, value): #
        if value < timezone.now(): # [cite: 2229]
            raise serializers.ValidationError('Randevu tarihi geçmişte olamaz') #
        return value #

    def validate(self, attrs): #
        sales_rep = attrs['sales_rep'] #
        appointment_date = attrs['appointment_date'] #

        start_time = appointment_date - timezone.timedelta(minutes=30) #
        end_time = appointment_date + timezone.timedelta(minutes=30) #

        overlapping = Appointment.objects.filter( # [cite: 2230]
            sales_rep=sales_rep, #
            appointment_date__range=(start_time, end_time), #
            status=Appointment.Status.PLANLANDI #
        ) #

        if self.instance: #
            overlapping = overlapping.exclude(id=self.instance.id) #

        if overlapping.exists(): #
            raise serializers.ValidationError({ # [cite: 2231]
                'appointment_date': 'Bu saatte zaten bir randevunuz var' #
            }) #

        return attrs #


class NoteSerializer(serializers.ModelSerializer): #
    """Not serializeri"""

    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True) #

    class Meta: #
        model = Note #
        fields = ['id', 'customer', 'content', 'is_important', 'created_by', 'created_by_name', 'created_at'] #
        read_only_fields = ['id', 'created_by', 'created_at'] # [cite: 2232]


class CustomerSerializer(serializers.ModelSerializer): #
    """Müşteri liste serializeri"""

    source_display = serializers.CharField(source='get_source_display', read_only=True) #
    assigned_to_name = serializers.SerializerMethodField() #
    created_by_name = serializers.SerializerMethodField() #

    latest_activity = serializers.SerializerMethodField() #
    win_probability = serializers.IntegerField(source='get_win_probability', read_only=True) #
    has_appointment_today = serializers.BooleanField(read_only=True) #

    activities_count = serializers.IntegerField(source='activities.count', read_only=True) #
    appointments_count = serializers.IntegerField(source='appointments.count', read_only=True) #

    budget_min = serializers.DecimalField( #
        max_digits=15, #
        decimal_places=2, # [cite: 2233]
        coerce_to_string=False, #
        required=False, #
        allow_null=True, #
        default=None #
    )

    budget_max = serializers.DecimalField( #
        max_digits=15, #
        decimal_places=2, #
        coerce_to_string=False, #
        required=False, #
        allow_null=True, #
        default=None # [cite: 2234]
    )

    class Meta: #
        model = Customer #
        fields = [ #
            'id', 'full_name', 'phone_number', 'email', #
            'assigned_to', 'assigned_to_name', 'source', 'source_display', #
            'interested_in', 'budget_min', 'budget_max', 'notes', #
            'created_by', 'created_by_name', 'created_at', 'updated_at', # [cite: 2235]
            'latest_activity', 'win_probability', 'has_appointment_today', #
            'activities_count', 'appointments_count' #
        ] #
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at'] #

    def get_assigned_to_name(self, obj): #
        """assigned_to_name güvenli döndür""" #
        if obj.assigned_to is None: #
            return None #
        full_name = obj.assigned_to.get_full_name() # [cite: 2236]
        return full_name if full_name.strip() else None #

    def get_created_by_name(self, obj): #
        """created_by_name güvenli döndür""" #
        if obj.created_by is None: #
            return None #
        full_name = obj.created_by.get_full_name() #
        return full_name if full_name.strip() else None #

    def get_latest_activity(self, obj): #
        latest = obj.get_latest_activity() # [cite: 2237]
        if latest: #
            return { #
                'type': latest.get_activity_type_display(), #
                'date': latest.created_at, #
                'outcome_score': latest.outcome_score #
            } #
        return None # [cite: 2238]

    def to_representation(self, instance): #
        """Decimal değerleri float'a çevir""" #
        data = super().to_representation(instance) #

        # Decimal to float conversion
        if data.get('budget_min') is not None: #
            data['budget_min'] = float(data['budget_min']) #

        if data.get('budget_max') is not None: #
            data['budget_max'] = float(data['budget_max']) # [cite: 2239]

        return data #


class CustomerDetailSerializer(serializers.ModelSerializer): #
    """Müşteri detay serializeri"""

    source_display = serializers.CharField(source='get_source_display', read_only=True) #
    assigned_to_name = serializers.SerializerMethodField() #
    created_by_name = serializers.SerializerMethodField() #

    activities = ActivitySerializer(many=True, read_only=True) #
    appointments = AppointmentSerializer(many=True, read_only=True) #
    extra_notes = NoteSerializer(many=True, read_only=True) #

    win_probability = serializers.IntegerField(source='get_win_probability', read_only=True) #

    budget_min = serializers.DecimalField( #
        max_digits=15, #
        decimal_places=2, # [cite: 2240]
        coerce_to_string=False, #
        required=False, #
        allow_null=True, #
        default=None #
    )

    budget_max = serializers.DecimalField( #
        max_digits=15, #
        decimal_places=2, #
        coerce_to_string=False, #
        required=False, #
        allow_null=True, #
        default=None # [cite: 2241]
    )

    class Meta: #
        model = Customer #
        fields = [ #
            'id', 'full_name', 'phone_number', 'email', #
            'assigned_to', 'assigned_to_name', 'source', 'source_display', #
            'interested_in', 'budget_min', 'budget_max', 'notes', #
            'created_by', 'created_by_name', 'created_at', 'updated_at', # [cite: 2242]
            'activities', 'appointments', 'extra_notes', 'win_probability' #
        ] #
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at'] #

    def get_assigned_to_name(self, obj): #
        """assigned_to_name güvenli döndür""" #
        if obj.assigned_to is None: #
            return None #
        full_name = obj.assigned_to.get_full_name() #
        return full_name if full_name.strip() else None # [cite: 2243]

    def get_created_by_name(self, obj): #
        """created_by_name güvenli döndür""" #
        if obj.created_by is None: #
            return None #
        full_name = obj.created_by.get_full_name() #
        return full_name if full_name.strip() else None #

    def to_representation(self, instance): #
        """Decimal değerleri float'a çevir""" #
        data = super().to_representation(instance) # [cite: 2244]

        # Decimal to float conversion
        if data.get('budget_min') is not None: #
            data['budget_min'] = float(data['budget_min']) #

        if data.get('budget_max') is not None: #
            data['budget_max'] = float(data['budget_max']) #

        return data #


class CustomerCreateSerializer(serializers.ModelSerializer): #
    """Müşteri oluşturma serializeri"""

    budget_min = serializers.DecimalField( # [cite: 2245]
        max_digits=15, #
        decimal_places=2, #
        coerce_to_string=False, #
        required=False, #
        allow_null=True, #
        default=None #
    )

    budget_max = serializers.DecimalField( #
        max_digits=15, #
        decimal_places=2, #
        coerce_to_string=False, #
        required=False, # [cite: 2246]
        allow_null=True, #
        default=None #
    )

    class Meta: #
        model = Customer #
        fields = [ #
            'full_name', 'phone_number', 'email', 'assigned_to', #
            'source', 'interested_in', 'budget_min', 'budget_max', 'notes' #
        ] #

    def validate_phone_number(self, value): # [cite: 2247]
        if Customer.objects.filter(phone_number=value).exists(): #
            raise serializers.ValidationError('Bu telefon numarası zaten kayıtlı') #
        return value #

    def validate(self, attrs): #
        budget_min = attrs.get('budget_min') #
        budget_max = attrs.get('budget_max') #

        if budget_min is not None and budget_max is not None: #
            if budget_min > budget_max: # [cite: 2248]
                raise serializers.ValidationError({ #
                    'budget_max': 'Maksimum bütçe, minimum bütçeden küçük olamaz' #
                }) #

        return attrs #

    def to_representation(self, instance): #
        """Create sonrası tam müşteri bilgilerini döndür""" #
        return CustomerSerializer(instance, context=self.context).data # [cite: 2249]


class CustomerUpdateSerializer(serializers.ModelSerializer): #
    """Müşteri güncelleme serializeri"""

    budget_min = serializers.DecimalField( #
        max_digits=15, #
        decimal_places=2, # [cite: 2250]
        coerce_to_string=False, #
        required=False, #
        allow_null=True, #
        default=None #
    )

    budget_max = serializers.DecimalField( #
        max_digits=15, #
        decimal_places=2, #
        coerce_to_string=False, #
        required=False, #
        allow_null=True, #
        default=None #
    )

    class Meta: #
        model = Customer #
        fields = [ #
            'full_name', 'phone_number', 'email', 'assigned_to', #
            'source', 'interested_in', 'budget_min', 'budget_max', 'notes' # [cite: 2251]
        ] #

    def validate_phone_number(self, value): #
        if Customer.objects.filter(phone_number=value).exclude(id=self.instance.id).exists(): #
            raise serializers.ValidationError('Bu telefon numarası zaten kayıtlı') #
        return value #

    def validate(self, attrs): #
        budget_min = attrs.get('budget_min') #
        budget_max = attrs.get('budget_max') #

        if budget_min is not None and budget_max is not None: # [cite: 2252]
            if budget_min > budget_max: #
                raise serializers.ValidationError({ #
                    'budget_max': 'Maksimum bütçe, minimum bütçeden küçük olamaz' #
                }) #

        return attrs #

    def to_representation(self, instance): # [cite: 2253]
        """Update sonrası tam müşteri bilgilerini döndür""" #
        return CustomerSerializer(instance, context=self.context).data #


class CustomerAssignSerializer(serializers.Serializer): #
    """Müşteri atama serializeri"""

    customer_ids = serializers.ListField( #
        child=serializers.IntegerField(), #
        required=True, #
        help_text='Atanacak müşteri ID listesi' #
    )

    sales_rep_id = serializers.IntegerField( #
        required=True, #
        help_text='Satış temsilcisi ID' # [cite: 2254]
    )

    def validate_sales_rep_id(self, value): #
        from apps.users.models import User #
        try: #
            user = User.objects.get(id=value) #
            if user.role != User.Role.SATIS_TEMSILCISI: #
                raise serializers.ValidationError('Seçilen kullanıcı satış temsilcisi değil') #
        except User.DoesNotExist: #
            raise serializers.ValidationError('Satış temsilcisi bulunamadı') # [cite: 2255]
        return value #

# ====================================================================
# 🔥 YENİ: Müşteri Zaman Tüneli için Serializer #
# ====================================================================
class TimelineEventSerializer(serializers.Serializer): #
    """
    Zaman tüneli olaylarını serileştirmek için genel bir serializer. # [cite: 2256]
    Gelen verinin tipine ('activity' veya 'appointment') göre ilgili #
    serializer'ı (ActivitySerializer veya AppointmentSerializer) çağırır. #
    """ # [cite: 2257]
    type = serializers.CharField() #
    date = serializers.DateTimeField() #
    data = serializers.SerializerMethodField() #

    def get_data(self, obj): #
        """
        Gelen objenin tipine göre doğru serializer'ı seç ve veriyi serileştir. # [cite: 2258]
        """ #
        event_type = obj.get('type') #
        event_data = obj.get('data') #

        if event_type == 'activity': #
            return ActivitySerializer(event_data, context=self.context).data #
        elif event_type == 'appointment': #
            return AppointmentSerializer(event_data, context=self.context).data #

        return None #
