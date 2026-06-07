"""
mensajeria/admin.py
===================
Panel de administración para el módulo de mensajería directa.
Los coordinadores con el permiso `puede_supervisar_mensajes` pueden
ver todas las conversaciones de su institución.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Conversacion, Mensaje


class MensajeInline(admin.TabularInline):
    model = Mensaje
    fields = ('remitente', 'texto', 'enviado_en', 'leido', 'leido_en', 'adjunto')
    readonly_fields = ('enviado_en', 'leido_en')
    extra = 0
    ordering = ('enviado_en',)


@admin.register(Conversacion)
class ConversacionAdmin(admin.ModelAdmin):
    list_display = (
        '__str__', 'institucion', 'estudiante_contexto',
        'ultimo_mensaje_en', 'archivada_por_a', 'archivada_por_b',
    )
    list_filter = ('institucion', 'archivada_por_a', 'archivada_por_b')
    search_fields = (
        'participante_a__first_name', 'participante_a__last_name',
        'participante_a__username',
        'participante_b__first_name', 'participante_b__last_name',
        'participante_b__username',
    )
    raw_id_fields = ('participante_a', 'participante_b', 'estudiante_contexto', 'institucion')
    readonly_fields = ('creada_en', 'ultimo_mensaje_en')
    inlines = [MensajeInline]
    date_hierarchy = 'creada_en'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Supervisores solo ven su institución
        inst = getattr(request.user, 'institucion_asociada', None)
        if inst:
            return qs.filter(institucion=inst)
        return qs.none()

    def has_module_perms(self, request):
        return (
            request.user.is_superuser
            or request.user.has_perm('mensajeria.puede_supervisar_mensajes')
        )

    def has_delete_permission(self, request, obj=None):
        """Solo superusuario o administrador puede eliminar conversaciones."""
        if request.user.is_superuser:
            return True
        return getattr(request.user, 'rol', '') == 'administrador'


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('conversacion', 'remitente', 'texto_preview', 'enviado_en', 'leido')
    list_filter = ('leido', 'conversacion__institucion')
    search_fields = ('texto', 'remitente__username', 'remitente__first_name')
    readonly_fields = ('enviado_en', 'leido_en')
    raw_id_fields = ('conversacion', 'remitente')

    def texto_preview(self, obj):
        return obj.texto[:60] + ('…' if len(obj.texto) > 60 else '')
    texto_preview.short_description = 'Texto'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        inst = getattr(request.user, 'institucion_asociada', None)
        if inst:
            return qs.filter(conversacion__institucion=inst)
        return qs.none()

    def has_delete_permission(self, request, obj=None):
        """Solo superusuario o administrador puede eliminar mensajes."""
        if request.user.is_superuser:
            return True
        return getattr(request.user, 'rol', '') == 'administrador'
