"""
Signals de auditoría para Calificacion, PagoRegistrado y Estudiante.

Utiliza threading.local() (via AuditoriaMiddleware) para obtener el usuario
que realiza el cambio y la IP del request sin necesidad de pasar esos datos
explícitamente por cada vista.
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .middleware import get_current_user, get_current_ip


# ---------------------------------------------------------------------------
# Caché de estado anterior (pre_save) para detectar cambios en ediciones
# ---------------------------------------------------------------------------

_estado_anterior = {}  # {(app_label, model_name, pk): dict_campos}


def _serializar_calificacion(obj):
    return {
        'valor_numerico': str(obj.valor_numerico) if obj.valor_numerico is not None else None,
        'valor_cualitativo': obj.valor_cualitativo,
        'observaciones': obj.observaciones,
    }


def _serializar_pago(obj):
    return {
        'valor_pagado': str(obj.valor_pagado),
        'metodo_pago': obj.metodo_pago,
        'fecha_pago': str(obj.fecha_pago),
        'referencia_transaccion': obj.referencia_transaccion,
        'observacion': obj.observacion,
        'anulado': obj.anulado,
        'anulado_motivo': obj.anulado_motivo,
    }


def _serializar_estudiante(obj):
    return {
        'activo': obj.activo,
        'grado_actual_id': obj.grado_actual_id,
        'valor_matricula': str(obj.valor_matricula),
        'valor_mensualidad': str(obj.valor_mensualidad),
        'documento_identidad': obj.documento_identidad,
        'codigo_estudiante': obj.codigo_estudiante,
    }


def _crear_registro(accion, modelo_nombre, objeto_id, descripcion,
                    institucion, valor_anterior=None, valor_nuevo=None):
    """Crea un RegistroAuditoria de forma segura, sin propagar excepciones."""
    try:
        from .models import RegistroAuditoria
        usuario = get_current_user()
        ip = get_current_ip()

        # Resolver usuario anónimo
        if usuario is not None and not getattr(usuario, 'is_authenticated', False):
            usuario = None

        RegistroAuditoria.objects.create(
            institucion=institucion,
            usuario=usuario,
            accion=accion,
            modelo=modelo_nombre,
            objeto_id=objeto_id,
            descripcion=descripcion,
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
            ip_address=ip,
        )
    except Exception:
        # Nunca interrumpir la operación principal por un fallo de auditoría
        pass


# ===========================================================================
# CALIFICACION
# ===========================================================================

@receiver(pre_save, sender='gestion_academica.Calificacion')
def calificacion_pre_save(sender, instance, **kwargs):
    """Guarda el estado anterior antes de una edición."""
    if instance.pk:
        try:
            anterior = sender.objects.get(pk=instance.pk)
            _estado_anterior[('gestion_academica', 'Calificacion', instance.pk)] = _serializar_calificacion(anterior)
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='gestion_academica.Calificacion')
def calificacion_post_save(sender, instance, created, **kwargs):
    clave = ('gestion_academica', 'Calificacion', instance.pk)
    anterior = _estado_anterior.pop(clave, None)
    nuevo = _serializar_calificacion(instance)

    # Nombre legible del estudiante y actividad
    try:
        nombre_est = instance.estudiante.usuario.get_full_name() or str(instance.estudiante.usuario)
        nombre_act = instance.actividad_calificable.titulo
    except Exception:
        nombre_est = f"ID {instance.estudiante_id}"
        nombre_act = f"Actividad ID {instance.actividad_calificable_id}"

    if created:
        accion = 'CREAR'
        valor_num = nuevo.get('valor_numerico') or nuevo.get('valor_cualitativo') or 'Pendiente'
        descripcion = f"Nota registrada para {nombre_est} en '{nombre_act}': {valor_num}"
    else:
        accion = 'EDITAR'
        val_ant = (anterior or {}).get('valor_numerico') or (anterior or {}).get('valor_cualitativo') or '—'
        val_nvo = nuevo.get('valor_numerico') or nuevo.get('valor_cualitativo') or '—'
        descripcion = f"Nota de {nombre_est} en '{nombre_act}' cambió de {val_ant} a {val_nvo}"

    _crear_registro(
        accion=accion,
        modelo_nombre='Calificacion',
        objeto_id=instance.pk,
        descripcion=descripcion,
        institucion=instance.institucion,
        valor_anterior=anterior,
        valor_nuevo=nuevo,
    )


@receiver(post_delete, sender='gestion_academica.Calificacion')
def calificacion_post_delete(sender, instance, **kwargs):
    try:
        nombre_est = instance.estudiante.usuario.get_full_name() or str(instance.estudiante.usuario)
        nombre_act = instance.actividad_calificable.titulo
    except Exception:
        nombre_est = f"ID {instance.estudiante_id}"
        nombre_act = f"Actividad ID {instance.actividad_calificable_id}"

    val = _serializar_calificacion(instance).get('valor_numerico') or \
          _serializar_calificacion(instance).get('valor_cualitativo') or '—'

    _crear_registro(
        accion='ELIMINAR',
        modelo_nombre='Calificacion',
        objeto_id=instance.pk,
        descripcion=f"Nota de {nombre_est} en '{nombre_act}' eliminada (valor: {val})",
        institucion=instance.institucion,
        valor_anterior=_serializar_calificacion(instance),
    )


# ===========================================================================
# PAGOREGISTRADO
# ===========================================================================

@receiver(pre_save, sender='finanzas.PagoRegistrado')
def pago_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            anterior = sender.objects.get(pk=instance.pk)
            _estado_anterior[('finanzas', 'PagoRegistrado', instance.pk)] = _serializar_pago(anterior)
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='finanzas.PagoRegistrado')
def pago_post_save(sender, instance, created, **kwargs):
    clave = ('finanzas', 'PagoRegistrado', instance.pk)
    anterior = _estado_anterior.pop(clave, None)
    nuevo = _serializar_pago(instance)

    try:
        nombre_est = instance.estudiante.usuario.get_full_name() or str(instance.estudiante.usuario)
    except Exception:
        nombre_est = f"Estudiante ID {instance.estudiante_id}"

    if created:
        accion = 'CREAR'
        descripcion = (
            f"Pago de ${instance.valor_pagado:.2f} registrado para {nombre_est} "
            f"— método: {instance.get_metodo_pago_display()}"
        )
    else:
        accion = 'EDITAR'
        val_ant = (anterior or {}).get('valor_pagado', '—')
        val_nvo = nuevo.get('valor_pagado', '—')
        # Detectar si es una anulación
        if nuevo.get('anulado') and not (anterior or {}).get('anulado'):
            descripcion = (
                f"Pago de {nombre_est} ANULADO "
                f"(valor: ${instance.valor_pagado:.2f}, motivo: {instance.anulado_motivo or '—'})"
            )
        else:
            descripcion = (
                f"Pago de {nombre_est} editado — "
                f"valor: ${val_ant} → ${val_nvo}"
            )

    _crear_registro(
        accion=accion,
        modelo_nombre='PagoRegistrado',
        objeto_id=instance.pk,
        descripcion=descripcion,
        institucion=instance.institucion,
        valor_anterior=anterior,
        valor_nuevo=nuevo,
    )


@receiver(post_delete, sender='finanzas.PagoRegistrado')
def pago_post_delete(sender, instance, **kwargs):
    try:
        nombre_est = instance.estudiante.usuario.get_full_name() or str(instance.estudiante.usuario)
    except Exception:
        nombre_est = f"Estudiante ID {instance.estudiante_id}"

    _crear_registro(
        accion='ELIMINAR',
        modelo_nombre='PagoRegistrado',
        objeto_id=instance.pk,
        descripcion=(
            f"Pago de {nombre_est} eliminado "
            f"(valor: ${instance.valor_pagado:.2f}, método: {instance.get_metodo_pago_display()})"
        ),
        institucion=instance.institucion,
        valor_anterior=_serializar_pago(instance),
    )


# ===========================================================================
# ESTUDIANTE (matrícula / estado)
# ===========================================================================

@receiver(pre_save, sender='gestion_academica.Estudiante')
def estudiante_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            anterior = sender.objects.get(pk=instance.pk)
            _estado_anterior[('gestion_academica', 'Estudiante', instance.pk)] = _serializar_estudiante(anterior)
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='gestion_academica.Estudiante')
def estudiante_post_save(sender, instance, created, **kwargs):
    clave = ('gestion_academica', 'Estudiante', instance.pk)
    anterior = _estado_anterior.pop(clave, None)
    nuevo = _serializar_estudiante(instance)

    try:
        nombre_est = instance.usuario.get_full_name() or str(instance.usuario)
    except Exception:
        nombre_est = f"Estudiante ID {instance.pk}"

    if created:
        accion = 'CREAR'
        descripcion = f"Estudiante {nombre_est} matriculado en la institución"
    else:
        accion = 'EDITAR'
        cambios = []
        if anterior:
            if anterior.get('activo') != nuevo.get('activo'):
                estado = "activado" if nuevo['activo'] else "desactivado/retirado"
                cambios.append(f"estado → {estado}")
            if anterior.get('grado_actual_id') != nuevo.get('grado_actual_id'):
                cambios.append(f"grado actualizado")
            if anterior.get('valor_matricula') != nuevo.get('valor_matricula'):
                cambios.append(
                    f"matrícula: ${anterior['valor_matricula']} → ${nuevo['valor_matricula']}"
                )
            if anterior.get('valor_mensualidad') != nuevo.get('valor_mensualidad'):
                cambios.append(
                    f"mensualidad: ${anterior['valor_mensualidad']} → ${nuevo['valor_mensualidad']}"
                )
        descripcion = f"Datos de {nombre_est} editados" + (
            f" ({', '.join(cambios)})" if cambios else ""
        )

    _crear_registro(
        accion=accion,
        modelo_nombre='Estudiante',
        objeto_id=instance.pk,
        descripcion=descripcion,
        institucion=instance.institucion,
        valor_anterior=anterior,
        valor_nuevo=nuevo,
    )


@receiver(post_delete, sender='gestion_academica.Estudiante')
def estudiante_post_delete(sender, instance, **kwargs):
    try:
        nombre_est = instance.usuario.get_full_name() or str(instance.usuario)
    except Exception:
        nombre_est = f"Estudiante ID {instance.pk}"

    _crear_registro(
        accion='ELIMINAR',
        modelo_nombre='Estudiante',
        objeto_id=instance.pk,
        descripcion=f"Estudiante {nombre_est} eliminado del sistema",
        institucion=instance.institucion,
        valor_anterior=_serializar_estudiante(instance),
    )
