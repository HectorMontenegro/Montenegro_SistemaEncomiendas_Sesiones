# envios/views.py
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator

from django.views.decorators.http import require_POST
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .cart import Cart
from .models import OrdenServicio, ItemOrdenServicio, EstadoOrden

from .models import Encomienda, Empleado, HistorialEstado
from .forms import EncomiendaForm
from clientes.models import Cliente
from rutas.models import Ruta
from config.choices import EstadoEnvio


def resolver_empleado_para_usuario(user, fallback=None):
    """
    Obtiene el empleado asociado al usuario autenticado.
    Prioriza email y usa fallback para no cortar el flujo web.
    """
    empleado = None
    if getattr(user, 'email', None):
        empleado = Empleado.objects.filter(email=user.email).first()
    if empleado:
        return empleado
    return fallback


# ═══════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════

def login_view(request):
    """Vista de login personalizada"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    
    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    """Cerrar sesión"""
    logout(request)
    messages.info(request, 'Has cerrado sesión correctamente.')
    return redirect('login')


@login_required
def perfil_view(request):
    """Perfil del empleado"""
    try:
        empleado = Empleado.objects.get(email=request.user.email)
    except Empleado.DoesNotExist:
        empleado = None
    
    return render(request, 'accounts/perfil.html', {
        'empleado': empleado,
        'user': request.user,
    })


# ═══════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════

@login_required
def dashboard(request):
    """Vista principal con estadísticas"""
    hoy = timezone.now().date()
    stats = {
        'activas': Encomienda.objects.activas().count(),
        'en_transito': Encomienda.objects.en_transito().count(),
        'con_retraso': Encomienda.objects.con_retraso().count(),
        'entregadas_hoy': Encomienda.objects.filter(
            estado=EstadoEnvio.ENTREGADO,
            fecha_entrega_real=hoy
        ).count(),
    }
    
    context = {
        'total_activas': stats['activas'],
        'en_transito': stats['en_transito'],
        'con_retraso': stats['con_retraso'],
        'entregadas_hoy': stats['entregadas_hoy'],
        'ultimas': Encomienda.objects.con_relaciones()[:10],
        'stats': stats,
        'stats_cards': [
            ('Activas', stats['activas'], 'primary', 'shipping-fast', 'stat-activas'),
            ('En tránsito', stats['en_transito'], 'info', 'truck', 'stat-en-transito'),
            ('Con retraso', stats['con_retraso'], 'danger', 'exclamation-triangle', 'stat-retraso'),
            ('Entregadas hoy', stats['entregadas_hoy'], 'success', 'check-circle', 'stat-entregadas'),
        ],
    }
    return render(request, 'envios/dashboard.html', context)


# ═══════════════════════════════════════════════════════════════
# LISTADO Y BÚSQUEDA (CON PAGINACIÓN)
# ═══════════════════════════════════════════════════════════════

@login_required
def encomienda_lista(request):
    """Listado paginado con filtros y búsqueda"""
    qs = Encomienda.objects.con_relaciones()
    
    # Filtros GET
    estado = request.GET.get('estado', '')
    q = request.GET.get('q', '')
    
    if estado:
        qs = qs.filter(estado=estado)
    
    if q:
        qs = qs.filter(
            Q(codigo__icontains=q) |
            Q(remitente__apellidos__icontains=q) |
            Q(destinatario__apellidos__icontains=q) |
            Q(descripcion__icontains=q)
        )
    
    # Paginación: 15 registros por página
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page', 1)
    encomiendas = paginator.get_page(page_number)
    
    return render(request, 'envios/lista.html', {
        'encomiendas': encomiendas,
        'estados': EstadoEnvio.choices,
        'estado_activo': estado,
        'q': q,
    })


# ═══════════════════════════════════════════════════════════════
# DETALLE
# ═══════════════════════════════════════════════════════════════

@login_required
def encomienda_detalle(request, pk):
    """Detalle de encomienda con historial"""
    enc = get_object_or_404(
        Encomienda.objects.con_relaciones(),
        pk=pk
    )
    
    return render(request, 'envios/detalle.html', {
        'encomienda': enc,
        'historial': enc.historial.select_related('empleado').all(),
        'estados': EstadoEnvio.choices,
    })


# ═══════════════════════════════════════════════════════════════
# CREAR (PATRÓN GET/POST)
# ═══════════════════════════════════════════════════════════════

@login_required
def encomienda_crear(request):
    """Crear nueva encomienda"""
    if request.method == 'POST':
        form = EncomiendaForm(request.POST)
        if form.is_valid():
            enc = form.save(commit=False)  # No guardar aún
            
            # Asignar empleado que registra
            try:
                enc.empleado_registro = Empleado.objects.get(
                    email=request.user.email
                )
            except Empleado.DoesNotExist:
                messages.error(request, 'No tienes perfil de empleado asignado.')
                return render(request, 'envios/form.html', {'form': form, 'titulo': 'Nueva Encomienda'})
            
            enc.save()  # Ahora sí guardar (dispara save() del modelo con validaciones)
            messages.success(request, f'Encomienda {enc.codigo} registrada correctamente.')
            return redirect('encomienda_detalle', pk=enc.pk)
    else:
        form = EncomiendaForm()
    
    return render(request, 'envios/form.html', {
        'form': form,
        'titulo': 'Nueva Encomienda',
    })


# ═══════════════════════════════════════════════════════════════
# EDITAR
# ═══════════════════════════════════════════════════════════════

@login_required
def encomienda_editar(request, pk):
    """Editar encomienda existente"""
    enc = get_object_or_404(Encomienda, pk=pk)
    
    # Solo editable si está pendiente
    if enc.estado != EstadoEnvio.PENDIENTE:
        messages.warning(request, 'Solo se pueden editar encomiendas pendientes.')
        return redirect('encomienda_detalle', pk=pk)
    
    if request.method == 'POST':
        form = EncomiendaForm(request.POST, instance=enc)
        if form.is_valid():
            form.save()
            messages.success(request, f'Encomienda {enc.codigo} actualizada.')
            return redirect('encomienda_detalle', pk=pk)
    else:
        form = EncomiendaForm(instance=enc)
    
    return render(request, 'envios/form.html', {
        'form': form,
        'titulo': f'Editar {enc.codigo}',
        'encomienda': enc,
    })


# ═══════════════════════════════════════════════════════════════
# CAMBIAR ESTADO
# ═══════════════════════════════════════════════════════════════

from django.views.decorators.http import require_POST

@require_POST
@login_required
def encomienda_cambiar_estado(request, pk):
    """Cambiar estado de encomienda vía POST"""
    enc = get_object_or_404(Encomienda, pk=pk)
    nuevo_estado = request.POST.get('estado')
    observacion = request.POST.get('observacion', '')
    
    try:
        empleado = resolver_empleado_para_usuario(
            request.user,
            fallback=enc.empleado_registro
        )
        if not empleado:
            raise Empleado.DoesNotExist()
        enc.cambiar_estado(nuevo_estado, empleado, observacion)
        messages.success(
            request, 
            f'Estado actualizado a: {enc.get_estado_display()}'
        )
    except (ValueError, Empleado.DoesNotExist) as e:
        if isinstance(e, Empleado.DoesNotExist):
            messages.error(request, 'No existe un perfil de empleado para registrar el cambio de estado.')
        else:
            messages.error(request, str(e))
    
    return redirect('encomienda_detalle', pk=pk)


# ═══════════════════════════════════════════════════════════════
# ENDPOINT JSON (para AJAX)
# ═══════════════════════════════════════════════════════════════

from django.http import JsonResponse
from django.conf import settings
from django.db import connection
import redis

@login_required
def encomienda_estado_json(request, pk):
    """Endpoint AJAX para consultar estado"""
    enc = get_object_or_404(Encomienda, pk=pk)
    return JsonResponse({
        'codigo': enc.codigo,
        'estado': enc.estado,
        'display': enc.get_estado_display(),
        'retraso': enc.tiene_retraso,
        'dias': enc.dias_en_transito,
    })


def health_check(request):
    """
    Verifica PostgreSQL, Redis y el channel layer usado por WebSockets.
    """
    estado = {
        'postgres': False,
        'redis': False,
        'channels': False,
    }

    try:
        connection.ensure_connection()
        estado['postgres'] = True
    except Exception as exc:
        estado['postgres_error'] = str(exc)

    redis_client = None
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        redis_client.ping()
        info = redis_client.info()
        estado['redis'] = True
        estado['redis_memoria'] = info.get('used_memory_human')
        estado['redis_clientes'] = info.get('connected_clients')
        estado['redis_version'] = info.get('redis_version')
    except Exception as exc:
        estado['redis_error'] = str(exc)

    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'health_check',
            {'type': 'health.ping'}
        )
        estado['channels'] = True
    except Exception as exc:
        estado['channels_error'] = str(exc)

    try:
        redis_client = redis_client or redis.from_url(settings.REDIS_URL)
        estado['empleados_conectados'] = redis_client.scard(
            'encomiendas:group:encomiendas_global'
        )
    except Exception:
        estado['empleados_conectados'] = None

    todo_ok = all([estado['postgres'], estado['redis'], estado['channels']])
    return JsonResponse(estado, status=200 if todo_ok else 503)

# envios/views.py — AÑADIR al final del archivo existente

import uuid
from django.views.decorators.http import require_POST
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .cart import Cart
from .models import OrdenServicio, ItemOrdenServicio, EstadoOrden


# ═══════════════════════════════════════════════════════════════
# VISTAS DEL CARRITO
# ═══════════════════════════════════════════════════════════════

@login_required
def cart_detail(request):
    """Ver contenido del carrito de servicios"""
    cart = Cart(request)
    
    # Precargar objetos relacionados para mostrar nombres
    from clientes.models import Cliente
    from rutas.models import Ruta
    
    items_enriquecidos = []
    for item in cart:
        remitente = Cliente.objects.filter(pk=item.remitente_id).first()
        destinatario = Cliente.objects.filter(pk=item.destinatario_id).first()
        ruta = Ruta.objects.filter(pk=item.ruta_id).first()
        
        items_enriquecidos.append({
            'item': item,
            'remitente': remitente,
            'destinatario': destinatario,
            'ruta': ruta,
        })
    
    return render(request, 'cart/detail.html', {
        'cart': cart,
        'items': items_enriquecidos,
    })


@require_POST
@login_required
def cart_add(request):
    """
    Añade encomienda al carrito desde el formulario de creación.
    Se usa cuando el usuario quiere "seguir agregando" en lugar de guardar inmediatamente.
    """
    cart = Cart(request)
    
    # Datos del formulario POST
    item_data = {
        'temp_id': str(uuid.uuid4())[:8],
        'codigo': request.POST.get('codigo', ''),
        'descripcion': request.POST.get('descripcion', ''),
        'peso_kg': request.POST.get('peso_kg', 0),
        'volumen_cm3': request.POST.get('volumen_cm3') or None,
        'remitente_id': request.POST.get('remitente'),
        'destinatario_id': request.POST.get('destinatario'),
        'ruta_id': request.POST.get('ruta'),
        'costo_envio': request.POST.get('costo_envio', 0),
    }
    
    cart.add(item_data)
    messages.success(request, f'Encomienda {item_data["codigo"]} añadida al carrito.')
    return redirect('encomienda_crear')  # Volver a crear otra


@login_required
def cart_remove(request, temp_id):
    """Eliminar item del carrito"""
    cart = Cart(request)
    cart.remove(temp_id)
    messages.info(request, 'Encomienda eliminada del carrito.')
    return redirect('cart_detail')


@login_required
def cart_clear(request):
    """Vaciar carrito completo"""
    cart = Cart(request)
    cart.clear()
    messages.info(request, 'Carrito vaciado correctamente.')
    return redirect('cart_detail')


# ═══════════════════════════════════════════════════════════════
# CHECKOUT Y GENERACIÓN DE ORDEN
# ═══════════════════════════════════════════════════════════════

@login_required
def checkout(request):
    """Procesar carrito y generar orden de servicio"""
    cart = Cart(request)
    
    if len(cart) == 0:
        messages.warning(request, 'Tu carrito está vacío. Agrega encomiendas primero.')
        return redirect('cart_detail')
    
    # Obtener o crear cliente asociado al usuario
    from clientes.models import Cliente
    try:
        cliente = Cliente.objects.get(email=request.user.email)
    except Cliente.DoesNotExist:
        messages.error(request, 'No tienes un perfil de cliente. Contacta al administrador.')
        return redirect('cart_detail')
    
    if request.method == 'POST':
        try:
            # Crear la orden de servicio
            orden = OrdenServicio.objects.create(
                cliente=cliente,
                creado_por=request.user,
                cantidad_encomiendas=len(cart),
                peso_total_kg=cart.total_peso,
                costo_total=cart.total_costo,
                notas=request.POST.get('notas', ''),
            )
            
            # Crear items de la orden y encomiendas reales
            from .models import Encomienda, Empleado
            
            try:
                empleado = Empleado.objects.get(email=request.user.email)
            except Empleado.DoesNotExist:
                empleado = None
            
            for idx, item in enumerate(cart.get_items(), 1):
                # Crear encomienda real
                remitente = Cliente.objects.get(pk=item.remitente_id)
                destinatario = Cliente.objects.get(pk=item.destinatario_id)
                ruta = Ruta.objects.get(pk=item.ruta_id)
                
                encomienda = Encomienda.objects.create(
                    codigo=item.codigo,
                    descripcion=item.descripcion,
                    peso_kg=item.peso_kg,
                    volumen_cm3=item.volumen_cm3,
                    remitente=remitente,
                    destinatario=destinatario,
                    ruta=ruta,
                    empleado_registro=empleado,
                    costo_envio=item.costo_envio,
                    estado=EstadoEnvio.PENDIENTE,
                )
                
                # Crear item de orden
                ItemOrdenServicio.objects.create(
                    orden=orden,
                    encomienda=encomienda,
                    nro_item=idx,
                    codigo_encomienda=encomienda.codigo,
                    descripcion=encomienda.descripcion,
                    peso_kg=encomienda.peso_kg,
                    costo_envio=encomienda.costo_envio,
                )
            
            # Asignar empleado si existe
            if empleado:
                orden.empleado = empleado
                orden.save()
            
            # Vaciar carrito
            cart.clear()
            
            # Enviar email de confirmación
            try:
                send_order_confirmation_email(orden)
                messages.success(request, f'¡Orden {orden.nro_pedido} creada! Se envió confirmación por email.')
            except Exception as e:
                messages.success(request, f'¡Orden {orden.nro_pedido} creada! (Email no enviado: {str(e)})')
            
            return redirect('order_detail', pedido_id=orden.pedido_id)
            
        except Exception as e:
            messages.error(request, f'Error al procesar la orden: {str(e)}')
            return redirect('cart_detail')
    
    # GET: Mostrar formulario de checkout
    return render(request, 'cart/checkout.html', {
        'cart': cart,
        'cliente': cliente,
    })


@login_required
def order_detail(request, pedido_id):
    """Ver detalle de orden de servicio"""
    orden = get_object_or_404(
        OrdenServicio.objects.prefetch_related('items', 'items__encomienda'),
        pedido_id=pedido_id
    )
    
    # Verificar permisos
    if not request.user.is_staff and orden.cliente.email != request.user.email:
        messages.error(request, 'No tienes permiso para ver esta orden.')
        return redirect('dashboard')
    
    return render(request, 'cart/order_detail.html', {
        'orden': orden,
    })


@login_required
def order_list(request):
    """Listado de órdenes del usuario"""
    if request.user.is_staff:
        ordenes = OrdenServicio.objects.all().select_related('cliente')
    else:
        from clientes.models import Cliente
        try:
            cliente = Cliente.objects.get(email=request.user.email)
            ordenes = OrdenServicio.objects.filter(cliente=cliente).select_related('cliente')
        except Cliente.DoesNotExist:
            ordenes = OrdenServicio.objects.none()
    
    return render(request, 'cart/order_list.html', {
        'ordenes': ordenes,
    })


# ═══════════════════════════════════════════════════════════════
# EMAIL DE CONFIRMACIÓN
# ═══════════════════════════════════════════════════════════════

def send_order_confirmation_email(orden):
    """Envía email HTML de confirmación de orden"""
    subject = f'Confirmación de Orden #{orden.nro_pedido} - Encomiendas'
    from_email = 'Sistema Encomiendas <no-reply@encomiendas.pe>'
    to_email = orden.cliente.email
    
    # Renderizar HTML
    html_content = render_to_string('emails/order_confirmation.html', {
        'orden': orden,
        'items': orden.items.all(),
    })
    
    # Versión texto plano
    text_content = strip_tags(html_content)
    
    # Crear mensaje
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[to_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


# ═══════════════════════════════════════════════════════════════
# HISTORIAL DE NAVEGACIÓN (SESSION-BASED)
# ═══════════════════════════════════════════════════════════════

@login_required
def encomienda_detalle_mejorado(request, pk):
    """
    Vista de detalle que guarda historial de encomiendas vistas.
    Reemplaza la anterior o se usa como alternativa.
    """
    enc = get_object_or_404(Encomienda.objects.con_relaciones(), pk=pk)
    
    # Guardar en historial de sesión
    if 'viewed_encomiendas' not in request.session:
        request.session['viewed_encomiendas'] = []
    
    viewed = request.session['viewed_encomiendas']
    enc_id_str = str(enc.pk)
    
    # Eliminar si existe y añadir al principio (MRU)
    if enc_id_str in viewed:
        viewed.remove(enc_id_str)
    viewed.insert(0, enc_id_str)
    request.session['viewed_encomiendas'] = viewed[:5]  # Mantener últimas 5
    request.session.modified = True
    
    # Obtrar encomiendas recientes para sidebar
    recent_ids = [int(x) for x in viewed[:5] if x != enc_id_str]
    recientes = Encomienda.objects.filter(pk__in=recent_ids).select_related('remitente', 'ruta')[:4]
    
    return render(request, 'envios/detalle.html', {
        'encomienda': enc,
        'historial': enc.historial.select_related('empleado').all(),
        'recientes': recientes,
        'estados': EstadoEnvio.choices,
    })


# ═══════════════════════════════════════════════════════════════
# PAGINACIÓN INFINITA (API para AJAX)
# ═══════════════════════════════════════════════════════════════

from django.http import JsonResponse

@login_required
def api_encomiendas_list(request):
    """
    API JSON para paginación infinita con JavaScript.
    Endpoint: /api/encomiendas/?page=2&q=lima
    """
    qs = Encomienda.objects.con_relaciones()
    
    # Filtros
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(
            Q(codigo__icontains=q) |
            Q(remitente__apellidos__icontains=q)
        )
    
    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(qs, 10)  # 10 por página para AJAX
    page_number = request.GET.get('page', 1)
    page = paginator.get_page(page_number)
    
    # Serializar manualmente
    data = {
        'results': [
            {
                'id': enc.pk,
                'codigo': enc.codigo,
                'remitente': enc.remitente.nombre_completo,
                'destino': enc.ruta.destino,
                'estado': enc.get_estado_display(),
                'estado_code': enc.estado,
                'fecha': enc.fecha_registro.strftime('%d/%m/%Y'),
                'url': f'/encomiendas/{enc.pk}/',
            }
            for enc in page
        ],
        'has_next': page.has_next(),
        'next_page': page.next_page_number() if page.has_next() else None,
        'total': paginator.count,
    }
    
    return JsonResponse(data)
