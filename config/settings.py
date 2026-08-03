"""
Django settings for config project.
Full MongoDB via PyMongo.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-od)f2fmo7*(5j*^2#m9ix+gmvfjejm&y02g)h-#4ai%za026m@'
DEBUG = True
ALLOWED_HOSTS = []

# ============================================================
# INSTALLED APPS — minimal tanpa allauth, tanpa sites
# ============================================================
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'events',
    'photos',
    'users',
    'dashboard',
    'galeri',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
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
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ============================================================
# DATABASE — MongoDB only (via PyMongo)
# Django ORM masih dibutuhkan untuk auth/session internal,
# tapi kita pake SQLite in-memory ringan (tidak ada data di sini)
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ============================================================
# MONGO DB — koneksi via config/db.py
# ============================================================
MONGO_URI = os.environ.get(
    'MONGO_URI',
    'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority'
)
MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'db_tugasakhir')

# ============================================================
# AUTH BACKEND — custom MongoDB
# ============================================================
AUTHENTICATION_BACKENDS = [
    'config.auth_backend.MongoAuthBackend',
]

# ============================================================
# SESSION — file-based (tidak perlu database ORM)
# ============================================================
SESSION_ENGINE = 'django.contrib.sessions.backends.file'
SESSION_FILE_PATH = BASE_DIR / 'sessions'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# ============================================================
# PASSWORD VALIDATION (tetap dari Django)
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================================
# INTERNATIONALIZATION
# ============================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ============================================================
# STATIC & MEDIA
# ============================================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ============================================================
# CACHE — Redis (via django-redis). Server: Memurai localhost:6379.
# Catatan: hasil face-search (BlazeFace / generic) disimpan di sini
# sehingga pencarian foto yang sama tidak perlu diproses ulang.
# ============================================================
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'run_event_photo',
        'TIMEOUT': 3600,
    }
}
