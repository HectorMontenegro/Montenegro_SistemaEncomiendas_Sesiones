import asyncio

from asgiref.sync import sync_to_async
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from config.choices import EstadoEnvio
from .models import Empleado, Encomienda


async def dashboard_stats_async(request):
    """
    Endpoint async: calcula las estadisticas del dashboard en paralelo.
    """
    if not request.user.is_authenticated:
        return HttpResponse(status=401)

    hoy = timezone.now().date()
    activas, en_transito, con_retraso, entregadas_hoy = await asyncio.gather(
        Encomienda.objects.activas().acount(),
        Encomienda.objects.en_transito().acount(),
        Encomienda.objects.con_retraso().acount(),
        Encomienda.objects.filter(
            estado=EstadoEnvio.ENTREGADO,
            fecha_entrega_real=hoy,
        ).acount(),
    )

    return JsonResponse({
        'activas': activas,
        'en_transito': en_transito,
        'con_retraso': con_retraso,
        'entregadas_hoy': entregadas_hoy,
    })


async def enviar_notificacion_email(enc, nuevo_estado: str):
    await asyncio.sleep(0.5)
    return f'Email enviado: {enc.codigo} -> {nuevo_estado}'


async def registrar_en_log_externo(enc, estado: str):
    await asyncio.sleep(0.1)
    return {'codigo': enc.codigo, 'estado': estado}


_background_tasks = set()


def run_background(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


@csrf_exempt
async def cambiar_estado_async(request, pk: int):
    """
    Vista async para cambiar estado y lanzar tareas no criticas en background.
    Espera POST form-data con estado/nuevo_estado y observacion.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo no permitido'}, status=405)
    if not request.user.is_authenticated:
        return HttpResponse(status=401)

    nuevo_estado = request.POST.get('nuevo_estado') or request.POST.get('estado')
    observacion = request.POST.get('observacion', '')
    if not nuevo_estado:
        return JsonResponse({'error': 'El estado es requerido'}, status=400)

    estados_validos = [choice[0] for choice in EstadoEnvio.choices]
    if nuevo_estado not in estados_validos:
        return JsonResponse({'error': f'Estado no valido. Opciones: {estados_validos}'}, status=400)

    try:
        enc = await Encomienda.objects.aget(pk=pk)
    except Encomienda.DoesNotExist:
        return JsonResponse({'error': 'Encomienda no encontrada'}, status=404)

    empleado = await Empleado.objects.filter(email=request.user.email).afirst()
    if not empleado:
        empleado = enc.empleado_registro
    if not empleado:
        return JsonResponse({'error': 'No tienes perfil de empleado asociado'}, status=403)

    try:
        await sync_to_async(enc.cambiar_estado)(nuevo_estado, empleado, observacion)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    run_background(enviar_notificacion_email(enc, nuevo_estado))
    run_background(registrar_en_log_externo(enc, nuevo_estado))

    return JsonResponse({'ok': True, 'estado': nuevo_estado})
