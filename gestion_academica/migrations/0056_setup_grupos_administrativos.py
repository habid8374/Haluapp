from django.db import migrations


# --- Permisos por grupo administrativo ---------------------------------------
# Los roles administrativos NO necesitan is_staff: el acceso a Finanzas y
# Admisiones se resuelve por PERMISOS de Django (grupos), respetando el
# aislamiento multi-institución que ya aplican las vistas/mixins de esos
# módulos. Cada usuario ve únicamente los datos de SU institución.

# Tesorería / Financiera → módulo de finanzas completo (operativo).
TESORERIA_PERMISSIONS = [
    ('finanzas', 'institucioneducativa', 'acceso_modulo_finanzas'),
    # Pagos
    ('finanzas', 'pagoregistrado', 'view_pagoregistrado'),
    ('finanzas', 'pagoregistrado', 'add_pagoregistrado'),
    ('finanzas', 'pagoregistrado', 'change_pagoregistrado'),
    ('finanzas', 'pagoregistrado', 'puede_editar_pago'),
    # Cuentas por cobrar
    ('finanzas', 'cuentaporcobrarestudiante', 'view_cuentaporcobrarestudiante'),
    ('finanzas', 'cuentaporcobrarestudiante', 'add_cuentaporcobrarestudiante'),
    ('finanzas', 'cuentaporcobrarestudiante', 'change_cuentaporcobrarestudiante'),
    ('finanzas', 'cuentaporcobrarestudiante', 'ver_cuentas_por_cobrar'),
    # Conceptos de pago
    ('finanzas', 'conceptopago', 'view_conceptopago'),
    ('finanzas', 'conceptopago', 'add_conceptopago'),
    ('finanzas', 'conceptopago', 'change_conceptopago'),
    ('finanzas', 'conceptopago', 'delete_conceptopago'),
    ('finanzas', 'tipoconceptopago', 'view_tipoconceptopago'),
    ('finanzas', 'tipoconceptopago', 'add_tipoconceptopago'),
    ('finanzas', 'tipoconceptopago', 'change_tipoconceptopago'),
    # Descuentos
    ('finanzas', 'descuento', 'view_descuento'),
    ('finanzas', 'descuento', 'add_descuento'),
    ('finanzas', 'descuento', 'change_descuento'),
    ('finanzas', 'descuento', 'delete_descuento'),
    # Gastos / proveedores
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
    # Contabilidad (lectura para reportes/exportaciones)
    ('finanzas', 'cuentacontable', 'view_cuentacontable'),
    ('finanzas', 'itemcuenta', 'view_itemcuenta'),
]

# Secretaría → admisiones / matrícula / documentos.
SECRETARIAS_PERMISSIONS = [
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
    # Ver estudiantes (para matrícula/consulta), sin editar notas
    ('gestion_academica', 'estudiante', 'view_estudiante'),
]

# Rector(a) / Directivo → supervisión de solo lectura (KPIs y reportes).
RECTORES_PERMISSIONS = [
    ('finanzas', 'institucioneducativa', 'acceso_modulo_finanzas'),
    ('finanzas', 'pagoregistrado', 'view_pagoregistrado'),
    ('finanzas', 'cuentaporcobrarestudiante', 'view_cuentaporcobrarestudiante'),
    ('finanzas', 'cuentaporcobrarestudiante', 'ver_cuentas_por_cobrar'),
    ('finanzas', 'gasto', 'view_gasto'),
    ('finanzas', 'conceptopago', 'view_conceptopago'),
    ('finanzas', 'descuento', 'view_descuento'),
    ('admisiones', 'aspirante', 'view_aspirante'),
    ('admisiones', 'documentoentregado', 'view_documentoentregado'),
    ('gestion_academica', 'estudiante', 'view_estudiante'),
]


def _ensure_permissions_exist():
    """Crea (si faltan) los permisos de los modelos involucrados.

    Los permisos de modelo se generan normalmente en el signal post_migrate,
    que corre DESPUÉS de las migraciones. En una BD nueva podrían no existir aún
    cuando esta data-migration se ejecuta, así que los forzamos con el registro
    real de apps. Es idempotente y seguro sobre BDs ya migradas."""
    try:
        from django.apps import apps as global_apps
        from django.contrib.auth.management import create_permissions
    except Exception:
        return
    for app_label in ('finanzas', 'admisiones', 'gestion_academica', 'auth'):
        try:
            app_config = global_apps.get_app_config(app_label)
            create_permissions(app_config, verbosity=0)
        except Exception:
            # Si algo falla, seguimos: _get_permission simplemente omitirá los
            # permisos que no encuentre (mismo comportamiento que la 0039).
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


def setup_groups(apps, schema_editor):
    _ensure_permissions_exist()

    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    Usuario = apps.get_model('gestion_academica', 'Usuario')

    groups_config = [
        ('secretarias', 'secretaria', SECRETARIAS_PERMISSIONS),
        ('tesoreria', 'tesoreria', TESORERIA_PERMISSIONS),
        ('rectores', 'rector', RECTORES_PERMISSIONS),
    ]

    for group_name, rol, perms_list in groups_config:
        group, _ = Group.objects.get_or_create(name=group_name)

        perms_to_add = []
        for app_label, model, codename in perms_list:
            perm = _get_permission(Permission, app_label, model, codename)
            if perm:
                perms_to_add.append(perm)

        if perms_to_add:
            group.permissions.add(*perms_to_add)

        # Agregar los usuarios existentes con este rol al grupo
        usuarios = Usuario.objects.filter(rol=rol)
        if usuarios.exists():
            group.user_set.add(*usuarios)


def teardown_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in ('secretarias', 'tesoreria', 'rectores'):
        Group.objects.filter(name=name).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0055_usuario_roles_administrativos'),
        ('finanzas', '0006_institucioneducativa_acceso_modulo_finanzas'),
        ('admisiones', '0010_aspirante_apoyo_academico_especial_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(setup_groups, teardown_groups),
    ]
