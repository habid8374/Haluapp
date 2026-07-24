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
