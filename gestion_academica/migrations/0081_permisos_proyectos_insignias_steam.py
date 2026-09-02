from django.db import migrations


# Permisos de Proyectos STEAM e Insignias (Fase 2 de Halu STEAM) para los
# grupos 'coordinadores' y 'docentes'. Mismo patrón que 0079
# (enfasis_permisos_coordinadores): asigna al Group, nunca por usuario.
#
# Coordinadores: control total (crean el catálogo de insignias, supervisan
# cualquier proyecto).
# Docentes: gestionan sus propios proyectos (hitos, equipos, evidencia) y
# pueden otorgar insignias ya existentes, pero NO crean/editan/eliminan el
# catálogo de insignias — eso lo define coordinación.
COORDINADORES_PERMISSIONS = [
    ('gestion_academica', 'proyectosteam', 'view_proyectosteam'),
    ('gestion_academica', 'proyectosteam', 'add_proyectosteam'),
    ('gestion_academica', 'proyectosteam', 'change_proyectosteam'),
    ('gestion_academica', 'proyectosteam', 'delete_proyectosteam'),
    ('gestion_academica', 'hitoproyecto', 'view_hitoproyecto'),
    ('gestion_academica', 'hitoproyecto', 'add_hitoproyecto'),
    ('gestion_academica', 'hitoproyecto', 'change_hitoproyecto'),
    ('gestion_academica', 'hitoproyecto', 'delete_hitoproyecto'),
    ('gestion_academica', 'participanteproyecto', 'view_participanteproyecto'),
    ('gestion_academica', 'participanteproyecto', 'add_participanteproyecto'),
    ('gestion_academica', 'participanteproyecto', 'change_participanteproyecto'),
    ('gestion_academica', 'participanteproyecto', 'delete_participanteproyecto'),
    ('gestion_academica', 'evidenciaproyecto', 'view_evidenciaproyecto'),
    ('gestion_academica', 'evidenciaproyecto', 'add_evidenciaproyecto'),
    ('gestion_academica', 'evidenciaproyecto', 'change_evidenciaproyecto'),
    ('gestion_academica', 'evidenciaproyecto', 'delete_evidenciaproyecto'),
    ('gestion_academica', 'insignia', 'view_insignia'),
    ('gestion_academica', 'insignia', 'add_insignia'),
    ('gestion_academica', 'insignia', 'change_insignia'),
    ('gestion_academica', 'insignia', 'delete_insignia'),
    ('gestion_academica', 'insigniaobtenida', 'view_insigniaobtenida'),
    ('gestion_academica', 'insigniaobtenida', 'add_insigniaobtenida'),
    ('gestion_academica', 'insigniaobtenida', 'change_insigniaobtenida'),
    ('gestion_academica', 'insigniaobtenida', 'delete_insigniaobtenida'),
]

DOCENTES_PERMISSIONS = [
    ('gestion_academica', 'proyectosteam', 'view_proyectosteam'),
    ('gestion_academica', 'proyectosteam', 'add_proyectosteam'),
    ('gestion_academica', 'proyectosteam', 'change_proyectosteam'),
    ('gestion_academica', 'proyectosteam', 'delete_proyectosteam'),
    ('gestion_academica', 'hitoproyecto', 'view_hitoproyecto'),
    ('gestion_academica', 'hitoproyecto', 'add_hitoproyecto'),
    ('gestion_academica', 'hitoproyecto', 'change_hitoproyecto'),
    ('gestion_academica', 'hitoproyecto', 'delete_hitoproyecto'),
    ('gestion_academica', 'participanteproyecto', 'view_participanteproyecto'),
    ('gestion_academica', 'participanteproyecto', 'add_participanteproyecto'),
    ('gestion_academica', 'participanteproyecto', 'change_participanteproyecto'),
    ('gestion_academica', 'participanteproyecto', 'delete_participanteproyecto'),
    ('gestion_academica', 'evidenciaproyecto', 'view_evidenciaproyecto'),
    ('gestion_academica', 'evidenciaproyecto', 'add_evidenciaproyecto'),
    ('gestion_academica', 'evidenciaproyecto', 'change_evidenciaproyecto'),
    ('gestion_academica', 'evidenciaproyecto', 'delete_evidenciaproyecto'),
    ('gestion_academica', 'insignia', 'view_insignia'),
    ('gestion_academica', 'insigniaobtenida', 'view_insigniaobtenida'),
    ('gestion_academica', 'insigniaobtenida', 'add_insigniaobtenida'),
]


def _get_permission(Permission, app_label, model, codename):
    try:
        return Permission.objects.get(
            content_type__app_label=app_label,
            content_type__model=model,
            codename=codename,
        )
    except Permission.DoesNotExist:
        return None


def _sincronizar(Group, Permission, nombre_grupo, lista_permisos, agregar):
    group, _ = Group.objects.get_or_create(name=nombre_grupo)
    perms = [
        _get_permission(Permission, app_label, model, codename)
        for app_label, model, codename in lista_permisos
    ]
    perms = [p for p in perms if p]
    if not perms:
        return
    if agregar:
        group.permissions.add(*perms)
    else:
        group.permissions.remove(*perms)


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    _sincronizar(Group, Permission, 'coordinadores', COORDINADORES_PERMISSIONS, agregar=True)
    _sincronizar(Group, Permission, 'docentes', DOCENTES_PERMISSIONS, agregar=True)


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    _sincronizar(Group, Permission, 'coordinadores', COORDINADORES_PERMISSIONS, agregar=False)
    _sincronizar(Group, Permission, 'docentes', DOCENTES_PERMISSIONS, agregar=False)


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0080_proyectos_insignias_steam'),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
