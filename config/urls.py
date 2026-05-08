# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('envios.urls')),  # ← Nuestras URLs
    path('accounts/', include('allauth.urls')),  
    path('accounts/', include('django.contrib.auth.urls')),  # ← Auth de Django (backup)
]

# Servir estáticos y media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)