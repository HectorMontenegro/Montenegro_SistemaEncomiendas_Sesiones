# envios/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/perfil/', views.perfil_view, name='perfil'),
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Encomiendas
    path('encomiendas/', views.encomienda_lista, name='encomienda_lista'),
    path('encomiendas/nueva/', views.encomienda_crear, name='encomienda_crear'),
    path('encomiendas/<int:pk>/', views.encomienda_detalle, name='encomienda_detalle'),
    path('encomiendas/<int:pk>/editar/', views.encomienda_editar, name='encomienda_editar'),
    path('encomiendas/<int:pk>/estado/', views.encomienda_cambiar_estado, name='encomienda_cambiar_estado'),
    
    # API AJAX
    path('api/encomiendas/<int:pk>/estado/', views.encomienda_estado_json, name='encomienda_estado_json'),
]