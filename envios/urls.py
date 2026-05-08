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

        # Carrito de servicios
    path('carrito/', views.cart_detail, name='cart_detail'),
    path('carrito/agregar/', views.cart_add, name='cart_add'),
    path('carrito/eliminar/<str:temp_id>/', views.cart_remove, name='cart_remove'),
    path('carrito/vaciar/', views.cart_clear, name='cart_clear'),
    
    # Checkout y órdenes
    path('checkout/', views.checkout, name='checkout'),
    path('ordenes/', views.order_list, name='order_list'),
    path('ordenes/<uuid:pedido_id>/', views.order_detail, name='order_detail'),
    
    # API para paginación infinita
    path('api/encomiendas/', views.api_encomiendas_list, name='api_encomiendas'),
]