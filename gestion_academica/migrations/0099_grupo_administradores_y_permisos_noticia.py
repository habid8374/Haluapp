from django.db import migrations


# Administrador(a) → el rol "dueño de la institución": hoy no tenía NINGÚN
# permiso de Django asignado (a diferencia de secretaria/tesoreria/rector/
# psicologo, que sí tienen su grupo desde las migraciones 0056/0061). En la
# práctica, es frecuente que en colegios pequeños una sola persona con este
# rol haga las veces de secretaría Y tesorería a la vez. Este grupo le da
# ambos conjuntos de permisos (unión de TESORERIA_PERMISSIONS y
# SECRETARIAS_PERMISSIONS de la migración 0056, más comunicados/Noticia).
ADMINISTRADORES_PERMISSIONS = [
    # --- Finanzas (igual a TESORERIA_PERMISSIONS en 0056) ---
    ('finanzas', 'institucioneducativa', 'acceso_modulo_finanzas'),
    ('finanzas', 'pagoregistrado', 'view_pagoregistrado'),
    ('finanzas', 'pagoregistrado', 'add_pagoregistrado'),
    ('finanzas', 'pagoregistrado', 'change_pagoregistrado'),
    ('finanzas', 'pagoregistrado', 'puede_editar_pago'),
    ('finanzas', 'cuentaporcobrarestudiante', 'view_cuentaporcobrarestudiante'),
    ('finanzas', 'cuentaporcobrarestudiante', 'add_cuentaporcobrarestudiante'),
    ('finanzas', 'cuentaporcobrarestudiante', 'change_cuentaporcobrarestudiante'),
    ('finanzas', 'cuentaporcobrarestudiante', 'ver_cuentas_por_cobrar'),
    ('finanzas', 'conceptopago', 'view_conceptopago'),
    ('finanzas', 'conceptopago', 'add_conceptopago'),
    ('finanzas', 'conceptopago', 'change_conceptopago'),
    ('finanzas', 'conceptopago', 'delete_conceptopago'),
    ('finanzas', 'tipoconceptopago', 'view_tipoconceptopago'),
    ('finanzas', 'tipoconceptopago', 'add_tipoconceptopago'),
    ('finanzas', 'tipoconceptopago', 'change_tipoconceptopago'),
    ('finanzas', 'descuento', 'view_descuento'),
    ('finanzas', 'descuento', 'add_descuento'),
    ('finanzas', 'descuento', 'change_descuento'),
    ('finanzas', 'descuento', 'delete_descuento'),
    ('finanzas', 'gasto', 'view_gasto'),
    ('finanzas', 'gasto', 'add_gasto'),
    ('finanzas', 'gasto', 'change_gasto'),
    ('finanzas', 'gasto', 'delete_gasto'),
    ('finanzas', 'categoriagasto', 'view_categoriagasto'),
    ('finanzas', 'categoriagasto', 'add_categoriagasto'),
    ('finanzas', 'categoriagasto', 'change_categoriagasto'),
    ('finanzas', 'proveedor', 'view_proveedor'),
    ('finanzas', 'proveedor', 'add_proveedor'),
    ('finanzas', 'proveedor', 'change_proveedor'),
    ('finanzas', 'cuentacontable', 'view_cuentacontable'),
    ('finanzas', 'itemcuenta', 'view_itemcuenta'),
    # --- Secretaría / admisiones (igual a SECRETARIAS_PERMISSIONS en 0056) ---
    ('admisiones', 'aspirante', 'view_aspirante'),
    ('admisiones', 'aspirante', 'add_aspirante'),
    ('admisiones', 'aspirante', 'change_aspirante'),
    ('admisiones', 'aspirante', 'delete_aspirante'),
    ('admisiones', 'documentoentregado', 'view_documentoentregado'),
    ('admisiones', 'documentoentregado', 'add_documentoentregado'),
    ('admisiones', 'documentoentregado', 'change_documentoentregado'),
    ('admisiones', 'documentorequerido', 'view_documentorequerido'),
    ('admisiones', 'documentorequerido', 'add_documentorequerido'),
    ('admisiones', 'documentorequerido', 'change_documentorequerido'),
    ('admisiones', 'horariodisponible', 'view_horariodisponible'),
    ('admisiones', 'horariodisponible', 'add_horariodisponible'),
    ('admisiones', 'horariodisponible', 'change_horariodisponible'),
    ('admisiones', 'citaagendada', 'view_citaagendada'),
    ('admisiones', 'citaagendada', 'add_citaagendada'),
    ('admisiones', 'citaagendada', 'change_citaagendada'),
    ('admisiones', 'loteimportacionaspirantes', 'view_loteimportacionaspirantes'),
    ('admisiones', 'loteimportacionaspirantes', 'add_loteimportacionaspirantes'),
    ('admisiones', 'loteimportacionaspirantes', 'change_loteimportacionaspirantes'),
    ('gestion_academica', 'estudiante', 'view_estudiante'),
    # --- Comunicados (Noticia) — ver más abajo, ningún grupo los tenía ---
    ('gestion_academica', 'noticia', 'view_noticia'),
    ('gestion_academica', 'noticia', 'add_noticia'),
    ('gestion_academica', 'noticia', 'change_noticia'),
    ('gestion_academica', 'noticia', 'delete_noticia'),
]

# Comunicados a padres/docentes (Noticia): estas vistas existen desde hace
# tiempo (NoticiaCreateView/UpdateView/DeleteView/GestionListView) pero
# ningún grupo tenía sus permisos — nadie sin is_superuser podía usarlas.
# Se agregan aquí a coordinadores (dueño natural del feature) además de a
# administradores (arriba).
NOTICIA_PERMISSIONS = [
    ('gestion_academica', 'noticia', 'view_noticia'),
    ('gestion_academica', 'noticia', 'add_noticia'),
    ('gestion_academica', 'noticia', 'change_noticia'),
    ('gestion_academica', 'noticia', 'delete_noticia'),
]


def _ensure_permissions_exist():
    try:
        from django.apps import apps as global_apps
        from django.contrib.auth.management import create_permissions
    except Exception:
        return
    for app_label in ('finanzas', 'admisiones', 'gestion_academica', 'auth'):
        try:
            create_permissions(global_apps.get_app_config(app_label), verbosity=0)
        except Exception:
            pass


def _get_permission(Permission, app_label, model, codename):
    try:
        return Permission.objects.get(
            content_type__app_label=app_label,
            content_type__model=model,
            codename=codename,
        )
    except Permission.DoesNotExist:
        return None


def setup_group(apps, schema_editor):
    _ensure_permissions_exist()

    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    Usuario = apps.get_model('gestion_academica', 'Usuario')

    group, _ = Group.objects.get_or_create(name='administradores')
    perms = [
        p for (a, m, c) in ADMINISTRADORES_PERMISSIONS
        if (p := _get_permission(Permission, a, m, c)) is not None
    ]
    if perms:
        group.permissions.add(*perms)

    # Backfill: todos los usuarios administrador ya existentes entran al
    # grupo ahora mismo (el signal solo actúa en post_save futuros).
    usuarios = Usuario.objects.filter(rol='administrador')
    if usuarios.exists():
        group.user_set.add(*usuarios)

    # Comunicados también para coordinadores (grupo ya existe desde 0039).
    try:
        coordinadores = Group.objects.get(name='coordinadores')
    except Group.DoesNotExist:
        coordinadores = None
    if coordinadores:
        noticia_perms = [
            p for (a, m, c) in NOTICIA_PERMISSIONS
            if (p := _get_permission(Permission, a, m, c)) is not None
        ]
        if noticia_perms:
            coordinadores.permissions.add(*noticia_perms)


def teardown_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    Group.objects.filter(name='administradores').delete()
    try:
        coordinadores = Group.objects.get(name='coordinadores')
    except Group.DoesNotExist:
        coordinadores = None
    if coordinadores:
        noticia_perms = [
            p for (a, m, c) in NOTICIA_PERMISSIONS
            if (p := _get_permission(Permission, a, m, c)) is not None
        ]
        if noticia_perms:
            coordinadores.permissions.remove(*noticia_perms)


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0098_asignacionsimulacionsteam_actividad_calificable'),
        ('finanzas', '0006_institucioneducativa_acceso_modulo_finanzas'),
        ('admisiones', '0010_aspirante_apoyo_academico_especial_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(setup_group, teardown_group),
    ]
