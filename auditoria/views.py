from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.http import Http404
from django.utils.dateparse import parse_date

from .models import RegistroAuditoria


def _get_institucion(request):
    return getattr(request.user, 'institucion_asociada', None)


@login_required
def historial_auditoria(request):
    """
    Historial de auditoría paginado.
    Accesible únicamente para coordinador, admin_institucion y superusuario.
    """
    cargo = getattr(request.user, 'cargo', None)
    if not (request.user.is_superuser or cargo in ('coordinador', 'admin_institucion')):
        raise Http404

    institucion = _get_institucion(request)

    if request.user.is_superuser:
        qs = RegistroAuditoria.objects.select_related('usuario', 'institucion').all()
    else:
        if institucion is None:
            qs = RegistroAuditoria.objects.none()
        else:
            qs = RegistroAuditoria.objects.select_related('usuario', 'institucion').filter(
                institucion=institucion
            )

    # --- Filtros ---
    modelo_filtro = request.GET.get('modelo', '').strip()
    accion_filtro = request.GET.get('accion', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    usuario_filtro = request.GET.get('usuario', '').strip()

    if modelo_filtro:
        qs = qs.filter(modelo=modelo_filtro)
    if accion_filtro:
        qs = qs.filter(accion=accion_filtro)
    if fecha_desde:
        fecha_desde_parsed = parse_date(fecha_desde)
        if fecha_desde_parsed:
            qs = qs.filter(fecha__date__gte=fecha_desde_parsed)
    if fecha_hasta:
        fecha_hasta_parsed = parse_date(fecha_hasta)
        if fecha_hasta_parsed:
            qs = qs.filter(fecha__date__lte=fecha_hasta_parsed)
    if usuario_filtro:
        qs = qs.filter(usuario__email__icontains=usuario_filtro)

    # --- Valores únicos para los selectores de filtro ---
    modelos_disponibles = ['Calificacion', 'PagoRegistrado', 'Estudiante']
    acciones_disponibles = RegistroAuditoria.ACCIONES

    # --- Paginación ---
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'modelos_disponibles': modelos_disponibles,
        'acciones_disponibles': acciones_disponibles,
        'modelo_filtro': modelo_filtro,
        'accion_filtro': accion_filtro,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'usuario_filtro': usuario_filtro,
        'total_registros': qs.count(),
    }
    return render(request, 'auditoria/historial.html', context)
