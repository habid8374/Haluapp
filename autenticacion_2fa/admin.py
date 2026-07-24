from django.contrib import admin

from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import DispositivoTOTP


@admin.register(DispositivoTOTP)
class DispositivoTOTPAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    """
    Gestión de dispositivos de verificación en dos pasos (2FA).

    El secreto TOTP (`secret`) nunca se muestra ni se edita aquí — quien
    tenga acceso a ese valor podría generar códigos válidos para siempre.
    Para "resetear" el 2FA de alguien que perdió su dispositivo/app
    autenticadora, desmarca "Confirmado" o elimina el registro: en ambos
    casos deja de pedirle el código en el próximo inicio de sesión (podrá
    configurar uno nuevo si quiere volver a activarlo).
    """
    institucion_lookup = 'usuario__institucion_asociada'
    list_display = ('usuario', 'confirmado', 'creado')
    list_filter = ('confirmado',)
    search_fields = ('usuario__username', 'usuario__email', 'usuario__first_name', 'usuario__last_name')
    fields = ('usuario', 'confirmado', 'creado')
    readonly_fields = ('usuario', 'creado')
    actions = ['deshabilitar_2fa']

    @admin.action(description="Deshabilitar 2FA (podrá configurar uno nuevo con un QR nuevo)")
    def deshabilitar_2fa(self, request, queryset):
        usuarios = list(queryset.values_list('usuario__username', flat=True))
        total = queryset.count()
        queryset.delete()
        self.message_user(
            request,
            f"2FA deshabilitado para {total} usuario(s): {', '.join(usuarios)}. "
            "Ya pueden iniciar sesión sin código, y si más adelante quieren "
            "activarlo de nuevo, la próxima vez que entren a configurar el 2FA "
            "verán un QR completamente nuevo.",
        )
