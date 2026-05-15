# envios/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)

class EncomiendaConsumer(AsyncWebsocketConsumer):
    """
    Consumer global. Cada empleado conectado recibe todas las notificaciones
    de cambio de estado del sistema.
    """
    
    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return
        
        self.group_name = 'encomiendas_global'
        
        # Unirse al grupo global
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Enviar estadísticas iniciales
        stats = await self.get_estadisticas()
        await self.send(text_data=json.dumps({
            'tipo': 'conectado',
            'usuario': user.username,
            'stats': stats,
        }))
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'tipo': 'error',
                'codigo': 'JSON_INVALIDO',
                'mensaje': 'El mensaje no es JSON válido'
            }))
            return
        
        tipo = data.get('tipo')
        
        if tipo == 'ping':
            await self.send(text_data=json.dumps({'tipo': 'pong'}))
        elif tipo == 'solicitar_stats':
            stats = await self.get_estadisticas()
            await self.send(text_data=json.dumps({
                'tipo': 'stats',
                'stats': stats
            }))
        elif tipo == 'suscribir_encomienda':
            enc_id = data.get('encomienda_id')
            if enc_id:
                await self.channel_layer.group_add(
                    f'encomienda_{enc_id}',
                    self.channel_name
                )
                await self.send(text_data=json.dumps({
                    'tipo': 'suscrito',
                    'encomienda_id': enc_id
                }))
        else:
            await self.send(text_data=json.dumps({
                'tipo': 'error',
                'mensaje': f'Tipo desconocido: {tipo}'
            }))
    
    # Handler de grupo: recibe del channel layer y reenvía al navegador
    async def encomienda_estado_cambio(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'estado_cambio',
            'encomienda_id': event['encomienda_id'],
            'codigo': event['codigo'],
            'estado_anterior': event['estado_anterior'],
            'estado_nuevo': event['estado_nuevo'],
            'empleado': event['empleado'],
            'timestamp': event['timestamp'],
        }))
    
    async def progreso(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'progreso',
            'actual': event['actual'],
            'total': event['total'],
            'codigo': event.get('codigo'),
            'porcentaje': event.get('porcentaje'),
        }))

    @database_sync_to_async
    def get_estadisticas(self):
        from .models import Encomienda
        return {
            'activas': Encomienda.objects.activas().count(),
            'en_transito': Encomienda.objects.en_transito().count(),
            'con_retraso': Encomienda.objects.con_retraso().count(),
        }


class EncomiendaDetalleConsumer(AsyncWebsocketConsumer):
    """
    Consumer de detalle. Solo notifica cambios de UNA encomienda específica.
    """
    
    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return
        
        self.enc_pk = self.scope['url_route']['kwargs']['pk']
        self.group_name = f'encomienda_{self.enc_pk}'
        
        # Verificar que la encomienda existe
        existe = await self.enc_existe(self.enc_pk)
        if not existe:
            await self.close(code=4004)  # Recurso no encontrado
            return
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        
        # Enviar estado actual
        enc_data = await self.get_encomienda(self.enc_pk)
        await self.send(text_data=json.dumps({
            'tipo': 'estado_actual',
            'encomienda': enc_data,
        }, cls=DjangoJSONEncoder))
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        pass  # Este consumer solo recibe push, no mensajes del cliente
    
    async def encomienda_estado_cambio(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'estado_cambio',
            'estado_anterior': event['estado_anterior'],
            'estado_nuevo': event['estado_nuevo'],
            'empleado': event['empleado'],
            'timestamp': event['timestamp'],
        }))
    
    @database_sync_to_async
    def enc_existe(self, pk):
        from .models import Encomienda
        return Encomienda.objects.filter(pk=pk).exists()
    
    @database_sync_to_async
    def get_encomienda(self, pk):
        from .models import Encomienda
        from api.serializers import EncomiendaDetailSerializer
        try:
            enc = Encomienda.objects.con_relaciones().get(pk=pk)
            return dict(EncomiendaDetailSerializer(enc).data)
        except Encomienda.DoesNotExist:
            return None


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    Consumer del dashboard. Recibe actualizaciones de estadísticas
    cada vez que cambia una encomienda.
    """
    
    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return
        
        self.group_name = 'dashboard'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        
        # Enviar estadísticas iniciales
        stats = await self.get_stats()
        await self.send(text_data=json.dumps({
            'tipo': 'stats_iniciales',
            'stats': stats,
        }))
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get('tipo') == 'solicitar_stats':
                stats = await self.get_stats()
                await self.send(text_data=json.dumps({
                    'tipo': 'stats_actualizado',
                    'stats': stats,
                }))
        except json.JSONDecodeError:
            pass
    
    # Handler del channel layer
    async def dashboard_actualizar(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'stats_actualizado',
            'stats': event['stats'],
        }))

    async def encomienda_estado_cambio(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'estado_cambio',
            'encomienda_id': event['encomienda_id'],
            'codigo': event['codigo'],
            'estado_anterior': event['estado_anterior'],
            'estado_nuevo': event['estado_nuevo'],
            'empleado': event['empleado'],
            'timestamp': event['timestamp'],
        }))
    
    async def progreso(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'progreso',
            'actual': event['actual'],
            'total': event['total'],
            'codigo': event.get('codigo'),
            'porcentaje': event.get('porcentaje'),
        }))

    @database_sync_to_async
    def get_stats(self):
        from .models import Encomienda
        from django.utils import timezone
        hoy = timezone.now().date()
        return {
            'activas': Encomienda.objects.activas().count(),
            'en_transito': Encomienda.objects.en_transito().count(),
            'con_retraso': Encomienda.objects.con_retraso().count(),
            'entregadas_hoy': Encomienda.objects.filter(
                estado='EN', fecha_entrega_real=hoy
            ).count(),
        }
