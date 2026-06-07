import os, sys
_base = os.path.dirname(os.path.abspath(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto_colegio.settings')
import django; django.setup()

from finanzas.models import CuentaPorCobrarEstudiante

print("%-6s  %-38s  %-10s  %-10s  %-10s  %s" % (
    "ID", "CONCEPTO", "MONTO", "ESTADO", "ASPIRANTE", "VIA_ESTUDIANTE"))
print("-" * 110)

cuentas = CuentaPorCobrarEstudiante.objects.select_related(
    'concepto_pago', 'aspirante', 'estudiante__aspirante_origen', 'institucion'
).filter(institucion_id=1).order_by('id')

for c in cuentas:
    asp_directo = c.aspirante
    via_est     = None
    if c.estudiante_id:
        via_est = getattr(c.estudiante, 'aspirante_origen', None)

    if asp_directo:
        asp_info = str(asp_directo)[:20]
        via      = "DIRECTO"
    elif via_est:
        asp_info = str(via_est)[:20]
        via      = "VIA_ESTUDIANTE"
    else:
        asp_info = "[SIN ASPIRANTE]"
        via      = "NINGUNA"

    token = ""
    if asp_directo:
        token = str(asp_directo.access_token)
    elif via_est:
        token = str(via_est.access_token)

    concepto = str(c.concepto_pago)[:35] if c.concepto_pago else "?"
    print("%-6s  %-38s  %-10s  %-10s  %-20s  %-14s  %s" % (
        c.pk, concepto, c.monto_asignado, c.estado, asp_info, via, token[:36] if token else ""))
