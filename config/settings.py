# config/settings.py

from pathlib import Path
from datetime import timedelta
from decouple import config
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# ==========================================
# 🔥 ALLOWED_HOSTS - RENDER İÇİN GÜNCELLENDİ
# ==========================================
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '172.20.10.2',
    '192.168.1.102',
    '192.168.1.103',
    '192.168.1.104',
    '192.168.1.161',
    '192.168.1.106',
    '10.0.2.2',
]

RENDER_EXTERNAL_HOSTNAME = config('RENDER_EXTERNAL_HOSTNAME', default=None)
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)


# INSTALLED_APPS
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'fcm_django',
    'django_extensions',
    'storages',  # 🔥 GÜNCELLEME: django-storages eklendi
    
    # Local apps
    'apps.users',
    'apps.properties',
    'apps.crm',
    'apps.sales',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ==========================================
# DATABASE
# ==========================================
DB_ENGINE = config('DB_ENGINE', default='sqlite3')

if DB_ENGINE == 'sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='realtyflow_db'),
            'USER': config('DB_USER', default='realtyflow_user'),
            'PASSWORD': config('DB_PASSWORD', default='secure_password'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'OPTIONS': {
                'sslmode': config('DB_SSLMODE', default='prefer')
            }
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'tr-TR'
TIME_ZONE = 'Europe/Istanbul'
USE_I1N = True
USE_TZ = True

# ==========================================
# 🔥 STATIC & MEDIA FILES (RENDER HATASI İÇİN GÜNCELLENDİ)
# ==========================================

# --- STATIC FILES (Render için olduğu gibi kalıyor) ---
# Render'da 'staticfiles' klasörüne collectstatic yapılır
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# --- MEDIA FILES (Firebase'e yönlendiriliyor) ---
FIREBASE_STORAGE_BUCKET_NAME = config('FIREBASE_STORAGE_BUCKET_NAME', default='')
FIREBASE_CREDS_PATH = config('FIREBASE_CREDENTIALS_PATH', default='')

try:
    # 1. Ayarlar (env vars) ve kimlik bilgisi dosyası var mı?
    if FIREBASE_STORAGE_BUCKET_NAME and FIREBASE_CREDS_PATH and os.path.exists(FIREBASE_CREDS_PATH):
        
        # 2. Gerekli paket (django-storages[firebase]) yüklü mü?
        #    Eğer yüklü değilse, bu satır ImportError fırlatacaktır.
        import storages.backends.firebase
        
        # --- Ayarlar Başarılı ---
        DEFAULT_FILE_STORAGE = 'storages.backends.firebase.FirebaseStorage'
        
        # Firebase Admin SDK'nın bu dosyayı bulabilmesi için
        os.environ.setdefault('FIREBASE_SERVICE_ACCOUNT_KEY_FILE', FIREBASE_CREDS_PATH)
        
        # Firebase Storage ayarları
        FIREBASE_STORAGE_BUCKET_NAME = FIREBASE_STORAGE_BUCKET_NAME
        FIREBASE_STORAGE_MEDIA_PUBLIC = True
        FIREBASE_STORAGE_URL_EXPIRATION = timedelta(days=365 * 10)
        
        MEDIA_URL = f'https://storage.googleapis.com/{FIREBASE_STORAGE_BUCKET_NAME}/media/'
        MEDIA_ROOT = '' # Lokal depolama kullanılmayacak
        
        print(f"✅ Firebase Storage '{FIREBASE_STORAGE_BUCKET_NAME}' için yapılandırıldı.")
        
    else:
        # --- Lokal Geliştirme (Ayarlar eksik) ---
        print("⚠️ Firebase Storage ayarları bulunamadı. Lokal medya depolama kullanılıyor.")
        DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
        MEDIA_URL = 'media/'
        MEDIA_ROOT = BASE_DIR / 'media'

except ImportError:
    # --- Paket Hatası (Render'daki durum bu) ---
    print("❌ HATA: 'django-storages[firebase]' paketi yüklü değil.")
    print("⚠️ Firebase ayarları (env vars) algılandı ancak gerekli paket eksik.")
    print("⚠️ Güvenli mod: Lokal medya depolamaya geri dönülüyor.")
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    MEDIA_URL = 'media/'
    MEDIA_ROOT = BASE_DIR / 'media'
# 🔥 GÜNCELLEME SONU 🔥


# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================
# 🔥 REST Framework - DECIMAL AYARI EKLENDİ
# ==========================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    
    'COERCE_DECIMAL_TO_STRING': False,
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ==========================================
# 🔥 CORS SETTINGS - RENDER İÇİN ÖNEMLİ
# ==========================================
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8080',
    'http://127.0.0.1:8080',
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Firebase (FCM ve Admin SDK için)
# (FIREBASE_CREDENTIALS_PATH yukarıda hem Storage hem Admin için tanımlandı)
if FIREBASE_CREDS_PATH and os.path.exists(FIREBASE_CREDS_PATH):
    try:
        import firebase_admin
        from firebase_admin import credentials
        
        # Sadece bir kez başlatıldığından emin ol
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_CREDS_PATH)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin SDK başarıyla başlatıldı")
        else:
            print("ℹ️ Firebase Admin SDK zaten başlatılmış.")
            
    except Exception as e:
        print(f"⚠️ Firebase Admin SDK başlatma hatası: {e}")

# FCM Django
FCM_DJANGO_SETTINGS = {
    "ONE_DEVICE_PER_USER": False,
    "DELETE_INACTIVE_DEVICES": True,
}

# Spectacular (API Docs)
SPECTACULAR_SETTINGS = {
    'TITLE': 'RealtyFlow CRM API',
    'DESCRIPTION': 'Gayrimenkul CRM sistemi API dokümantasyonu',
    'VERSION': '1.0.0',
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
