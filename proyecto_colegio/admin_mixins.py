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

    # Campos de "autor" que se autocompletan con el usuario en sesión.
    CAMPOS_AUTOR = ('creado_por', 'registrado_por', 'publicado_por', 'generado_por')

    def _institucion_usuario(self, request):
        return getattr(request.user, 'institucion_asociada', None)

    def get_exclude(self, request, obj=None):
        """Para no-superusuarios oculta del formulario la institución y los
        campos de autor: se asignan solos en save_model (la institución del
        usuario y el usuario en sesión), así no hay desplegables que confundan
        ni que puedan tocar. El superusuario sí los ve. No se oculta un campo
        que el admin liste explícitamente en fields/fieldsets."""
        base = tuple(super().get_exclude(request, obj) or ())
        if request.user.is_superuser:
            return base or None

        ocultar = []
        if '__' not in self.institucion_lookup:
            ocultar.append(self.institucion_lookup)
        model_fields = {f.name for f in self.model._meta.fields}
        ocultar += [c for c in self.CAMPOS_AUTOR if c in model_fields]

        explicit = set(self.fields or ())
        for _n, opts in (self.fieldsets or ()):
            explicit |= set(opts.get('fields') or ())

        exclude = list(base)
        for c in ocultar:
            if c not in exclude and c not in explicit:
                exclude.append(c)
        return tuple(exclude) or None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        inst = self._institucion_usuario(request)
        if inst is None:
            return qs.none()
        return qs.filter(**{self.institucion_lookup: inst})

    def get_list_filter(self, request):
        """Oculta el filtro por institución a los no-superusuarios.

        El `list_filter` de institución renderiza en la barra lateral los
        NOMBRES de todas las instituciones (Django lista todos los objetos
        relacionados, no solo los del queryset ya acotado), filtrando así datos
        de OTROS colegios. Un admin de una sola institución no necesita ese
        filtro; se lo quitamos para no exponer la existencia/nombre de otras
        instituciones. El superusuario conserva el filtro completo."""
        list_filter = super().get_list_filter(request)
        if request.user.is_superuser:
            return list_filter
        return tuple(
            f for f in list_filter
            if f not in ('institucion', 'institucion_asociada')
        )

    @staticmethod
    def _campo_institucion_de(model):
        """Devuelve el nombre del campo de institución del modelo dado
        ('institucion' o 'institucion_asociada'), o None si es un modelo global
        (sin institución: p. ej. ContentType, tablas de referencia)."""
        nombres = {f.name for f in model._meta.fields}
        if 'institucion' in nombres:
            return 'institucion'
        if 'institucion_asociada' in nombres:
            return 'institucion_asociada'
        return None

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Acota TODOS los desplegables FK a la institución del usuario.

        Antes solo se acotaba el campo 'institucion'. Eso dejaba fugar cualquier
        otra FK a un modelo con institución (p. ej. «Creado por» → Usuario, o FKs
        a Estudiante, Materia, Grado…), mostrando registros de OTROS colegios.
        Ahora, para no-superusuarios, se filtra el queryset de cada FK cuyo modelo
        relacionado tenga institución; los modelos globales se dejan intactos."""
        if not request.user.is_superuser:
            inst = self._institucion_usuario(request)
            related = db_field.related_model
            campo = self._campo_institucion_de(related)
            if campo is not None:
                if inst is not None:
                    kwargs['queryset'] = related._default_manager.filter(**{campo: inst})
                else:
                    kwargs['queryset'] = related._default_manager.none()
                # Preseleccionar la propia institución en el campo institución.
                if db_field.name in ('institucion', 'institucion_asociada') and inst is not None:
                    kwargs['initial'] = inst
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Igual que arriba pero para relaciones M2M (widgets de selección
        múltiple), que también podían listar registros de otros colegios."""
        if not request.user.is_superuser:
            inst = self._institucion_usuario(request)
            related = db_field.related_model
            campo = self._campo_institucion_de(related)
            if campo is not None:
                kwargs['queryset'] = (
                    related._default_manager.filter(**{campo: inst})
                    if inst is not None else related._default_manager.none()
                )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # 1) Forzar la institución del usuario (si el modelo la tiene directa).
        if not request.user.is_superuser and '__' not in self.institucion_lookup:
            inst = self._institucion_usuario(request)
            if inst is not None and hasattr(obj, f'{self.institucion_lookup}_id'):
                setattr(obj, self.institucion_lookup, inst)
        # 2) Autocompletar «creado por / registrado por» con el usuario en sesión
        #    (si el modelo tiene ese campo y está vacío), en vez de un desplegable.
        for campo_autor in self.CAMPOS_AUTOR:
            if hasattr(obj, f'{campo_autor}_id') and not getattr(obj, f'{campo_autor}_id'):
                setattr(obj, campo_autor, request.user)
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
