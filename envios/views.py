# envios/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator

from .models import Encomienda, Empleado, HistorialEstado
from .forms import EncomiendaForm
from clientes.models import Cliente
from rutas.models import Ruta
from config.choices import EstadoEnvio


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
    
    context = {
        'total_activas': Encomienda.objects.activas().count(),
        'en_transito': Encomienda.objects.en_transito().count(),
        'con_retraso': Encomienda.objects.con_retraso().count(),
        'entregadas_hoy': Encomienda.objects.filter(
            estado=EstadoEnvio.ENTREGADO,
            fecha_entrega_real=hoy
        ).count(),
        'ultimas': Encomienda.objects.con_relaciones()[:10],
        'stats': [
            ('Activas', Encomienda.objects.activas().count(), 'primary', 'shipping-fast'),
            ('En tránsito', Encomienda.objects.en_transito().count(), 'info', 'truck'),
            ('Con retraso', Encomienda.objects.con_retraso().count(), 'danger', 'exclamation-triangle'),
            ('Entregadas hoy', Encomienda.objects.filter(estado=EstadoEnvio.ENTREGADO, fecha_entrega_real=hoy).count(), 'success', 'check-circle'),
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
        empleado = Empleado.objects.get(email=request.user.email)
        enc.cambiar_estado(nuevo_estado, empleado, observacion)
        messages.success(
            request, 
            f'Estado actualizado a: {enc.get_estado_display()}'
        )
    except (ValueError, Empleado.DoesNotExist) as e:
        messages.error(request, str(e))
    
    return redirect('encomienda_detalle', pk=pk)


# ═══════════════════════════════════════════════════════════════
# ENDPOINT JSON (para AJAX)
# ═══════════════════════════════════════════════════════════════

from django.http import JsonResponse

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