# Flujo: Aspirante → Matrícula → Pensiones (Fase B)

Este documento describe el ciclo completo desde que un aspirante se inscribe
hasta que queda matriculado con sus 10 mensualidades del año lectivo.

---

## 1. Diagrama del flujo

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. INSCRIPCIÓN                                                   │
│    Aspirante.procesar_inscripcion_completa()                     │
│    ├─ Crea Usuario                                               │
│    ├─ Crea Estudiante (activo=False)                             │
│    └─ crear_cuenta_cobro_inscripcion()  ──┐                      │
│       ⇒ ResultadoCobroInscripcion         │                      │
│         (puede ser warning si falta       │                      │
│          ConceptoPago)                    │                      │
└────────────────────────────────────────────┼─────────────────────┘
                                             │
              Aspirante recibe correo con botón "Pagar Inscripción"
                                             │
┌────────────────────────────────────────────▼─────────────────────┐
│ 2. PAGO DE INSCRIPCIÓN                                           │
│    Mercado Pago → Webhook → estado: ADMITIDO                     │
└──────────────────────────────────────────────────────────────────┘
                                             │
              Admin agenda cita, revisa documentos, evalúa
                                             │
┌────────────────────────────────────────────▼─────────────────────┐
│ 3. APROBADO PARA MATRÍCULA                                       │
│    estado: APROBADO_MATRICULA                                    │
│    Signal post_save → crear_cuenta_cobro_matricula()             │
│    Aspirante recibe correo con botón "Pagar Matrícula"           │
└──────────────────────────────────────────────────────────────────┘
                                             │
┌────────────────────────────────────────────▼─────────────────────┐
│ 4. PAGO DE MATRÍCULA                                             │
│    Mercado Pago → Webhook → aspirante.matricular()               │
│    ├─ activa Estudiante                                          │
│    ├─ asigna rol "estudiante"                                    │
│    ├─ estado: MATRICULADO                                        │
│    └─ sincronizar_cuentas_automaticas()  ──┐                     │
│       ⇒ ResultadoSincronizacionCuentas     │                     │
│         (warning si faltan ConceptoPago    │                     │
│          de pensión)                       │                     │
└────────────────────────────────────────────┼─────────────────────┘
                                             │
                                             ▼
                              10 cuentas de pensión creadas
                              (Feb–Nov del año lectivo)
                              + 1 cuenta de matrícula
```

---

## 2. `sincronizar_cuentas_automaticas` (Fase B)

Esta es la función crítica que genera las 10 mensualidades + matrícula al
matricular. Vive en `finanzas/managers.py` y se llama así:

```python
from finanzas.models import CuentaPorCobrarEstudiante

resultado = CuentaPorCobrarEstudiante.objects.sincronizar_cuentas_automaticas(estudiante)

if resultado.es_warning:
    print(f"⚠ {resultado.mensaje}")
elif resultado.es_exito:
    print(f"OK: {resultado.resumen()}")
```

### 2.1 Qué hace

1. Valida que el estudiante esté activo, tenga grado y nivel.
2. Determina el **año lectivo** desde `PeriodoAcademico.activo`.
3. Inicializa `valor_mensualidad` y `valor_matricula` del estudiante a partir
   del nivel (solo si están en 0).
4. Busca el `ConceptoPago` de **matrícula** del nivel y crea/reusa la cuenta.
5. Busca los `ConceptoPago` de **pensión** del nivel y para cada mes Feb–Nov
   crea/reusa la cuenta correspondiente.
6. Aplica descuentos activos del estudiante (M2M `descuentos`).
7. Devuelve `ResultadoSincronizacionCuentas`.

### 2.2 Estructura del resultado

```python
@dataclass
class ResultadoSincronizacionCuentas:
    estudiante: Estudiante
    año: int
    cuentas_pension_creadas: int           # 0–10
    cuentas_pension_existentes: int        # las que ya estaban
    cuenta_matricula_creada: bool
    cuenta_matricula_existente: bool
    motivo_falla: str | None
    mensaje: str

    es_exito: bool          # True si motivo_falla is None
    es_warning: bool        # True si es problema accionable
    total_cuentas_creadas: int
    resumen() -> str
```

### 2.3 Motivos de falla

| `motivo_falla` | Significado | Acción del admin |
|---|---|---|
| `estudiante_inactivo` | El estudiante tiene `activo=False` | Verificar la matrícula |
| `sin_grado` | No tiene `grado_actual` | Asignar grado |
| `sin_nivel_escolaridad` | El grado no tiene `nivel_escolaridad` | Editar el grado y asignar nivel |
| `sin_concepto_matricula` | No hay ConceptoPago con `es_pago_matricula=True` para el nivel, o hay duplicados | Editar el nivel para que la signal lo cree, o ejecutar `crear_conceptos` |
| `sin_concepto_pension` | No hay ConceptoPago con `es_pago_pension=True` para el nivel | Igual al anterior |
| `error_inesperado` | Excepción no controlada | Revisar logs |

Los 5 primeros son `es_warning=True` (no son bugs, son configuración).

### 2.4 Idempotencia

El método se puede llamar tantas veces como se quiera para el mismo
estudiante. Usa `get_or_create` por:
- Matrícula: `(estudiante, concepto, año)`
- Pensión: `(estudiante, concepto, año, mes)`

---

## 3. `Aspirante.matricular()` (Fase B)

Ahora retorna `(estudiante, ResultadoSincronizacionCuentas)` para que las
vistas puedan reportar al admin si las cuentas no se generaron.

### 3.1 Callers actualizados

| Caller | Comportamiento |
|---|---|
| `admisiones.views.matricular_aspirante` | Muestra `messages.warning` si `resultado.es_warning` |
| `admisiones.views.mercadopago_webhook` | Loguea `resultado.resumen()` |
| `finanzas.views` (al registrar pago manual) | Muestra `messages.warning` si aplica |
| `finanzas/management/commands/sincronizar_pagos_matricula` | Imprime advertencia con código de salida |

### 3.2 Backward-compatibility

El primer elemento de la tupla sigue siendo el `Estudiante`. Callers viejos
que escriban:

```python
estudiante = aspirante.matricular()  # ❌ ahora obtiene tupla
```

deben migrar a:

```python
estudiante, resultado = aspirante.matricular()
```

---

## 4. Recuperación de fallos

### 4.1 Pago aprobado en MP pero matrícula no creada

Causa típica: webhook caído, problema de red, signature inválida.

```bash
python manage.py reconciliar_pagos_mercadopago \
    --institucion <id> --desde 2026-05-01 --hasta 2026-05-12
```

Crea los `PagoRegistrado` faltantes a partir de pagos aprobados en MP.

```bash
python manage.py sincronizar_pagos_matricula
```

Para cada pago de matrícula sin matrícula registrada, llama a
`aspirante.matricular()` (que a su vez genera las pensiones).

### 4.2 Estudiante matriculado pero sin pensiones

Causa típica: configuración incompleta al momento de matricular (faltaba
`ConceptoPago` de pensión para el nivel).

1. Configurar/crear los conceptos faltantes (editar el nivel o `crear_conceptos`).
2. Re-correr la sincronización para ese estudiante:

```bash
# Vía admin:
# Ir a Finanzas → Estudiantes → seleccionar → "Sincronizar cuentas automáticas"

# Vía masivo (todos los estudiantes activos de la institución):
# Ir a Finanzas → Reportes → "Sincronizar masivo"
```

O programáticamente:

```python
from finanzas.models import CuentaPorCobrarEstudiante
from gestion_academica.models import Estudiante

estudiante = Estudiante.objects.get(pk=123)
resultado = CuentaPorCobrarEstudiante.objects.sincronizar_cuentas_automaticas(estudiante)
print(resultado.resumen())
```

---

## 5. Cambios respecto a versiones anteriores

| Antes (legacy) | Ahora (Fase B) |
|---|---|
| Buscaba ConceptoPago por `tipo_concepto.nombre__icontains='pensión'` | Busca por `es_pago_pension=True` |
| No filtraba por `nivel_escolaridad` (todos los niveles compartían concepto) | Filtra por `nivel_escolaridad` |
| Año fijo a `now().year` | Lee `PeriodoAcademico.activo.año_escolar` |
| Creaba conceptos al vuelo si no existían | Asume que existen (responsabilidad de la signal de Fase A) |
| Devolvía un `int` (cuentas creadas) | Devuelve `ResultadoSincronizacionCuentas` |
| `matricular()` devolvía solo el estudiante | Devuelve `(estudiante, resultado)` |
| Si fallaba la sincronización, solo se logueaba | Se reporta al admin vía `messages.warning` |
| No generaba la cuenta de matrícula desde aquí | Sí la genera (junto con las 10 pensiones) |
