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
] # [cite: 3]

RENDER_EXTERNAL_HOSTNAME = config('RENDER_EXTERNAL_HOSTNAME', default=None) # [cite: 3]
if RENDER_EXTERNAL_HOSTNAME: # [cite: 3]
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME) # [cite: 3]


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
    'django_filters', # [cite: 4]
    'drf_spectacular', # [cite: 4]
    'fcm_django', # [cite: 4]
    'django_extensions', # [cite: 4]
    'storages',  # 🔥 GÜNCELLEME: django-storages eklendi # [cite: 4]

    # Local apps
    'apps.users', # [cite: 4]
    'apps.properties', # [cite: 4]
    'apps.crm', # [cite: 4]
    'apps.sales', # [cite: 4]
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
        'DIRS': [BASE_DIR / 'templates'], # [cite: 5]
        'APP_DIRS': True, # [cite: 5]
        'OPTIONS': { # [cite: 5]
            'context_processors': [ # [cite: 5]
                'django.template.context_processors.debug', # [cite: 5]
                'django.template.context_processors.request', # [cite: 5]
                'django.contrib.auth.context_processors.auth', # [cite: 5]
                'django.contrib.messages.context_processors.messages', # [cite: 6]
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
    DATABASES = { # [cite: 6]
        'default': { # [cite: 7]
            'ENGINE': 'django.db.backends.postgresql', # [cite: 7]
            'NAME': config('DB_NAME', default='realtyflow_db'), # [cite: 7]
            'USER': config('DB_USER', default='realtyflow_user'), # [cite: 7]
            'PASSWORD': config('DB_PASSWORD', default='secure_password'), # [cite: 7]
            'HOST': config('DB_HOST', default='localhost'), # [cite: 7]
            'PORT': config('DB_PORT', default='5432'), # [cite: 7]
            'OPTIONS': { # [cite: 8]
                'sslmode': config('DB_SSLMODE', default='prefer') # [cite: 8]
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

# --- STATIC FILES (Render için olduğu gibi kalıyor) --- # [cite: 9]
# Render'da 'staticfiles' klasörüne collectstatic yapılır # [cite: 9]
STATIC_URL = 'static/' # [cite: 9]
STATIC_ROOT = BASE_DIR / 'staticfiles' # [cite: 9]

# --- MEDIA FILES (Firebase'e yönlendiriliyor) --- # [cite: 9]
FIREBASE_STORAGE_BUCKET_NAME = config('FIREBASE_STORAGE_BUCKET_NAME', default='') # [cite: 9]
FIREBASE_CREDS_PATH = config('FIREBASE_CREDENTIALS_PATH', default='') # [cite: 9]

try:
    # 1. Ayarlar (env vars) ve kimlik bilgisi dosyası var mı? # [cite: 9]
    if FIREBASE_STORAGE_BUCKET_NAME and FIREBASE_CREDS_PATH and os.path.exists(FIREBASE_CREDS_PATH): #

        # 2. Gerekli paket (django-storages[firebase]) yüklü mü? #
        #    Eğer yüklü değilse, bu satır ImportError fırlatacaktır. # [cite: 11]
        import storages.backends.firebase # [cite: 12]

        # --- Ayarlar Başarılı ---
        DEFAULT_FILE_STORAGE = 'storages.backends.firebase.FirebaseStorage' # [cite: 12]

        # Firebase Admin SDK'nın bu dosyayı bulabilmesi için # [cite: 12]
        os.environ.setdefault('FIREBASE_SERVICE_ACCOUNT_KEY_FILE', FIREBASE_CREDS_PATH) # [cite: 12]

        # Firebase Storage ayarları # [cite: 12]
        FIREBASE_STORAGE_BUCKET_NAME = FIREBASE_STORAGE_BUCKET_NAME # [cite: 12]
        FIREBASE_STORAGE_MEDIA_PUBLIC = True #
        FIREBASE_STORAGE_URL_EXPIRATION = timedelta(days=365 * 10) #

        MEDIA_URL = f'https://storage.googleapis.com/{FIREBASE_STORAGE_BUCKET_NAME}/media/' #
        MEDIA_ROOT = '' # Lokal depolama kullanılmayacak #

        print(f"✅ Firebase Storage '{FIREBASE_STORAGE_BUCKET_NAME}' için yapılandırıldı.") #

    else:
        # --- Lokal Geliştirme (Ayarlar eksik) --- #
        print("⚠️ Firebase Storage ayarları bulunamadı. Lokal medya depolama kullanılıyor.") #
        DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage' #
        MEDIA_URL = 'media/' #
        MEDIA_ROOT = BASE_DIR / 'media' #

except ImportError:
    # --- Paket Hatası (Render'daki durum bu) --- #
    print("❌ HATA: 'django-storages[firebase]' paketi yüklü değil.") #
    print("⚠️ Firebase ayarları (env vars) algılandı ancak gerekli paket eksik.") #
    print("⚠️ Güvenli mod: Lokal medya depolamaya geri dönülüyor.") #
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage' #
    MEDIA_URL = 'media/' #
    MEDIA_ROOT = BASE_DIR / 'media' # [cite: 15]
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
    'PAGE_SIZE': 20, # [cite: 16]
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema', # [cite: 16]

    'COERCE_DECIMAL_TO_STRING': False, # [cite: 16]
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
    'accept-encoding', # [cite: 17]
    'authorization', # [cite: 17]
    'content-type', # [cite: 17]
    'dnt', # [cite: 17]
    'origin', # [cite: 17]
    'user-agent', # [cite: 17]
    'x-csrftoken', # [cite: 17]
    'x-requested-with', # [cite: 17]
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
# (FIREBASE_CREDENTIALS_PATH yukarıda hem Storage hem Admin için tanımlandı) # [cite: 17]
if FIREBASE_CREDS_PATH and os.path.exists(FIREBASE_CREDS_PATH): # [cite: 17]
    try:
        import firebase_admin # [cite: 18]
        from firebase_admin import credentials # [cite: 18]

        # Sadece bir kez başlatıldığından emin ol # [cite: 18]
        if not firebase_admin._apps: # [cite: 18]
            cred = credentials.Certificate(FIREBASE_CREDS_PATH) # [cite: 18]
            firebase_admin.initialize_app(cred) # [cite: 18]
            print("✅ Firebase Admin SDK başarıyla başlatıldı") # [cite: 18]
        else:
            print("ℹ️ Firebase Admin SDK zaten başlatılmış.") # [cite: 19]

    except Exception as e:
        print(f"⚠️ Firebase Admin SDK başlatma hatası: {e}") # [cite: 19]

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
    'formatters': { # [cite: 20]
        'verbose': { # [cite: 20]
            'format': '{levelname} {asctime} {module} {message}', # [cite: 20]
            'style': '{', # [cite: 20]
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler', # [cite: 20]
            'formatter': 'verbose', # [cite: 20]
        }, # [cite: 21]
    },
    'root': {
        'handlers': ['console'], # [cite: 21]
        'level': 'INFO', # [cite: 21]
    },
    'loggers': {
        'django': {
            'handlers': ['console'], # [cite: 21]
            'level': 'INFO', # [cite: 21]
            'propagate': False, # [cite: 21]
        },
        'apps': { # [cite: 22]
            'handlers': ['console'], # [cite: 22]
            'level': 'DEBUG', # [cite: 22]
            'propagate': False, # [cite: 22]
        },
    },
}
