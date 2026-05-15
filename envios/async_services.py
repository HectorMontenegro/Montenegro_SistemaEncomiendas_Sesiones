import asyncio

import httpx
from django.utils import timezone

from config.choices import EstadoEnvio
from .models import Encomienda


TRANSPORTISTA_TRACKING_URL = 'https://api.transportista.pe/v1/track/{codigo}'


async def queryset_to_list(queryset):
    return [obj async for obj in queryset]


async def verificar_estado_transportista(codigo: str) -> dict:
    """
    Consulta async a una API externa de tracking.
    Devuelve un dict controlado ante timeout o error de conexion.
    """
    url = TRANSPORTISTA_TRACKING_URL.format(codigo=codigo)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            response.raise_for_status()
            data = response.json()
            return {
                'codigo': codigo,
                'encontrado': True,
                'estado_ext': data.get('status'),
                'ubicacion': data.get('location'),
                'timestamp': timezone.now().isoformat(),
            }
    except httpx.TimeoutException:
        return {'codigo': codigo, 'encontrado': False, 'error': 'timeout'}
    except httpx.ConnectError:
        return {'codigo': codigo, 'encontrado': False, 'error': 'conexion'}
    except httpx.HTTPError as exc:
        return {'codigo': codigo, 'encontrado': False, 'error': str(exc)}


async def actualizar_estados_en_transito() -> list:
    """
    Verifica encomiendas en transito en paralelo y marca como entregadas
    las que la API externa reporte como DELIVERED.
    """
    encomiendas = await queryset_to_list(Encomienda.objects.en_transito())
    if not encomiendas:
        return []

    resultados = await asyncio.gather(
        *[verificar_estado_transportista(enc.codigo) for enc in encomiendas],
        return_exceptions=True,
    )

    actualizadas = []
    for enc, resultado in zip(encomiendas, resultados):
        if isinstance(resultado, Exception):
            continue
        if resultado.get('encontrado') and resultado.get('estado_ext') == 'DELIVERED':
            enc.estado = EstadoEnvio.ENTREGADO
            enc.fecha_entrega_real = timezone.now().date()
            await enc.asave()
            actualizadas.append(enc.codigo)

    return actualizadas


async def verificar_una(session: httpx.AsyncClient, codigo: str) -> dict:
    try:
        response = await session.get(
            TRANSPORTISTA_TRACKING_URL.format(codigo=codigo),
            timeout=5.0,
        )
        response.raise_for_status()
        return {'codigo': codigo, 'ok': True, 'data': response.json()}
    except httpx.TimeoutException:
        return {'codigo': codigo, 'ok': False, 'error': 'timeout'}
    except Exception as exc:
        return {'codigo': codigo, 'ok': False, 'error': str(exc)}


async def verificar_lote_completo() -> dict:
    """
    Verifica todas las encomiendas en transito concurrentemente usando
    una sola sesion HTTP compartida.
    """
    encomiendas = await queryset_to_list(Encomienda.objects.en_transito())
    if not encomiendas:
        return {'verificadas': 0, 'exitosas': 0, 'fallidas': 0, 'errores': 0, 'resultados': []}

    async with httpx.AsyncClient() as session:
        resultados = await asyncio.gather(
            *[verificar_una(session, enc.codigo) for enc in encomiendas],
            return_exceptions=True,
        )

    exitosas = [r for r in resultados if isinstance(r, dict) and r.get('ok')]
    fallidas = [r for r in resultados if isinstance(r, dict) and not r.get('ok')]
    errores = [r for r in resultados if isinstance(r, Exception)]

    return {
        'verificadas': len(encomiendas),
        'exitosas': len(exitosas),
        'fallidas': len(fallidas),
        'errores': len(errores),
        'resultados': resultados,
    }


async def verificar_con_timeout(enc) -> dict:
    try:
        return await asyncio.wait_for(
            verificar_estado_transportista(enc.codigo),
            timeout=3.0,
        )
    except asyncio.TimeoutError:
        return {
            'codigo': enc.codigo,
            'estado': enc.get_estado_display(),
            'fuente': 'cache_local',
            'advertencia': 'API del transportista no disponible',
        }


async def verificar_lote_con_timeout(codigos: list) -> list:
    encomiendas = await queryset_to_list(
        Encomienda.objects.filter(codigo__in=codigos)
    )
    resultados = await asyncio.gather(
        *[verificar_con_timeout(enc) for enc in encomiendas],
        return_exceptions=True,
    )
    return [
        resultado if not isinstance(resultado, Exception) else {'error': str(resultado)}
        for resultado in resultados
    ]
