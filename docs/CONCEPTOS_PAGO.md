# Generación automática de Conceptos de Pago (Fase A)

Este documento explica cómo HALU genera y mantiene sincronizados los
`ConceptoPago` a partir de los `NivelEscolaridad` configurados por cada
institución.

---

## 1. Modelo conceptual

```
InstitucionEducativa
        │
        ├── PeriodoAcademico (activo=True, año_escolar=AAAA)
        │
        ├── NivelEscolaridad (Preescolar, Primaria, …)
        │     │   valor_inscripcion_estandar
        │     │   valor_matricula_estandar
        │     │   valor_pension_estandar
        │     │
        │     ├── Grado (Pre-jardín, 1°, 2°, …) ──┐
        │     │                                   │
        │     └── ConceptoPago (auto-generados)   │
        │           1× Inscripción <nivel>        │
        │           1× Matrícula <nivel> AAAA     │
        │           10× Pensión <mes> AAAA        │
        │              (Feb–Nov)                  │
        │                                         │
        └─────────────────────────────────────────┘
                                                  │
                                       Aspirante usa Grado
                                       → toma Nivel
                                       → toma ConceptoPago correcto
```

**Cada `ConceptoPago` lleva un `nivel_escolaridad` para multi-tenant
correcto y 3 flags excluyentes**:

| Flag | True solo en |
|---|---|
| `es_pago_inscripcion` | El concepto único de inscripción del nivel |
| `es_pago_matricula` | El concepto único de matrícula del nivel/año |
| `es_pago_pension` | Las 10 mensualidades del nivel/año (Feb–Nov) |

---

## 2. ¿Dónde está la lógica?

### 2.1 Servicio único: `finanzas/services.py`

```python
from finanzas.services import sincronizar_conceptos_de_nivel

resultado = sincronizar_conceptos_de_nivel(nivel)
print(resultado.resumen())
# Nivel 'Preescolar (...)' año 2026: 12 creados, 0 actualizados, 0 sin cambios.
```

El servicio:

1. Resuelve el **año lectivo**:
   - Lee `PeriodoAcademico.objects.filter(institucion=X, activo=True).año_escolar`.
   - Si no hay periodo activo, cae a `timezone.localdate().year`.
2. Asegura los `TipoConceptoPago` canónicos (`Inscripción`, `Matrícula`, `Pensión`).
3. Para cada uno de los 12 conceptos esperados, hace `get_or_create` por
   `(institucion, nombre_concepto, tipo_concepto)`.
4. **Si el concepto ya existía**, solo actualiza:
   - `nivel_escolaridad` si estaba vacío.
   - Los flags `es_pago_*` si estaban incorrectos.
   - El `valor` solo si estaba en 0 (nunca pisa un valor editado a mano).
   - `automatico` si estaba en `False`.

### 2.2 Disparo automático: signal en `gestion_academica/signals.py`

```python
@receiver(post_save, sender=NivelEscolaridad)
def crear_conceptos_pago_para_nivel(sender, instance, created, **kwargs):
    transaction.on_commit(
        lambda: sincronizar_conceptos_de_nivel(instance)
    )
```

Garantías:
- Se dispara al **crear** y al **editar** un nivel.
- Usa `transaction.on_commit` → si la transacción que crea el nivel se
  revierte, los conceptos NO se crean (no quedan huérfanos).
- Si el servicio falla, **NO** rompe la creación del nivel (solo loguea).

### 2.3 Backfill manual: comando refactorizado

```bash
python manage.py crear_conceptos
python manage.py crear_conceptos --institucion 1
python manage.py crear_conceptos --año 2026
```

Útil para:
- Niveles creados ANTES de la signal (antes de la migración 0009).
- Forzar regeneración para un año lectivo distinto (sin tocar el activo).

El comando es idempotente; puede correrse cuantas veces se quiera.

---

## 3. Convenciones de nombrado

```
Inscripción {nombre_nivel}
Matrícula {nombre_nivel} {año}
Pensión {Mes} {año} - {nombre_nivel}
```

Ejemplo para `nivel='Preescolar'` y año 2026:

| Tipo | Nombre del concepto |
|---|---|
| Inscripción | `Inscripción Preescolar` |
| Matrícula | `Matrícula Preescolar 2026` |
| Pensión | `Pensión Febrero 2026 - Preescolar` |
| Pensión | `Pensión Marzo 2026 - Preescolar` |
| ... (8 más) | ... |
| Pensión | `Pensión Noviembre 2026 - Preescolar` |

**No renombres los conceptos a mano** — la signal los reconoce por nombre
y si los renombras, creará duplicados. Si necesitas cambiar el nombre, hazlo
desde el código del servicio para que sea consistente.

---

## 4. Flujo end-to-end

### 4.1 Caso: nueva institución desde cero

1. Admin de HALU crea `InstitucionEducativa`.
2. Admin de la institución crea `PeriodoAcademico` con `activo=True` y `año_escolar=2026`.
3. Admin crea **Niveles**:
   - `Preescolar` con valores 50000/200000/300000 → signal crea 12 conceptos para 2026.
   - `Primaria` con valores 60000/250000/350000 → signal crea otros 12 conceptos.
4. Admin crea **Grados** (`Pre-jardín`, `Transición`, `1°`, …) y asigna su `nivel_escolaridad`.
5. Plataforma lista para recibir aspirantes.

### 4.2 Caso: cambio de año lectivo

1. Admin marca el `PeriodoAcademico` 2026 como `activo=False`.
2. Crea `PeriodoAcademico` 2027 con `activo=True`.
3. Para cada nivel ya existente, edítalo (cambio cosmético basta) o ejecuta:
   ```bash
   python manage.py crear_conceptos --año 2027
   ```
4. Resultado: 12 conceptos NUEVOS por nivel para el 2027 (no borra los del 2026, quedan en histórico).

### 4.3 Caso: nivel mal configurado

Si un nivel no tiene `valor_pension_estandar` (queda en 0), los conceptos
de pensión se crean con `valor=0`. El admin debe editarlos manualmente
desde Finanzas → Conceptos de Pago. La próxima vez que se edite el
nivel con el valor correcto, la signal **subirá** los conceptos a 0 al
nuevo valor.

---

## 5. Validación

```bash
python manage.py verificar_admisiones_health --institucion <id>
```

Paso `[7/7] Conceptos de Pago` debe reportar para cada nivel:

```
[OK] [Inscripción] Nivel 'Preescolar': 1 concepto configurado.
[OK] [Matrícula]   Nivel 'Preescolar': 1 concepto configurado.
[OK] [Pensiones]   Nivel 'Preescolar': 10 ConceptoPago de pensión.
```

Si reporta `[ERR]`, ejecuta `manage.py crear_conceptos --institucion <id>`
y vuelve a verificar.

---

## 6. Cambios respecto a versiones anteriores

| Antes (legacy) | Ahora (Fase A) |
|---|---|
| Comando `crear_conceptos` creaba conceptos por institución, sin `nivel_escolaridad` | Conceptos siempre tienen `nivel_escolaridad` |
| Comando creaba con `valor=0` y nombre genérico | Toma `valor_*_estandar` del nivel y nombra con el nivel incluido |
| `tipo_concepto` se llamaba "Mensualidad" | Se llama "Pensión" (consistente con `es_pago_pension`) |
| `es_pago_inscripcion`/`es_pago_matricula` quedaban en `False` | Los flags se setean correctamente |
| Sin `es_pago_pension` | Nuevo flag agregado en migración `finanzas.0009` |
| Manual: el admin debía correr el comando | Automático: signal `post_save` en `NivelEscolaridad` |
