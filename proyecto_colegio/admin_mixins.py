"""
Mixin multi-tenant para el Django admin.

REGLA CRÍTICA SAAS MULTI-INSTITUCIÓN: ningún usuario staff de un colegio
puede ver, editar ni crear registros de otra institución desde /admin/.
El superusuario (propietario de la plataforma) conserva acceso total.
"""


class InstitucionScopedAdminMixin:
    """
    Aplica aislamiento por institución a un ModelAdmin:

    1. `get_queryset`  → no-superusuarios solo ven registros de su institución.
    2. `formfield_for_foreignkey` → el dropdown de institución queda limitado
       a la institución del usuario (y preseleccionado).
    3. `save_model` → fuerza la institución del usuario al guardar, anulando
       cualquier manipulación del POST.

    Si el modelo no tiene FK directa `institucion`, definir en el ModelAdmin
    la ruta de filtrado, p. ej.:

        institucion_lookup = 'curso__institucion'

    Para el modelo Usuario usar:

        institucion_lookup = 'institucion_asociada'
    """

    institucion_lookup = 'institucion'

    def _institucion_usuario(self, request):
        return getattr(request.user, 'institucion_asociada', None)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        inst = self._institucion_usuario(request)
        if inst is None:
            return qs.none()
        return qs.filter(**{self.institucion_lookup: inst})

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and db_field.name in (
            'institucion', 'institucion_asociada'
        ):
            from finanzas.models import InstitucionEducativa
            inst = self._institucion_usuario(request)
            kwargs['queryset'] = (
                InstitucionEducativa.objects.filter(pk=inst.pk)
                if inst else InstitucionEducativa.objects.none()
            )
            if inst:
                kwargs['initial'] = inst
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Solo aplica cuando la institución es un campo directo del modelo.
        if not request.user.is_superuser and '__' not in self.institucion_lookup:
            inst = self._institucion_usuario(request)
            if inst is not None and hasattr(obj, f'{self.institucion_lookup}_id'):
                setattr(obj, self.institucion_lookup, inst)
        super().save_model(request, obj, form, change)


class SuperuserOnlyAdminMixin:
    """
    Restringe un ModelAdmin exclusivamente al superusuario
    (p. ej. InstitucionEducativa, configuración global de la plataforma).
    """

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
