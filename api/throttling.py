# api/throttling.py
"""
Throttling (limitación de tasa) personalizado.
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class BurstRateThrottle(AnonRateThrottle):
    """Límite para ráfagas de peticiones anónimas."""
    scope = 'burst'


class SustainedRateThrottle(UserRateThrottle):
    """Límite sostenido para usuarios autenticados."""
    scope = 'sustained'


class EncomiendaRateThrottle(UserRateThrottle):
    """Límite específico para operaciones de encomiendas."""
    scope = 'encomienda'
    rate = '30/minute'  # 30 peticiones por minuto