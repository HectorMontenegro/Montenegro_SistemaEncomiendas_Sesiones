from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application


class EncomiendaConsumerTests(TransactionTestCase):
    def make_user(self, username='ws-user'):
        return get_user_model().objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='secret123',
        )

    def ws_path(self, user=None):
        if not user:
            return '/ws/encomiendas/'
        token = AccessToken.for_user(user)
        return f'/ws/encomiendas/?token={token}'

    def test_conexion_sin_autenticacion(self):
        async_to_sync(self._test_conexion_sin_autenticacion)()

    async def _test_conexion_sin_autenticacion(self):
        communicator = WebsocketCommunicator(application, '/ws/encomiendas/')
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)
        await communicator.disconnect()

    def test_conexion_autenticada(self):
        user = self.make_user()
        async_to_sync(self._test_conexion_autenticada)(self.ws_path(user))

    async def _test_conexion_autenticada(self, path):
        communicator = WebsocketCommunicator(application, path)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['tipo'], 'conectado')
        self.assertIn('stats', response)
        self.assertIn('activas', response['stats'])

        await communicator.disconnect()

    def test_ping_pong(self):
        user = self.make_user('ping-user')
        async_to_sync(self._test_ping_pong)(self.ws_path(user))

    async def _test_ping_pong(self, path):
        communicator = WebsocketCommunicator(application, path)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from(timeout=3)

        await communicator.send_json_to({'tipo': 'ping'})
        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['tipo'], 'pong')

        await communicator.disconnect()

    def test_notificacion_via_channel_layer(self):
        user = self.make_user('notify-user')
        async_to_sync(self._test_notificacion_via_channel_layer)(self.ws_path(user))

    async def _test_notificacion_via_channel_layer(self, path):
        communicator = WebsocketCommunicator(application, path)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from(timeout=3)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            'encomiendas_global',
            {
                'type': 'encomienda_estado_cambio',
                'encomienda_id': 1,
                'codigo': 'ENC-2026-001',
                'estado_anterior': 'PE',
                'estado_nuevo': 'TR',
                'empleado': 'Empleado Demo',
                'timestamp': '2026-05-14T10:00:00Z',
            }
        )

        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response['tipo'], 'estado_cambio')
        self.assertEqual(response['codigo'], 'ENC-2026-001')
        self.assertEqual(response['estado_nuevo'], 'TR')

        await communicator.disconnect()
