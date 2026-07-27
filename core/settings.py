import os
from pathlib import Path

# 1. Setting Jalur Utama Proyek
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Keamanan (Standar Django)
SECRET_KEY = 'django-insecure-mutiara-tugas-akhir-running-photo'
DEBUG = True
ALLOWED_HOSTS = []

# 3. DAFTAR APLIKASI
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Aplikasi Tugas Akhir Mutiara
    'photos', 
    'django_extensions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',  
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'core.wsgi.application'

# 4. SETTING DATABASE (Mongodb)
DATABASES = {
    'default': {
        'ENGINE': 'djongo',
        'NAME': 'db_tugasakhir',
        'CLIENT': {
            'host': 'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority',
        }
    }
}

# 5. Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# 6. Setting Folder Media & Static buat Foto Pelari
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

SESSION_ENGINE = 'django.contrib.sessions.backends.db'

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}