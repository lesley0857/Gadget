import os
import dj_database_url
import cloudinary
import cloudinary.uploader
import cloudinary.api	

from dotenv import load_dotenv
from pathlib import Path
from datetime import timedelta




load_dotenv()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '7gp+h+_c)q4i5afkc*zzh-4voojio9$7o6*g3)+9kfk=b)#u3@'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


CLOUDINARY_STORAGE = {
    "CLOUD_NAME": "djxoeirbo",
    "API_KEY": "994877198429841",
    "API_SECRET": "PIcYa2IzNtmrCvSrQWWUxynowpA",

    "TRANSFORMATION": {
        "quality": "auto",
        "fetch_format": "auto",
    }
}

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'django.contrib.humanize',

    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    
    'rest_framework',
    'django_celery_beat',
    'cloudinary',
    'cloudinary_storage',
    "django_summernote",

    'accounts',
    'cart',
    'catalog',
    'locations',
    'logistics',
    'pricing',
    'orders',
    'payments',
    'wallets',
    'withdrawals',
    'disputes',
    'webhooks',
    'services',
    'remarobeprojects',
    'testimonials',
    'blog',
    

    
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    "allauth.account.middleware.AccountMiddleware",

]

ROOT_URLCONF = 'phoneappproject.urls'

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
                'catalog.context_processors.global_categories',
                "context_processors.website_content",
            ],
        },
    },
]

WSGI_APPLICATION = 'phoneappproject.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
#postgresql://oluoma:7veqWjqVPPwXtvIh4EqFIWJqrIuiAibs@dpg-d6tsf85m5p6s73bj9ht0-a.oregon-postgres.render.com/phoneappdb_7e6i
print(os.environ['POSTGRES_DB'])

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'neondb',
#         'USER': 'your_user',
#         'PASSWORD': 'your_password',
#         'HOST': 'ep-gentle-wave-aplz2z82.us-east-1.aws.neon.tech',  # Remove '-pooler' for direct connection
#         'PORT': '5432',
#         'OPTIONS': {
#             'connect_timeout': 10,  # Recommended by Neon Docs
#         },
#     }
# }


# DATABASES = {
#     'default': dj_database_url.parse(
       
#         url="postgresql://neondb_owner:npg_TJ02eojwrcXZ@ep-gentle-wave-aplz2z82-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
#         url = "postgresql://oluoma:7veqWjqVPPwXtvIh4EqFIWJqrIuiAibs@dpg-d6tsf85m5p6s73bj9ht0-a.oregon-postgres.render.com/phoneappdb_7e6i",
#         conn_max_age=600,    # optional: connection pooling
#         ssl_require=True     # forces SSL
#     )
# }

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Cloudinary

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        # For each OAuth based provider, either add a ``SocialApp``
        # (``socialaccount`` app) containing the required client
        # credentials, or list them here:
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'APP': {
            'client_id': '1092555448782-fveoqtiebkd9ku16b9as7fpg7o1u7mlk.apps.googleusercontent.com',
            'secret': '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',
            'key': ''
        }
    }
}


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
}

permission_classes = ['IsAuthenticated']


# Celery
CELERY_BROKER_URL = "redis://redis:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static/")
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
AUTH_USER_MODEL = 'accounts.User'
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SITE_ID = 1

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

KWIK_TOKEN = "test_token"
KWIK_VENDOR_ID = "123456"
KWIK_DOMAIN = "yourapp.com"

SHIPPING_MARGIN_PERCENT = 0.15   # 15% profit
GROUPING_RADIUS_KM = 3           # vendors within 3km grouped

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = "nwekelesley@gmail.com"
EMAIL_HOST_PASSWORD = "qmdrunmbsljwdzwt"
EMAIL_USE_TLS = True


AUTHENTICATION_BACKENDS = [
    # 'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
SOCIALACCOUNT_ADAPTER = 'accounts.adapters.CustomSocialAccountAdapter'

ACCOUNT_LOGIN_METHODS = {'email'}

ACCOUNT_SIGNUP_FIELDS = [
    'email*',
    'password1*',
    'password2*',
]

ACCOUNT_EMAIL_VERIFICATION = "none"
LOGIN_REDIRECT_URL = '/'




USE_L10N = True