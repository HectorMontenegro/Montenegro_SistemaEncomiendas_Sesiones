from django.shortcuts import render

# api/views.py
"""
Vistas de la API REST para el Sistema de Encomiendas.
Usamos ViewSets para agrupar operaciones CRUD.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from envios.models import Encomienda, Empleado, HistorialEstado
from clientes.models import Cliente
from rutas.models import Ruta
from config.choices import EstadoEnvio, EstadoGeneral

from .serializers import (
    EncomiendaListSerializer,
    EncomiendaDetailSerializer,
    EncomiendaCreateSerializer,
    ClienteSerializer,
    ClienteListSerializer,
    RutaSerializer,
    RutaListSerializer,
    EmpleadoSerializer,
    HistorialEstadoSerializer,
)
from .permissions import IsAdminOrReadOnly, IsEmpleadoActivo, IsOwnerOrReadOnly
from .pagination import EncomiendaPagination, StandardResultsSetPagination
from .throttling import EncomiendaRateThrottle


# ═══════════════════════════════════════════════════════════════
# VIEWSET: CLIENTES
# ═══════════════════════════════════════════════════════════════

class ClienteViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar clientes.
    """
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo_doc', 'estado']
    search_fields = ['nro_doc', 'nombres', 'apellidos', 'email']
    ordering_fields = ['apellidos', 'nombres', 'fecha_registro']
    ordering = ['apellidos', 'nombres']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ClienteListSerializer
        return ClienteSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrReadOnly()]
        return [IsAuthenticated()]


# ═══════════════════════════════════════════════════════════════
# VIEWSET: RUTAS
# ═══════════════════════════════════════════════════════════════

class RutaViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar rutas.
    """
    queryset = Ruta.objects.all()
    serializer_class = RutaSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'origen', 'destino']
    search_fields = ['codigo', 'origen', 'destino']
    ordering_fields = ['codigo', 'precio_base', 'dias_entrega']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RutaListSerializer
        return RutaSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrReadOnly()]
        return [IsAuthenticated()]


# ═══════════════════════════════════════════════════════════════
# VIEWSET: EMPLEADOS
# ═══════════════════════════════════════════════════════════════

class EmpleadoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint de solo lectura para empleados.
    """
    queryset = Empleado.objects.all()
    serializer_class = EmpleadoSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['cargo', 'estado']
    search_fields = ['codigo', 'nombres', 'apellidos', 'email']
    permission_classes = [IsAuthenticated]


# ═══════════════════════════════════════════════════════════════
# VIEWSET: ENCOMIENDAS (Principal)
# ═══════════════════════════════════════════════════════════════

class EncomiendaViewSet(viewsets.ModelViewSet):
    """
    API endpoint principal para gestionar encomiendas.
    Incluye endpoints personalizados para cambio de estado,
    estadísticas, etc.
    """
    queryset = Encomienda.objects.all()
    pagination_class = EncomiendaPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'ruta', 'remitente', 'destinatario']
    search_fields = ['codigo', 'descripcion', 'remitente__apellidos', 'destinatario__apellidos']
    ordering_fields = ['fecha_registro', 'costo_envio', 'estado']
    ordering = ['-fecha_registro']
    throttle_classes = [EncomiendaRateThrottle]
    
    def get_serializer_class(self):
        """Seleccionar serializer según la acción."""
        if self.action == 'list':
            return EncomiendaListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return EncomiendaCreateSerializer
        return EncomiendaDetailSerializer
    
    def get_permissions(self):
        """Permisos según acción."""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'cambiar_estado']:
            return [IsAuthenticated(), IsEmpleadoActivo()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        """
        Optimizar consultas con select_related para evitar N+1.
        """
        queryset = Encomienda.objects.select_related(
            'remitente', 'destinatario', 'ruta', 'empleado_registro'
        ).prefetch_related('historial', 'historial__empleado')
        
        # Filtro por estado desde query params
        estado = self.request.query_params.get('estado', None)
        if estado:
            queryset = queryset.filter(estado=estado)
        
        return queryset
    
    def perform_create(self, serializer):
        """Asignar empleado automáticamente al crear."""
        empleado = Empleado.objects.filter(
            email=self.request.user.email,
            estado=EstadoGeneral.ACTIVO
        ).first()
        serializer.save(empleado_registro=empleado)
    
    # ═══════════════════════════════════════════════════════════
    # ACCIONES PERSONALIZADAS (Endpoints extra)
    # ═══════════════════════════════════════════════════════════
    
    @action(detail=True, methods=['post'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        """
        Endpoint para cambiar el estado de una encomienda.
        POST /api/v1/encomiendas/{id}/cambiar-estado/
        Body: {"nuevo_estado": "TR", "observacion": "..."}
        """
        encomienda = self.get_object()
        
        nuevo_estado = request.data.get('nuevo_estado')
        observacion = request.data.get('observacion', '')
        
        if not nuevo_estado:
            return Response(
                {'error': 'El campo nuevo_estado es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que el estado sea válido
        estados_validos = [choice[0] for choice in EstadoEnvio.choices]
        if nuevo_estado not in estados_validos:
            return Response(
                {'error': f'Estado no válido. Opciones: {estados_validos}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            encomienda.cambiar_estado(nuevo_estado, empleado, observacion)
            
            return Response({
                'mensaje': f'Estado actualizado a {nuevo_estado}',
                'encomienda': EncomiendaDetailSerializer(encomienda).data
            })
            
        except Empleado.DoesNotExist:
            return Response(
                {'error': 'No tienes perfil de empleado asociado.'},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        """
        Endpoint para obtener estadísticas de encomiendas.
        GET /api/v1/encomiendas/estadisticas/
        """
        from django.utils import timezone
        
        hoy = timezone.now().date()
        
        data = {
            'total_encomiendas': Encomienda.objects.count(),
            'pendientes': Encomienda.objects.filter(estado=EstadoEnvio.PENDIENTE).count(),
            'en_transito': Encomienda.objects.filter(estado=EstadoEnvio.EN_TRANSITO).count(),
            'entregadas': Encomienda.objects.filter(estado=EstadoEnvio.ENTREGADO).count(),
            'con_retraso': Encomienda.objects.filter(
                estado__in=[EstadoEnvio.PENDIENTE, EstadoEnvio.EN_TRANSITO],
                fecha_entrega_est__lt=hoy
            ).count(),
            'entregadas_hoy': Encomienda.objects.filter(
                estado=EstadoEnvio.ENTREGADO,
                fecha_entrega_real=hoy
            ).count(),
        }
        
        return Response(data)
    
    @action(detail=False, methods=['get'], url_path='por-ruta/(?P<ruta_id>[^/.]+)')
    def por_ruta(self, request, ruta_id=None):
        """
        Listar encomiendas por ruta específica.
        GET /api/v1/encomiendas/por-ruta/{ruta_id}/
        """
        encomiendas = Encomienda.objects.filter(ruta_id=ruta_id)
        page = self.paginate_queryset(encomiendas)
        
        if page is not None:
            serializer = EncomiendaListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = EncomiendaListSerializer(encomiendas, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='mi-historial')
    def mi_historial(self, request):
        """
        Listar encomiendas registradas por el empleado actual.
        GET /api/v1/encomiendas/mi-historial/
        """
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            encomiendas = Encomienda.objects.filter(empleado_registro=empleado)
            page = self.paginate_queryset(encomiendas)
            
            if page is not None:
                serializer = EncomiendaListSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = EncomiendaListSerializer(encomiendas, many=True)
            return Response(serializer.data)
            
        except Empleado.DoesNotExist:
            return Response(
                {'error': 'No tienes perfil de empleado.'},
                status=status.HTTP_403_FORBIDDEN
            )


# ═══════════════════════════════════════════════════════════════
# VIEWSET: HISTORIAL ESTADO (Solo lectura)
# ═══════════════════════════════════════════════════════════════

class HistorialEstadoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint de solo lectura para historial de estados.
    """
    queryset = HistorialEstado.objects.select_related('encomienda', 'empleado')
    serializer_class = HistorialEstadoSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['estado_nuevo', 'empleado']
    ordering = ['-fecha_cambio']
    permission_classes = [IsAuthenticated]
