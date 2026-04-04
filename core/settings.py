"""
Django settings for core project.
"""

from pathlib import Path
import os

# Base dir
BASE_DIR = Path(__file__).resolve().parent.parent


# 🔐 Seguridad
SECRET_KEY = 'django-insecure-234o*%c&_q3*de#=grkfkmxc=d+p5ra1($8@uqul)lz_7^cii$'

DEBUG = True

ALLOWED_HOSTS = [
    'linercandia.pythonanywhere.com',
    '127.0.0.1',
    'localhost'
]


# 🧩 Apps
INSTALLED_APPS = [
    'gestion_ventas.apps.GestionVentasConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]


# ⚙️ Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# 🔗 URLs / WSGI
ROOT_URLCONF = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'


# 🎨 Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # 👈 recomendado
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# 🗄️ Base de datos
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# 🔑 Validación de contraseñas
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# 🌍 Internacionalización
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'

USE_I18N = True
USE_TZ = True


# 📦 Static files (CORREGIDO)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    BASE_DIR / "static"
]


# 🖼️ Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# 🔧 Default auto field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# 🔐 CSRF / Cookies (para producción)
CSRF_TRUSTED_ORIGINS = [
    'https://linercandia.pythonanywhere.com'
]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True


# 🌐 URL base de la app (FIX ERROR 🔥)
APP_BASE_URL = "https://linercandia.pythonanywhere.com"