from django.contrib import admin

from .models import CredencialWebAuthn


@admin.register(CredencialWebAuthn)
class CredencialWebAuthnAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nombre_dispositivo', 'sign_count', 'creado_en', 'ultimo_uso')
    search_fields = ('usuario__username', 'usuario__email', 'nombre_dispositivo')
    readonly_fields = ('credential_id', 'public_key', 'sign_count', 'creado_en', 'ultimo_uso')
