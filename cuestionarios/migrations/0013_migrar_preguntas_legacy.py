from django.db import migrations


# Consolidación del sistema de evaluaciones en UN solo lugar.
# Copia las preguntas del sistema viejo (gestion_academica.Pregunta / Opcion,
# ligadas a ActividadCalificable) al sistema nuevo (cuestionarios.Cuestionario
# / PreguntaCuestionario / OpcionPregunta). Es ADITIVA: no borra nada del
# sistema viejo, solo crea el cuestionario nuevo cuando la actividad aún no
# tiene uno, para que todo quede editable desde el editor unificado.

TIPO_MAP = {
    'opcion_multiple': 'opcion_multiple',
    'verdadero_falso': 'verdadero_falso',
    'respuesta_abierta': 'texto_libre',
}


def migrar_preguntas(apps, schema_editor):
    ActividadCalificable = apps.get_model('gestion_academica', 'ActividadCalificable')
    Pregunta = apps.get_model('gestion_academica', 'Pregunta')
    Cuestionario = apps.get_model('cuestionarios', 'Cuestionario')
    PreguntaCuestionario = apps.get_model('cuestionarios', 'PreguntaCuestionario')
    OpcionPregunta = apps.get_model('cuestionarios', 'OpcionPregunta')

    actividades_ids = list(
        Pregunta.objects.values_list('actividad_id', flat=True).distinct()
    )
    for act_id in actividades_ids:
        if act_id is None:
            continue
        try:
            act = ActividadCalificable.objects.get(pk=act_id)
        except ActividadCalificable.DoesNotExist:
            continue
        # No duplicar: si la actividad ya tiene cuestionario nuevo, se omite.
        if Cuestionario.objects.filter(actividad_calificable_id=act_id).exists():
            continue

        preguntas_viejas = list(
            Pregunta.objects.filter(actividad_id=act_id).order_by('orden', 'id')
        )
        if not preguntas_viejas:
            continue

        intentos = getattr(act, 'numero_intentos_permitidos', 1) or 1
        cuest = Cuestionario.objects.create(
            actividad_calificable_id=act_id,
            titulo=(act.titulo or 'Cuestionario')[:255],
            descripcion='',
            tiempo_limite=0,
            intentos_permitidos=min(int(intentos), 10),
            activo=True,
            mostrar_respuestas=False,
            institucion_id=act.institucion_id,
        )
        for i, pv in enumerate(preguntas_viejas):
            pc = PreguntaCuestionario.objects.create(
                cuestionario=cuest,
                enunciado=pv.enunciado or '',
                tipo=TIPO_MAP.get(pv.tipo, 'opcion_multiple'),
                puntaje=1,
                orden=i,
            )
            for j, ov in enumerate(pv.opciones.all().order_by('id')):
                OpcionPregunta.objects.create(
                    pregunta=pc,
                    texto=(ov.texto or '')[:500],
                    es_correcta=bool(ov.es_correcta),
                    orden=j,
                )


def revertir(apps, schema_editor):
    # No-op: no se borran los cuestionarios migrados para evitar pérdida de datos.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cuestionarios', '0012_alter_cuestionario_intentos_permitidos'),
        ('gestion_academica', '0065_seguimientoorientacion'),
    ]

    operations = [
        migrations.RunPython(migrar_preguntas, revertir),
    ]
