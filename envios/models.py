# envios/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import timedelta
import uuid

from config.choices import EstadoGeneral, EstadoEnvio
from clientes.models import Cliente
from rutas.models import Ruta
from .validators import validar_peso_positivo, validar_codigo_encomienda
from .querysets import EncomiendaQuerySet

# ─── Modelo Empleado ─────────────────────────────────────────────
class Empleado(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    cargo = models.CharField(max_length=80)
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    estado = models.IntegerField(
        choices=EstadoGeneral.choices,
        default=EstadoGeneral.ACTIVO
    )
    fecha_ingreso = models.DateField()
    
    # Relación ManyToMany con Rutas
    rutas_asignadas = models.ManyToManyField(
        'rutas.Ruta',
        blank=True,
        related_name='empleados_asignados'
    )

    def __str__(self):
        return f'{self.codigo} - {self.apellidos}, {self.nombres}'

    class Meta:
        db_table = 'empleados'
        verbose_name = 'Empleado'
        verbose_name_plural = 'Empleados'
        ordering = ['apellidos']


# ─── Modelo Encomienda ────────────────────────────────────────────
class Encomienda(models.Model):
    # Identificación
    codigo = models.CharField(
        max_length=20,
        unique=True,
        validators=[validar_codigo_encomienda]
    )
    descripcion = models.TextField()
    peso_kg = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[
            validar_peso_positivo,
            MinValueValidator(0.01, message='El peso mínimo es 0.01kg')
        ]
    )
    volumen_cm3 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Relaciones ForeignKey con PROTECT
    remitente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='envios_como_remitente',
    )
    destinatario = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='envios_como_destinatario',
    )
    ruta = models.ForeignKey(
        Ruta,
        on_delete=models.PROTECT,
        related_name='encomiendas',
    )
    empleado_registro = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name='encomiendas_registradas'
    )

    # Estado y fechas
    estado = models.CharField(
        max_length=2,
        choices=EstadoEnvio.choices,
        default=EstadoEnvio.PENDIENTE
    )
    costo_envio = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_entrega_est = models.DateField(null=True, blank=True)
    fecha_entrega_real = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    # Manager personalizado
    objects = EncomiendaQuerySet.as_manager()

    # ─── Propiedades de negocio ─────────────────────────────────
    @property
    def esta_entregada(self):
        return self.estado == EstadoEnvio.ENTREGADO

    @property
    def esta_en_transito(self):
        return self.estado == EstadoEnvio.EN_TRANSITO

    @property
    def dias_en_transito(self):
        if not self.fecha_registro:
            return 0
        delta = timezone.now().date() - self.fecha_registro.date()
        return delta.days

    @property
    def tiene_retraso(self):
        if not self.fecha_entrega_est or self.esta_entregada:
            return False
        return timezone.now().date() > self.fecha_entrega_est

    @property
    def descripcion_corta(self):
        if len(self.descripcion) > 50:
            return self.descripcion[:50] + '...'
        return self.descripcion

    # ─── Validaciones cruzadas (clean) ──────────────────────────
    def clean(self):
        errors = {}
        
        # Regla 1: remitente y destinatario no pueden ser la misma persona
        if self.remitente_id and self.destinatario_id:
            if self.remitente_id == self.destinatario_id:
                errors['destinatario'] = ValidationError(
                    'El destinatario no puede ser el mismo que el remitente.'
                )
        
        # Regla 2: fecha de entrega estimada no puede ser en el pasado
        if self.fecha_entrega_est:
            if self.fecha_entrega_est < timezone.now().date():
                errors['fecha_entrega_est'] = ValidationError(
                    'La fecha de entrega estimada no puede ser en el pasado.'
                )
        
        # Regla 3: fecha de entrega real no puede ser antes de la estimada
        if self.fecha_entrega_est and self.fecha_entrega_real:
            if self.fecha_entrega_real < self.fecha_entrega_est:
                errors['fecha_entrega_real'] = ValidationError(
                    'La fecha de entrega real no puede ser antes de la estimada.'
                )
        
        if errors:
            raise ValidationError(errors)

    # ─── Sobrescribir save para forzar validaciones ──────────────
    def save(self, *args, **kwargs):
        self.full_clean()  # ¡CRÍTICO! Dispara clean_fields() + clean()
        super().save(*args, **kwargs)

    # ─── Métodos de negocio ─────────────────────────────────────
    def cambiar_estado(self, nuevo_estado, empleado, observacion=''):
        """
        Cambia el estado de la encomienda y registra el cambio
        en HistorialEstado automáticamente.
        """
        if nuevo_estado == self.estado:
            raise ValueError(f'La encomienda ya se encuentra en estado {self.get_estado_display()}')
        
        estado_anterior = self.estado
        self.estado = nuevo_estado
        
        # Si se entrega, registrar fecha real
        if nuevo_estado == EstadoEnvio.ENTREGADO:
            self.fecha_entrega_real = timezone.now().date()
        
        self.save()
        
        # Registrar en el historial
        HistorialEstado.objects.create(
            encomienda=self,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            empleado=empleado,
            observacion=observacion
        )
        return self

    def calcular_costo(self):
        """
        Calcula el costo del envío basándose en el precio base de la ruta
        y el peso del paquete.
        """
        PRECIO_POR_KG_EXTRA = 2.50  # soles por kg adicional
        PESO_BASE = 5.0  # los primeros 5kg están en el precio base
        
        costo = self.ruta.precio_base
        
        if self.peso_kg > PESO_BASE:
            costo += (self.peso_kg - PESO_BASE) * PRECIO_POR_KG_EXTRA
        
        return round(costo, 2)

    # ─── Classmethod factory ────────────────────────────────────
    @classmethod
    def crear_con_costo_calculado(cls, remitente, destinatario, ruta,
                                   empleado, descripcion, peso_kg, **kwargs):
        """
        Fábrica: crea una encomienda calculando el costo automáticamente.
        """
        codigo = f'ENC-{timezone.now().strftime("%Y%m%d")}-{str(uuid.uuid4())[:6].upper()}'
        fecha_est = timezone.now().date() + timedelta(days=ruta.dias_entrega)
        
        encomienda = cls(
            codigo=codigo,
            descripcion=descripcion,
            peso_kg=peso_kg,
            remitente=remitente,
            destinatario=destinatario,
            ruta=ruta,
            empleado_registro=empleado,
            fecha_entrega_est=fecha_est,
            **kwargs
        )
        encomienda.costo_envio = encomienda.calcular_costo()
        encomienda.save()
        return encomienda

    def __str__(self):
        return f'{self.codigo} [{self.get_estado_display()}]'

    class Meta:
        db_table = 'encomiendas'
        verbose_name = 'Encomienda'
        verbose_name_plural = 'Encomiendas'
        ordering = ['-fecha_registro']


# ─── Modelo HistorialEstado ─────────────────────────────────────
class HistorialEstado(models.Model):
    encomienda = models.ForeignKey(
        Encomienda,
        on_delete=models.CASCADE,
        related_name='historial'
    )
    estado_anterior = models.CharField(
        max_length=2,
        choices=EstadoEnvio.choices
    )
    estado_nuevo = models.CharField(
        max_length=2,
        choices=EstadoEnvio.choices
    )
    observacion = models.TextField(blank=True, null=True)
    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name='cambios_estado'
    )
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.encomienda.codigo}: {self.estado_anterior} → {self.estado_nuevo}'

    class Meta:
        db_table = 'historial_estados'
        ordering = ['-fecha_cambio']