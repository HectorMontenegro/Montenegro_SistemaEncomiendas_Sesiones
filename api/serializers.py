# api/serializers.py
"""
Serializadores para la API del Sistema de Encomiendas.
Convierten modelos Django a JSON y validan datos de entrada.
"""

from rest_framework import serializers
from envios.models import Encomienda, Empleado, HistorialEstado
from clientes.models import Cliente
from rutas.models import Ruta
from config.choices import EstadoEnvio, EstadoGeneral


# ═══════════════════════════════════════════════════════════════
# SERIALIZADORES DE CLIENTES
# ═══════════════════════════════════════════════════════════════

class ClienteSerializer(serializers.ModelSerializer):
    """Serializador completo para Cliente."""
    nombre_completo = serializers.CharField(read_only=True)
    esta_activo = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Cliente
        fields = [
            'id', 'tipo_doc', 'nro_doc', 'nombres', 'apellidos',
            'nombre_completo', 'telefono', 'email', 'direccion',
            'estado', 'esta_activo', 'fecha_registro'
        ]
        read_only_fields = ['id', 'fecha_registro']


class ClienteListSerializer(serializers.ModelSerializer):
    """Serializador simplificado para listados de clientes."""
    nombre_completo = serializers.CharField(read_only=True)
    
    class Meta:
        model = Cliente
        fields = ['id', 'nro_doc', 'nombre_completo', 'telefono', 'estado']


# ═══════════════════════════════════════════════════════════════
# SERIALIZADORES DE RUTAS
# ═══════════════════════════════════════════════════════════════

class RutaSerializer(serializers.ModelSerializer):
    """Serializador completo para Ruta."""
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    class Meta:
        model = Ruta
        fields = [
            'id', 'codigo', 'origen', 'destino', 'descripcion',
            'precio_base', 'dias_entrega', 'estado', 'estado_display'
        ]


class RutaListSerializer(serializers.ModelSerializer):
    """Serializador simplificado para listados de rutas."""
    
    class Meta:
        model = Ruta
        fields = ['id', 'codigo', 'origen', 'destino', 'precio_base']


# ═══════════════════════════════════════════════════════════════
# SERIALIZADORES DE EMPLEADOS
# ═══════════════════════════════════════════════════════════════

class EmpleadoSerializer(serializers.ModelSerializer):
    """Serializador para Empleado."""
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    class Meta:
        model = Empleado
        fields = [
            'id', 'codigo', 'nombres', 'apellidos', 'cargo',
            'email', 'telefono', 'estado', 'estado_display',
            'fecha_ingreso'
        ]


# ═══════════════════════════════════════════════════════════════
# SERIALIZADORES DE HISTORIAL ESTADO
# ═══════════════════════════════════════════════════════════════

class HistorialEstadoSerializer(serializers.ModelSerializer):
    """Serializador para Historial de Estados."""
    estado_anterior_display = serializers.CharField(
        source='get_estado_anterior_display', read_only=True
    )
    estado_nuevo_display = serializers.CharField(
        source='get_estado_nuevo_display', read_only=True
    )
    empleado_nombre = serializers.StringRelatedField(source='empleado', read_only=True)
    
    class Meta:
        model = HistorialEstado
        fields = [
            'id', 'estado_anterior', 'estado_anterior_display',
            'estado_nuevo', 'estado_nuevo_display',
            'observacion', 'empleado', 'empleado_nombre',
            'fecha_cambio'
        ]
        read_only_fields = ['fecha_cambio']


# ═══════════════════════════════════════════════════════════════
# SERIALIZADORES DE ENCOMIENDAS
# ═══════════════════════════════════════════════════════════════

class EncomiendaListSerializer(serializers.ModelSerializer):
    """
    Serializador simplificado para listados de encomiendas.
    Incluye datos relacionados básicos.
    """
    remitente_nombre = serializers.CharField(
        source='remitente.nombre_completo', read_only=True
    )
    destinatario_nombre = serializers.CharField(
        source='destinatario.nombre_completo', read_only=True
    )
    ruta_codigo = serializers.CharField(source='ruta.codigo', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    tiene_retraso = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Encomienda
        fields = [
            'id', 'codigo', 'descripcion', 'peso_kg',
            'remitente_nombre', 'destinatario_nombre',
            'ruta_codigo', 'estado', 'estado_display',
            'costo_envio', 'fecha_registro', 'tiene_retraso'
        ]


class EncomiendaDetailSerializer(serializers.ModelSerializer):
    """
    Serializador completo para detalle de encomienda.
    Incluye todos los datos relacionados.
    """
    remitente = ClienteSerializer(read_only=True)
    destinatario = ClienteSerializer(read_only=True)
    ruta = RutaSerializer(read_only=True)
    empleado_registro = EmpleadoSerializer(read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    historial = HistorialEstadoSerializer(many=True, read_only=True)
    
    # Campos calculados del modelo
    esta_entregada = serializers.BooleanField(read_only=True)
    esta_en_transito = serializers.BooleanField(read_only=True)
    dias_en_transito = serializers.IntegerField(read_only=True)
    tiene_retraso = serializers.BooleanField(read_only=True)
    descripcion_corta = serializers.CharField(read_only=True)
    
    class Meta:
        model = Encomienda
        fields = [
            'id', 'codigo', 'descripcion', 'descripcion_corta',
            'peso_kg', 'volumen_cm3',
            'remitente', 'destinatario', 'ruta',
            'empleado_registro', 'estado', 'estado_display',
            'costo_envio', 'fecha_registro', 'fecha_entrega_est',
            'fecha_entrega_real', 'observaciones',
            'esta_entregada', 'esta_en_transito', 'dias_en_transito',
            'tiene_retraso', 'historial'
        ]


class EncomiendaCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear/actualizar encomiendas.
    Incluye validaciones de negocio.
    """
    # Campos de escritura para relaciones (usamos IDs)
    remitente_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.filter(estado=EstadoGeneral.ACTIVO),
        source='remitente',
        write_only=True
    )
    destinatario_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.filter(estado=EstadoGeneral.ACTIVO),
        source='destinatario',
        write_only=True
    )
    ruta_id = serializers.PrimaryKeyRelatedField(
        queryset=Ruta.objects.filter(estado=EstadoGeneral.ACTIVO),
        source='ruta',
        write_only=True
    )
    
    class Meta:
        model = Encomienda
        fields = [
            'codigo', 'descripcion', 'peso_kg', 'volumen_cm3',
            'remitente_id', 'destinatario_id', 'ruta_id',
            'costo_envio', 'fecha_entrega_est', 'observaciones'
        ]
    
    def validate_codigo(self, value):
        """Validar que el código empiece con ENC-"""
        if not value.startswith('ENC-'):
            raise serializers.ValidationError(
                "El código debe comenzar con 'ENC-'"
            )
        return value
    
    def validate(self, data):
        """Validaciones cruzadas del negocio."""
        remitente = data.get('remitente')
        destinatario = data.get('destinatario')
        
        if remitente and destinatario and remitente == destinatario:
            raise serializers.ValidationError(
                {"destinatario": "El remitente y destinatario no pueden ser la misma persona."}
            )
        
        return data
    
    def create(self, validated_data):
        """Crear encomienda con empleado del request."""
        request = self.context.get('request')
        if request and hasattr(request.user, 'empleado'):
            validated_data['empleado_registro'] = request.user.empleado
        
        return super().create(validated_data)
