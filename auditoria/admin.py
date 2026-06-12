from django.contrib import admin

from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin
from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('fecha', 'accion', 'modelo', 'objeto_id', 'usuario', 'descripcion', 'ip_address')
    list_filter = ('accion', 'modelo', 'fecha')
    search_fields = ('descripcion', 'usuario__email', 'modelo')
    readonly_fields = (
        'institucion', 'usuario', 'accion', 'modelo', 'objeto_id',
        'descripcion', 'valor_anterior', 'valor_nuevo', 'ip_address', 'fecha',
    )
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
