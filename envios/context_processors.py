# envios/context_processors.py
from .models import Encomienda

def estadisticas_globales(request):
    """
    Inyecta estadísticas en el navbar de todas las páginas.
    Se registra en settings.py TEMPLATES/OPTIONS/context_processors
    """
    if not request.user.is_authenticated:
        return {}
    
    return {
        'nav_activas': Encomienda.objects.activas().count(),
        'nav_retraso': Encomienda.objects.con_retraso().count(),
        'nav_pendientes': Encomienda.objects.pendientes().count(),
    }