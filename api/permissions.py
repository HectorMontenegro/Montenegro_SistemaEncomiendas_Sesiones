# api/permissions.py
"""
Permisos personalizados para la API del Sistema de Encomiendas.
"""

from rest_framework import permissions
from config.choices import EstadoGeneral


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permiso que permite lectura a cualquiera,
    pero escritura solo a administradores/staff.
    """
    def has_permission(self, request, view):
        # Permitir GET, HEAD, OPTIONS a cualquiera autenticado
        if request.method in permissions.SAFE_METHODS:
            return True
        # Solo admin puede escribir
        return request.user and request.user.is_staff


class IsEmpleadoActivo(permissions.BasePermission):
    """
    Permiso que verifica que el usuario tenga un Empleado activo asociado.
    Relevante para el sistema de encomiendas.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Verificar que el usuario tenga un empleado activo
        from envios.models import Empleado
        return Empleado.objects.filter(
            email=request.user.email,
            estado=EstadoGeneral.ACTIVO
        ).exists()


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permiso que permite editar solo al creador del objeto.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Verificar si el objeto tiene creado_por o empleado_registro
        if hasattr(obj, 'empleado_registro'):
            return obj.empleado_registro.email == request.user.email
        if hasattr(obj, 'creado_por'):
            return obj.creado_por == request.user
        
        return False
