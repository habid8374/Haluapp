# gestion_academica/views/politica_datos.py
"""Vistas para leer y aceptar la Política de Tratamiento de Datos Personales."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from xhtml2pdf import pisa

from gestion_academica.legal import (
    POLITICA_TRATAMIENTO_DATOS_SECCIONES,
    POLITICA_TRATAMIENTO_DATOS_VERSION,
    hash_politica_vigente,
)
from ._main import link_callback


def _es_coordinador_o_admin(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('coordinador', 'administrador') or user.is_superuser


def _ip_cliente(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _next_seguro(request, valor):
    """Evita redirecciones abiertas: solo se sigue `next` si apunta a este mismo sitio."""
    if valor and url_has_allowed_host_and_scheme(valor, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return valor
    return None


def ver_politica_datos(request):
    """Lectura pública de la política — accesible sin sesión iniciada
    (visible desde el pie de página y desde el login)."""
    return render(request, 'gestion_academica/politica_datos.html', {
        'secciones': POLITICA_TRATAMIENTO_DATOS_SECCIONES,
        'version': POLITICA_TRATAMIENTO_DATOS_VERSION,
        'modo_aceptacion': False,
    })


@login_required
def aceptar_politica_datos(request):
    """Pantalla obligatoria de aceptación. Redirige a `next` (o al inicio)
    una vez el usuario marca la casilla y confirma."""
    user = request.user
    version_vigente = POLITICA_TRATAMIENTO_DATOS_VERSION
    ya_al_dia = (
        user.acepto_tratamiento_datos
        and user.version_politica_aceptada == version_vigente
    )

    if request.method == 'POST':
        siguiente = _next_seguro(request, request.POST.get('next') or request.GET.get('next'))
        if request.POST.get('acepto') != 'si':
            messages.error(
                request,
                "Debes marcar la casilla de aceptación para continuar usando la plataforma.",
            )
            return redirect(request.get_full_path())

        user.acepto_tratamiento_datos = True
        user.fecha_aceptacion_tratamiento_datos = timezone.now()
        user.version_politica_aceptada = version_vigente
        user.hash_politica_aceptada = hash_politica_vigente()
        user.ip_aceptacion_politica = _ip_cliente(request)
        user.user_agent_aceptacion_politica = request.META.get('HTTP_USER_AGENT', '')[:1000]
        user.save(update_fields=[
            'acepto_tratamiento_datos',
            'fecha_aceptacion_tratamiento_datos',
            'version_politica_aceptada',
            'hash_politica_aceptada',
            'ip_aceptacion_politica',
            'user_agent_aceptacion_politica',
        ])
        messages.success(request, "Gracias — quedó registrada tu aceptación de la política de tratamiento de datos.")
        return redirect(siguiente or 'gestion_academica:inicio_academico')

    if ya_al_dia:
        # Ya está al día (llegó aquí por un enlace viejo o marcador) — no lo
        # detenemos con el formulario, lo dejamos seguir su camino.
        return redirect(_next_seguro(request, request.GET.get('next')) or 'gestion_academica:inicio_academico')

    return render(request, 'gestion_academica/politica_datos.html', {
        'secciones': POLITICA_TRATAMIENTO_DATOS_SECCIONES,
        'version': version_vigente,
        'modo_aceptacion': True,
        'next': request.GET.get('next', ''),
    })


@login_required
def reporte_aceptacion_politica(request):
    """Reporte visible para coordinador/administrador: quién ha aceptado la
    política vigente y quién sigue pendiente — reemplaza tener que entrar
    usuario por usuario en el admin de Django."""
    if not _es_coordinador_o_admin(request.user):
        raise PermissionDenied

    from gestion_academica.models import Usuario

    version_vigente = POLITICA_TRATAMIENTO_DATOS_VERSION
    es_superuser = request.user.is_superuser
    usuarios = Usuario.objects.exclude(is_superuser=True).select_related('institucion_asociada')
    if not es_superuser:
        institucion = getattr(request.user, 'institucion_asociada', None)
        usuarios = usuarios.filter(institucion_asociada=institucion) if institucion else usuarios.none()
    usuarios = usuarios.order_by('first_name', 'last_name')

    total = usuarios.count()
    al_dia = usuarios.filter(
        acepto_tratamiento_datos=True,
        version_politica_aceptada=version_vigente,
    ).count()
    pendientes = total - al_dia
    porcentaje = round((al_dia / total * 100), 1) if total else 0

    return render(request, 'gestion_academica/reportes/aceptacion_politica_datos.html', {
        'titulo_pagina': 'Aceptación de Política de Datos',
        'usuarios': usuarios,
        'total': total,
        'al_dia': al_dia,
        'pendientes': pendientes,
        'porcentaje': porcentaje,
        'version_vigente': version_vigente,
        'es_superuser': es_superuser,
    })


@login_required
def constancia_aceptacion_politica(request, usuario_id=None):
    """Constancia en PDF (imprimible/descargable) de que un usuario aceptó
    la política de tratamiento de datos — sirve como prueba formal ante una
    solicitud del titular (art. 8 Ley 1581 de 2012) sin tener que entrar al
    admin. Sin `usuario_id` genera la propia (autoservicio desde "Mi
    perfil"); con `usuario_id`, solo coordinador/administrador de la misma
    institución (o superusuario) puede generarla para otro usuario."""
    from gestion_academica.models import Usuario

    if usuario_id is None:
        objetivo = request.user
    else:
        objetivo = get_object_or_404(Usuario, pk=usuario_id)
        if objetivo.pk != request.user.pk:
            if not _es_coordinador_o_admin(request.user):
                raise PermissionDenied
            if not request.user.is_superuser:
                institucion = getattr(request.user, 'institucion_asociada', None)
                if not institucion or objetivo.institucion_asociada_id != institucion.id:
                    raise PermissionDenied

    if not objetivo.acepto_tratamiento_datos:
        messages.error(request, "Este usuario todavía no ha aceptado la política de tratamiento de datos — no hay constancia que generar.")
        if usuario_id is None:
            return redirect('gestion_academica:ver_mi_perfil')
        return redirect('gestion_academica:reporte_aceptacion_politica')

    from django.conf import settings

    template = get_template('gestion_academica/constancia_aceptacion_politica.html')
    html = template.render({
        'objetivo': objetivo,
        'fecha_generacion': timezone.now(),
        'logo_url': getattr(settings, 'SOFTWARE_LOGO_URL', 'core/img/logo_mi_software.png'),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Constancia_Aceptacion_Politica_{objetivo.username}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF. Por favor, inténtelo de nuevo.', status=500)
    return response
