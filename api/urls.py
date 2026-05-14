# api/urls.py
"""
URLs de la API REST del Sistema de Encomiendas.
Usamos routers para generar URLs automáticamente.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import (
    EncomiendaViewSet,
    ClienteViewSet,
    RutaViewSet,
    EmpleadoViewSet,
    HistorialEstadoViewSet,
)

# Crear router y registrar viewsets
router = DefaultRouter()
router.register(r'encomiendas', EncomiendaViewSet, basename='encomienda')
router.register(r'clientes', ClienteViewSet, basename='cliente')
router.register(r'rutas', RutaViewSet, basename='ruta')
router.register(r'empleados', EmpleadoViewSet, basename='empleado')
router.register(r'historial', HistorialEstadoViewSet, basename='historial')

# URLs de la API
urlpatterns = [
    # Router URLs (generadas automáticamente)
    path('', include(router.urls)),
    
    # Autenticación JWT
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]