from django.shortcuts import redirect
from django.urls import reverse


# Rutas que no requieren 2FA (evita bucle infinito)
_RUTAS_EXENTAS = frozenset([
    '/login/',
    '/accounts/logout/',
    '/2fa/verificar/',
    '/2fa/configurar/',
    '/2fa/qr/',
])

# Roles que DEBEN tener 2FA activo
_ROLES_OBLIGATORIOS = frozenset(['coordinador', 'admin_institucion', 'psicologo'])


class Verificacion2FAMiddleware:
    """
    Intercepta a coordinadores y admin_institucion que tienen 2FA configurado
    y confirmado, y los redirige al paso de verificación si no lo han completado
    en la sesión actual.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._requiere_verificacion(request):
            return redirect(reverse('2fa:verificar') + f'?next={request.path}')
        return self.get_response(request)

    def _requiere_verificacion(self, request):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return False
        # Solo aplica a rutas que no sean las de 2FA/login
        for ruta in _RUTAS_EXENTAS:
            if request.path.startswith(ruta):
                return False
        # Solo roles obligatorios
        cargo = getattr(user, 'cargo', None)
        if cargo not in _ROLES_OBLIGATORIOS:
            return False
        # Solo si tiene dispositivo TOTP confirmado
        try:
            disp = user.dispositivo_totp
            if not disp.confirmado:
                return False
        except Exception:
            return False
        # Solo si no ha verificado en esta sesión
        return not request.session.get('2fa_verificado', False)
