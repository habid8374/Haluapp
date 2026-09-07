from allauth.account.adapter import DefaultAccountAdapter


class NoPublicSignupAccountAdapter(DefaultAccountAdapter):
    """HALU es una plataforma B2B provisionada: los usuarios los crea el
    colegio (admisiones, coordinador, importación masiva) o el superadmin —
    nunca un desconocido desde internet. django-allauth expone por defecto
    /accounts/signup/ y deja crear cuentas activas sin ninguna aprobación.

    Bloquea esa alta pública. El adapter social de allauth
    (DefaultSocialAccountAdapter.is_open_for_signup) delega en este mismo
    método, así que esto también cierra el alta de una cuenta NUEVA vía
    "Iniciar sesión con Google" — sin afectar el login normal ni el login
    social de una cuenta que YA existe (eso no pasa por is_open_for_signup).
    """

    def is_open_for_signup(self, request):
        return False
