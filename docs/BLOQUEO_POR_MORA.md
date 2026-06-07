# Fase C — Bloqueo real del portal del estudiante por mora

> Este documento describe la lógica de **bloqueo del portal académico de
> estudiantes con mensualidades vencidas**. Aplica a HALU 1.x en adelante.

## TL;DR

Hasta la versión anterior, el portal del estudiante mostraba un **mensaje
visual** ("Acceso restringido") pero el estudiante podía seguir consumiendo
deberes, lecciones, calificaciones, boletín y aula virtual cambiando la URL.
**Fase C** convierte ese bloqueo en **un bloqueo real a nivel de vista**:

- **Backend** (Django) y **API** (DRF) rechazan la petición si el estudiante
  está moroso, redirigen al dashboard, o devuelven `403`.
- El **dashboard del estudiante** muestra una pantalla de mora bien diseñada
  (saldo total vencido, días de atraso, lista de cuentas, CTA para pagar).
- El **toggle por institución** permite a cada cliente activar o desactivar el
  bloqueo (modelo SaaS multi-tenant) y configurar días de gracia.

## Configuración por institución

En el admin de `InstitucionEducativa` aparecen 2 nuevos campos:

| Campo                          | Tipo            | Default | Descripción                                                                                              |
| ------------------------------ | --------------- | ------- | -------------------------------------------------------------------------------------------------------- |
| `bloquear_portal_por_mora`     | `BooleanField`  | `True`  | Si está apagado, ningún estudiante de esa institución será bloqueado, sin importar su deuda.             |
| `dias_gracia_mora`             | `PositiveInt`   | `0`     | Días de margen tras el vencimiento antes de bloquear. Útil para no bloquear el día 1 (ej. fin de semana). |

> **Recomendación**: dejar `bloquear_portal_por_mora=True` y `dias_gracia_mora=3`
> para evitar fricción innecesaria en pagos que se procesan con 24-72h de retraso.

## ¿Cómo se decide si un estudiante está al día?

`gestion_academica.models.Estudiante.esta_al_dia()` devuelve `True` si:

1. La institución tiene `bloquear_portal_por_mora=False`, **o**
2. El estudiante NO tiene `CuentaPorCobrarEstudiante` con:
   - `estado != PAGADO` y `estado != ANULADO`,
   - `fecha_vencimiento_especifica < hoy - dias_gracia_mora`.

```python
estudiante = Estudiante.objects.get(pk=...)
estudiante.esta_al_dia()           # bool
estudiante.cuentas_vencidas_qs     # QuerySet de cuentas vencidas
estudiante.dias_de_atraso_max      # int — atraso de la cuenta más antigua
```

## Vistas protegidas

### Vistas Django clásicas (`@requiere_pagos_al_dia`)

Importa el decorator desde `gestion_academica.decorators`:

```python
from gestion_academica.decorators import requiere_pagos_al_dia

@login_required
@permission_required('gestion_academica.ver_mis_deberes')
@requiere_pagos_al_dia
def mis_deberes_lista(request):
    ...
```

Comportamiento:
- Si el usuario **no es estudiante** (admin, docente, familiar, super-admin):
  pasa transparente.
- Si es estudiante **al día**: pasa transparente.
- Si es estudiante **moroso**: redirige a `gestion_academica:dashboard_estudiante`
  con un `messages.error()` indicando los días de atraso.

Vistas ya protegidas (Fase C inicial):

| Vista                                      | Archivo                          |
| ------------------------------------------ | -------------------------------- |
| `mis_cursos_y_calificaciones_resumen`      | `gestion_academica/views.py`     |
| `detalle_mis_calificaciones_por_curso`     | `gestion_academica/views.py`     |
| `mis_deberes_lista`                        | `gestion_academica/views.py`     |
| `realizar_entrega_deber`                   | `gestion_academica/views.py`     |
| `mi_boletin_periodo_actual`                | `gestion_academica/views.py`     |
| `boletin_imprimible`                       | `gestion_academica/views.py`     |
| `mi_historial_asistencia`                  | `gestion_academica/views.py`     |
| `detalle_curso_aula_virtual`               | `gestion_academica/views.py`     |
| `resolver_actividad_page` (x2 ocurrencias) | `gestion_academica/views.py`     |
| `detalle_leccion_diaria`                   | `gestion_academica/views.py`     |
| `detalle_calificaciones_por_materia`       | `gestion_academica/views.py`     |
| `aula_virtual` (e-learning)                | `elearning/views.py`             |
| `rendir_evaluacion` (e-learning)           | `elearning/views.py`             |

> **NO se protege** `dashboard_estudiante` (debe seguir accesible para que el
> moroso vea su estado de cartera y pague), `ver_mi_perfil`, ni vistas de
> `cuestionarios` (CBV — pendiente de revisión opcional con `method_decorator`).

### Vistas DRF (`EstaAlDiaPermission`)

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from gestion_academica.decorators import EstaAlDiaPermission

@api_view(['GET'])
@permission_classes([IsAuthenticated, EstaAlDiaPermission])
def mis_deberes_api_view(request):
    ...
```

Comportamiento: si el estudiante está moroso, devuelve `403` con `detail` =
"El portal está bloqueado por mensualidades vencidas.".

APIs ya protegidas:

| API                                          |
| -------------------------------------------- |
| `mis_deberes_api_view`                       |
| `mi_boletin_api_view`                        |
| `detalle_calificaciones_materia_api_view`    |
| `mi_horario_api_view`                        |
| `mi_historial_asistencia_api_view`           |

## Dashboard del estudiante

Cuando `portal_bloqueado_por_mora == True`, el dashboard reemplaza
calificaciones, asignaturas y horario por una **tarjeta de mora rica**:

- KPIs grandes: cuentas vencidas, días de atraso máx., saldo vencido total.
- Tabla con las 10 cuentas vencidas más antiguas (concepto, vencimiento, saldo).
- CTA prominente "Pagar ahora y desbloquear el portal" → `finanzas:mi_estado_de_cuenta`.
- Mensaje claro: "Una vez registrado el pago, el acceso se reactivará al recargar".

La API `dashboard_estudiante_api_view` también devuelve `portal_bloqueado_por_mora`
y `dias_atraso_max` en `alertas_principales` para que la app móvil reproduzca
la misma pantalla.

## Health-check

`python manage.py verificar_admisiones_health` ahora incluye un paso `[8/8]`
que reporta cuántos estudiantes activos están bloqueados por mora:

```
[8/8] Estudiantes en mora (informativo / Fase C)
  -> Colegio Demo (id=1)
  [OK]    Bloqueo activo (gracia 0 día(s)). Estudiantes afectados: 12/300 (4.0%).
```

Si el bloqueo está apagado para una institución, el comando lo reporta como WARN
para que el super-admin lo vea de inmediato.

Si más del **50%** de los estudiantes están bloqueados, se emite un WARN
adicional sugiriendo revisar la causa (puede ser una mala generación de cuentas).

## Migración

```bash
python manage.py migrate finanzas
```

Aplica `finanzas.0010_institucion_bloqueo_mora` que añade los 2 nuevos campos
a `InstitucionEducativa`.

## Cómo desactivar el bloqueo de emergencia

Si una institución necesita desactivar el bloqueo por una situación particular
(ej. caída de la pasarela de pago), basta con desmarcar
`bloquear_portal_por_mora` en el admin → guardar. **No requiere reinicio**, el
toggle se evalúa en cada request.

Para volver a activarlo, marcarlo de nuevo y guardar.

## Cómo extender a más vistas

1. Importar el decorator: `from gestion_academica.decorators import requiere_pagos_al_dia`.
2. Aplicarlo **después** de `@login_required` y `@permission_required`:
   ```python
   @login_required
   @permission_required('app.algun_permiso')
   @requiere_pagos_al_dia
   def mi_vista(request):
       ...
   ```
3. Si la vista es DRF, usar `EstaAlDiaPermission` en `permission_classes`.

## Limitaciones conocidas

- Las vistas CBV de `cuestionarios/` (`IniciarCuestionarioView`,
  `ResolverCuestionarioView`, etc.) aún no aplican el decorator. Se puede
  agregar con `method_decorator` en una iteración futura si el negocio lo
  considera prioritario.
- El bloqueo aplica a **todos** los estudiantes activos de una institución
  cuando el toggle está activo. No hay aún forma de excluir individualmente a
  un estudiante específico (caso "becado por convenio sin obligación de pago"),
  más allá de marcarle todas las cuentas como `ANULADO` en finanzas.
