# Fase C: política de bloqueo del portal del estudiante por mora.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0009_conceptopago_es_pago_pension'),
    ]

    operations = [
        migrations.AddField(
            model_name='institucioneducativa',
            name='bloquear_portal_por_mora',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Si está activo, los estudiantes con cuentas vencidas no podrán "
                    "acceder a deberes, actividades, calificaciones, lecciones, ni "
                    "boletín. Solo verán su estado de cartera con CTA para pagar."
                ),
                verbose_name="¿Bloquear portal del estudiante si tiene mensualidades vencidas?",
            ),
        ),
        migrations.AddField(
            model_name='institucioneducativa',
            name='dias_gracia_mora',
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Días de margen tras el vencimiento antes de bloquear el portal. "
                    "Ej: 3 → no se bloquea hasta 3 días después del vencimiento. "
                    "Solo aplica si 'bloquear_portal_por_mora' está activo."
                ),
                verbose_name="Días de gracia para mora",
            ),
        ),
    ]
