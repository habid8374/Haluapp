# gestion_academica/views/politica_datos.py
"""Vistas para leer y aceptar la Política de Tratamiento de Datos Personales."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from gestion_academica.legal import (
    POLITICA_TRATAMIENTO_DATOS_SECCIONES,
    POLITICA_TRATAMIENTO_DATOS_VERSION,
    hash_politica_vigente,
)


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
