# proyecto_colegio/middleware.py
import requests
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from django.urls import reverse # Necesario para resolver URLs por nombre
from django.conf import settings # Para acceder a STATIC_URL, MEDIA_URL
from django.contrib import messages
from django.contrib.auth import logout
from django.utils import translation
from django.utils.translation import gettext as _


class TurnstileMiddleware:
    """
    Verifica el desafío de Cloudflare Turnstile ("no soy un robot") en los
    formularios de login antes de que la vista procese la petición.

    Diseño:
    - Latente: si no hay claves configuradas (TURNSTILE_ENABLED=False), no hace
      absolutamente nada — el login funciona igual que sin este middleware.
    - Solo actúa sobre POST a las rutas de login declaradas en settings.
    - A prueba de caídas: si Cloudflare no responde, NO bloquea el acceso (el
      límite de intentos sigue protegiendo). Disponibilidad > rigidez para un
      colegio. Un token ausente o rechazado explícitamente sí bloquea.
    """
    SITEVERIFY = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (getattr(settings, 'TURNSTILE_ENABLED', False)
                and request.method == 'POST'
                and request.path in getattr(settings, 'TURNSTILE_LOGIN_PATHS', [])):
            if not self._verificar(request):
                messages.error(
                    request,
                    "No pudimos confirmar la verificación de seguridad. "
                    "Marca la casilla «No soy un robot» e inténtalo de nuevo.",
                )
                return redirect(request.get_full_path())
        return self.get_response(request)

    def _verificar(self, request):
        token = request.POST.get('cf-turnstile-response', '')
        if not token:
            return False
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
        try:
            resp = requests.post(self.SITEVERIFY, data={
                'secret': settings.TURNSTILE_SECRET_KEY,
                'response': token,
                'remoteip': ip,
            }, timeout=5)
            return bool(resp.json().get('success'))
        except Exception:
            # Cloudflare inaccesible: no dejamos a nadie por fuera del sistema.
            return True

class RedireccionRegistroInicialMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Rutas que DEBEN ser accesibles incluso si no hay usuarios registrados.
        EXCLUDED_PATHS = [
            reverse('gestion_academica:registro_inicial'), # La URL del formulario de registro inicial
            reverse('login'), # La URL de login estándar
            reverse('logout'), # La URL de logout estándar
            reverse('admin:index'), # El panel de administración
            
            # ¡CORRECCIÓN CLAVE AQUÍ! Usamos los nombres de URL directos (sin namespace)
            reverse('password_reset'),
            reverse('password_reset_done'),
            reverse('password_change'), 
            reverse('password_change_done'),
            # Las URLs de confirmación ('password_reset_confirm') y 'password_reset_complete'
            # tienen argumentos dinámicos (<uidb64>/<token>) que no se pueden usar con reverse() así.
            # Se excluyen por el prefijo '/accounts/' más abajo.
            # No las incluyas aquí directamente con reverse() sin argumentos.
        ]
        
        # Prefijos de URLs de autenticación o admin que también deberían ser excluidos
        # Esto capturará URLs como 'password_reset_confirm/<uidb64>/<token>/'
        AUTH_URL_PREFIXES = [
            '/accounts/', # Todas las URLs bajo /accounts/ (password_reset_confirm, etc.)
            '/admin/',    # Todas las URLs bajo /admin/
        ]
        
        current_path = request.path_info.split('?')[0] # Eliminar parámetros de query

        # Condición principal: Si no hay usuarios registrados
        if not get_user_model().objects.exists():
            # Y la ruta actual NO es una de las rutas excluidas explícitamente,
            # Y NO es una URL de archivos estáticos o de medios,
            # Y NO comienza con un prefijo de URL de autenticación o admin
            if current_path not in EXCLUDED_PATHS and \
               not current_path.startswith(settings.STATIC_URL) and \
               not current_path.startswith(settings.MEDIA_URL) and \
               not any(current_path.startswith(prefix) for prefix in AUTH_URL_PREFIXES):
                
                # Redirige al usuario al formulario de registro inicial
                return redirect('gestion_academica:registro_inicial') 
            
        response = self.get_response(request)
        return response
    

class InstitucionActivaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # El middleware no aplica para usuarios no autenticados o superusuarios
        if not request.user.is_authenticated or request.user.is_superuser:
            return self.get_response(request)

        # Excluimos las páginas de logout para evitar un bucle de redirección
        if request.path_info.startswith('/logout/') or request.path_info.startswith('/accounts/logout/'):
            return self.get_response(request)

        institucion = getattr(request.user, 'institucion_asociada', None)

        # Si el usuario tiene una institución y está marcada como NO activa
        if institucion and not institucion.activa:
            # Cerramos su sesión
            logout(request)
            # Le mostramos un mensaje claro
            messages.error(request, "El acceso para su institución ha sido suspendido. Por favor, contacte al administrador de la plataforma.")
            # Lo redirigimos a la página de login
            return redirect('login')

        # Si todo está en orden, la petición continúa normalmente
        return self.get_response(request)


# ── Secciones del portal del estudiante que se pueden bloquear ──────────────
# Cada institución elige (con casillas) cuáles se le ocultan a un estudiante con
# el acceso bloqueado manualmente. Lo NO marcado sigue disponible (p. ej. los
# deberes). El mapeo es por nombre de URL (resuelto con resolve()), no por ruta,
# para no romperse si cambian los paths.
SECCIONES_BLOQUEABLES = {
    'notas': {
        'label': 'Notas / Calificaciones',
        'url_names': {
            'mis_cursos_calificaciones',
            'detalle_mis_calificaciones_por_curso',
            'detalle_calificaciones_por_materia',
        },
    },
    'progreso': {
        'label': 'Progreso académico',
        'url_names': {'mi_progreso_academico'},
    },
    'boletin': {
        'label': 'Boletín',
        'url_names': {
            'mi_boletin_periodo_actual',
            'mi_boletin',
            'boletin_imprimible',
            'api_mi_boletin',
        },
    },
    'deberes': {
        'label': 'Deberes y Actividades',
        'url_names': {
            'mis_deberes_lista', 'realizar_entrega_deber', 'api_mis_deberes',
            'resolver_actividad',
        },
        'namespaces': {'cuestionarios'},   # evaluaciones/cuestionarios del docente
    },
    'simulacros': {
        'label': 'Simulacros Saber',
        'namespaces': {'simulacros'},   # se bloquea todo el módulo de simulacros
    },
}

# Preset por defecto (coincide con finanzas.models._default_bloqueo_secciones).
DEFAULT_SECCIONES_BLOQUEADAS = ['notas', 'progreso', 'boletin']


def secciones_bloqueables_choices():
    """[(key, label)] para pintar las casillas en la pantalla de bloqueos."""
    orden = ['notas', 'progreso', 'boletin', 'deberes', 'simulacros']
    return [(k, SECCIONES_BLOQUEABLES[k]['label']) for k in orden if k in SECCIONES_BLOQUEABLES]


def _seccion_de_match(resolver_match):
    """Devuelve la clave de sección bloqueable a la que pertenece la URL
    resuelta, o None si la URL no corresponde a ninguna sección bloqueable."""
    namespace = resolver_match.namespace
    url_name = resolver_match.url_name
    for key, cfg in SECCIONES_BLOQUEABLES.items():
        # Namespace(s) completos que pertenecen a la sección (ej. simulacros,
        # o cuestionarios dentro de «deberes»).
        if namespace and namespace in cfg.get('namespaces', ()):
            return key
        # URLs puntuales dentro de gestion_academica.
        if namespace == 'gestion_academica' and url_name in cfg.get('url_names', ()):
            return key
    return None


class BloqueoEstudianteMiddleware:
    """Limita el portal de un estudiante con ``acceso_bloqueado=True``.

    Bloqueo manual (ej. por no pago, gestionado por Secretaría): el estudiante
    SÍ inicia sesión y navega su portal con normalidad; solo se le **ocultan
    las secciones que su institución haya marcado** en la configuración de
    bloqueos (``InstitucionEducativa.bloqueo_secciones``; por defecto Notas,
    Progreso y Boletín). El resto del portal —incluidos los deberes— sigue
    disponible. En su dashboard ve el aviso rojo de suspensión.

    - Solo afecta al rol ``estudiante``. Otros roles y el superusuario pasan
      transparente.
    - Sección bloqueada, web → redirige al dashboard (donde se muestra el aviso).
    - Sección bloqueada, API móvil → 403 JSON, para no romper la app.
    - Secciones no marcadas → pasan transparente.
    """

    RUTAS_EXENTAS_PREFIJOS = (
        '/logout/',
        '/accounts/logout/',
        '/admin/',
        '/2fa/',
        '/academico/politica-datos/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (user.is_authenticated and not user.is_superuser
                and getattr(user, 'rol', '') == 'estudiante'):
            current_path = request.path_info
            exento = (
                current_path.startswith(self.RUTAS_EXENTAS_PREFIJOS)
                or current_path.startswith(settings.STATIC_URL)
                or current_path.startswith(settings.MEDIA_URL)
            )
            if not exento:
                estudiante = getattr(user, 'estudiante', None)
                if estudiante is not None and getattr(estudiante, 'acceso_bloqueado', False):
                    if self._seccion_bloqueada(request, estudiante):
                        if current_path.startswith('/academico/api/'):
                            from django.http import JsonResponse
                            return JsonResponse(
                                {'detail': 'Acceso suspendido. Contacta con administración.'},
                                status=403,
                            )
                        dashboard_url = reverse('gestion_academica:dashboard_estudiante')
                        if current_path != dashboard_url:
                            return redirect(dashboard_url)
        return self.get_response(request)

    def _seccion_bloqueada(self, request, estudiante):
        """True si la URL pedida cae en una sección que la institución del
        estudiante tiene marcada como bloqueada."""
        from django.urls import resolve, Resolver404
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return False
        seccion = _seccion_de_match(match)
        if seccion is None:
            return False
        institucion = getattr(estudiante, 'institucion', None)
        secciones = DEFAULT_SECCIONES_BLOQUEADAS
        if institucion is not None:
            valor = getattr(institucion, 'bloqueo_secciones', None)
            if isinstance(valor, list):
                secciones = valor
        return seccion in secciones


class ModuloFinancieroMiddleware:
    """Bloquea TODO el módulo de finanzas (prefijo ``/finanzas/``) para las
    instituciones que no lo tienen habilitado: públicas o con
    ``usa_modulo_financiero=False``.

    Cierra el hueco de que la mayoría de vistas de finanzas solo estaban
    protegidas por permiso: aunque un usuario tenga el permiso (p. ej. un rector
    con acceso amplio), si su institución no usa finanzas no puede entrar por
    URL. El superusuario pasa transparente y el webhook externo de Mercado Pago
    (petición sin usuario autenticado) también, para no romper los pagos de los
    colegios que sí usan finanzas.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith('/finanzas/'):
            user = getattr(request, 'user', None)
            if user is not None and user.is_authenticated and not user.is_superuser:
                inst = getattr(user, 'institucion_asociada', None)
                if inst and (inst.tipo_institucion == 'publico'
                             or not getattr(inst, 'usa_modulo_financiero', True)):
                    from django.shortcuts import render
                    return render(request, 'finanzas/acceso_no_disponible.html', status=403)
        return self.get_response(request)


class ModulosContratadosMiddleware:
    """Bloquea por URL los módulos que la institución del usuario NO tiene
    contratados en su plan (catálogo ``ModuloPlataforma`` +
    ``InstitucionEducativa.modulos_contratados``).

    Los prefijos a vigilar se leen del catálogo (campo ``prefijo_url``), así
    agregar o quitar un módulo se hace desde el admin, sin tocar código. El
    superusuario pasa transparente. Si el colegio no tiene el módulo, se muestra
    un mensaje amable y se redirige al inicio académico (no un error técnico).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and not user.is_superuser:
            path = request.path_info
            try:
                from finanzas.modulos import prefijos_bloqueables
                gated = prefijos_bloqueables()
            except Exception:
                gated = []
            for prefijo, codigo in gated:
                if prefijo and path.startswith(prefijo):
                    inst = getattr(user, 'institucion_asociada', None)
                    tiene = bool(inst) and inst.modulos_contratados.filter(
                        codigo=codigo, activo=True
                    ).exists()
                    if not tiene:
                        messages.warning(
                            request,
                            _("Tu institución no tiene contratado este módulo. Si te "
                              "interesa activarlo, contacta al administrador de la plataforma."),
                        )
                        return redirect('gestion_academica:inicio_academico')
                    break
        return self.get_response(request)


class IdiomaPreferidoMiddleware:
    """
    Activa el idioma preferido guardado en el perfil del usuario autenticado
    (Usuario.idioma_preferido) en cada petición, para que no dependa solo de
    la cookie de sesión o del idioma del navegador.

    Va después de LocaleMiddleware (que ya activó un idioma por defecto según
    la cookie/navegador) y después de AuthenticationMiddleware (necesita
    request.user). Ver docs/PLAN_MULTIIDIOMA.md.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            idioma = getattr(request.user, 'idioma_preferido', '') or ''
            if idioma:
                translation.activate(idioma)
                request.LANGUAGE_CODE = translation.get_language()
        return self.get_response(request)


class PoliticaDatosMiddleware:
    """
    Obliga a todo usuario autenticado a aceptar la Política de Tratamiento
    de Datos Personales vigente antes de usar el resto de la plataforma.

    Se activa en el primer login y, si se sube la versión de la política
    (gestion_academica.legal.POLITICA_TRATAMIENTO_DATOS_VERSION), vuelve a
    activarse para todos hasta que la re-acepten.

    No aplica a superusuarios (dueño de la plataforma) ni a /admin/, /api/,
    logout ni archivos estáticos/media, para no bloquear flujos técnicos.
    """

    RUTAS_EXENTAS_PREFIJOS = (
        '/academico/politica-datos/aceptar/',
        '/logout/',
        '/accounts/logout/',
        '/admin/',
        '/academico/api/',  # Endpoints de la app móvil — no se bloquean con una redirección HTML
        # Verificación 2FA (autenticacion_2fa.middleware.Verificacion2FAMiddleware):
        # si no se exceptúa, un usuario con 2FA activo que aún no acepta la
        # política queda en un bucle infinito 2fa -> política -> 2fa -> ...
        # (cada middleware redirige a la página del otro sin reconocerla).
        '/2fa/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._requiere_aceptacion(request):
            from urllib.parse import quote
            from django.urls import reverse
            return redirect(reverse('gestion_academica:aceptar_politica_datos') + f'?next={quote(request.path)}')
        return self.get_response(request)

    def _requiere_aceptacion(self, request):
        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return False

        current_path = request.path_info
        if current_path.startswith(self.RUTAS_EXENTAS_PREFIJOS) or \
           current_path.startswith(settings.STATIC_URL) or \
           current_path.startswith(settings.MEDIA_URL):
            return False

        from gestion_academica.legal import POLITICA_TRATAMIENTO_DATOS_VERSION
        return not (
            user.acepto_tratamiento_datos
            and user.version_politica_aceptada == POLITICA_TRATAMIENTO_DATOS_VERSION
        )