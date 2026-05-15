# envios/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Consumer global: todas las notificaciones del sistema
    re_path(r'^ws/encomiendas/$', consumers.EncomiendaConsumer.as_asgi(), name='ws-encomiendas'),
    
    # Consumer de detalle: una encomienda específica
    re_path(r'^ws/encomiendas/(?P<pk>\d+)/$', consumers.EncomiendaDetalleConsumer.as_asgi(), name='ws-encomienda-detalle'),
    
    # Consumer del dashboard: estadísticas en tiempo real
    re_path(r'^ws/dashboard/$', consumers.DashboardConsumer.as_asgi(), name='ws-dashboard'),
]