# Dashboard de Mantenimiento (Super-Admin)

> Pantalla web del panel super-admin que ejecuta el **health-check operativo
> de HALU** en vivo, con barra de progreso, log en tiempo real y registro
> histórico de cada ejecución.

## TL;DR

Hasta ahora el health-check solo se podía correr desde la consola con
`python manage.py verificar_admisiones_health`. Eso es perfecto para
SRE/desarrolladores, pero **inutilizable para un super-admin no técnico** en
producción.

El **Dashboard de Mantenimiento** trae esa misma información al navegador:

- Acceso desde el panel super-admin (botón "Mantenimiento", amarillo).
- Botón "Iniciar diagnóstico ahora" → encola tarea Celery → muestra cada
  paso aparecer en vivo vía WebSocket.
- Histórico de las últimas 20 ejecuciones con estado, autor, duración y enlace
  al detalle completo.
- Cada ejecución se persiste en `finanzas.EjecucionHealthCheck` (auditoría).

## Ruta de acceso

```
/finanzas/superadmin/mantenimiento/
```

Reglas de acceso (las tres a la vez):

1. `is_superuser=True`.
2. Login estándar de Django.
3. Sesión `superadmin_autenticado` activa (la "cerradura" del panel,
   ver `superadmin_login_view`).

Cualquier usuario que no cumpla los 3 puntos recibe un redirect a la pantalla
de cerradura o un 403.

## Arquitectura

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Dashboard de Mantenimiento (Super-Admin)                                  │
└────────────────────────────────────────────────────────────────────────────┘
                                  │
            (click "Iniciar diagnóstico")
                                  ▼
            POST /finanzas/superadmin/mantenimiento/ejecutar/
                                  │
                                  ▼
   1. Crear EjecucionHealthCheck (estado=PENDIENTE)
   2. encolar  finanzas.tasks.run_health_check_task.delay(ej.pk, inst_id)
   3. redirect a /finanzas/superadmin/mantenimiento/<pk>/      ─┐
                                                                │
                                  ▼                             │
            Cliente abre WebSocket ws/healthcheck/<pk>/ ◄───────┤
                                  │                             │
                                  │  WebSocket bidireccional    │
                                  │                             │
                                  ▼                             ▼
                     ┌──────────────────────┐   ┌────────────────────────┐
                     │ HealthCheckConsumer  │   │ Celery worker          │
                     │ (channels)           │   │ run_health_check_task  │
                     └──────────────────────┘   └────────────────────────┘
                                  ▲                             │
                                  │                             │
                                  └─────── group_send ──────────┘
                                  (1 mensaje por cada evento del check)
                                                                │
                                                                ▼
                                            admisiones.services.health_check
                                                                │
                                                                ▼
                            (8 pasos: Redis, Celery, Channels, Plantillas,
                             URLs, Multi-tenant, ConceptoPago, Mora)
```

## Componentes

### Modelo `EjecucionHealthCheck`

`finanzas/models.py`. Audita cada ejecución del dashboard.

| Campo                 | Tipo                  | Notas                                                          |
| --------------------- | --------------------- | -------------------------------------------------------------- |
| `iniciado_por`        | FK a `User`           | Quien hizo click en el botón.                                  |
| `institucion_filtro`  | FK a `Institucion`    | Opcional. Si se pasa, restringe el check a esa institución.    |
| `iniciado_at`         | `DateTimeField`       | Auto.                                                          |
| `terminado_at`        | `DateTimeField` (nul) | Se setea al final (success o fallido).                         |
| `estado`              | enum                  | PENDIENTE / EJECUTANDO / OK / WARN / ERROR / FALLIDO.          |
| `task_id`             | str                   | Celery task ID, para auditoría.                                |
| `errores_count`       | int                   | Conteo final de eventos `nivel=ERR`.                           |
| `warnings_count`      | int                   | Conteo final de eventos `nivel=WARN`.                          |
| `pasos_completados`   | smallint              | Hasta qué paso (1..8) llegó.                                   |
| `eventos`             | `JSONField`           | Lista completa de eventos generados (1 item por línea de log). |
| `error_excepcion`     | text                  | Si la tarea Celery murió de excepción, traceback resumido.     |

El admin de Django muestra todos los registros (read-only).

### Service `admisiones.services.health_check`

Lógica canónica de los 8 pasos. **No imprime nada**, recibe un
`progreso_callback(evento)` que se llama por cada línea generada.

```python
from admisiones.services.health_check import ejecutar_health_check

resultado = ejecutar_health_check(
    institucion_id=None,                 # o un ID para filtrar
    progreso_callback=lambda evento: ...,# opcional
)
print(resultado.errores, resultado.warnings)
print(resultado.eventos)
```

Cada `EventoHealthCheck` tiene:

```python
{
    "nivel": "OK" | "WARN" | "ERR" | "INFO",
    "paso": "1/8" | "2/8" | ... | "",          # solo en encabezados
    "titulo": "Redis (broker)" | ...,          # solo en encabezados
    "mensaje": "Redis responde PING en redis://...",
}
```

Lo usan dos consumidores:
- `manage.py verificar_admisiones_health` (CLI).
- `finanzas.tasks.run_health_check_task` (Celery + WebSocket).

### Tarea Celery `run_health_check_task`

`finanzas/tasks.py`. Ejecuta el service y notifica progreso al WebSocket.

- `soft_time_limit=120s`, `time_limit=150s`.
- `max_retries=0` (es un diagnóstico manual; no reintenta).
- Envía cada evento al grupo WS `healthcheck_<ejecucion_id>` mediante
  `group_send`.
- Al final marca `terminado_at`, `estado`, `errores_count`, etc. y notifica
  `tipo=finalizado` (o `fallido` si excepción).

### WebSocket consumer `HealthCheckConsumer`

`finanzas/consumers.py`. Solo super-admins pueden conectar. Reenvía como JSON
al cliente cada `payload` que recibe en `group_send`.

Ruta WS:

```
ws://<host>/ws/healthcheck/<ejecucion_id>/
```

### Vistas

| URL                                                              | View                          | Método | Función                             |
| ---------------------------------------------------------------- | ----------------------------- | ------ | ----------------------------------- |
| `/finanzas/superadmin/mantenimiento/`                            | `mantenimiento_dashboard`     | GET    | Página principal con histórico.     |
| `/finanzas/superadmin/mantenimiento/ejecutar/`                   | `mantenimiento_ejecutar`      | POST   | Crea ejecución + encola Celery.     |
| `/finanzas/superadmin/mantenimiento/<pk>/`                       | `mantenimiento_detalle`       | GET    | Página de progreso/resultado.       |
| `/finanzas/superadmin/mantenimiento/<pk>/estado/`                | `mantenimiento_estado_api`    | GET    | JSON con el estado (fallback poll). |

Todas pasan por `_superadmin_required` (helper local) que valida los 3
requisitos de acceso.

### Templates

- `finanzas/templates/finanzas/mantenimiento_dashboard.html`:
  KPIs del último diagnóstico, formulario para lanzar uno nuevo (con dropdown
  de instituciones), guía de los 8 pasos, histórico paginado.
- `finanzas/templates/finanzas/mantenimiento_detalle.html`:
  Log estilo terminal con coloreado por nivel (verde=OK, amarillo=WARN,
  rojo=ERR, azul=INFO/encabezados), KPIs en vivo, progress bar animada,
  reconexión y manejo gracioso de errores WS.

### Enlace en el dashboard super-admin

`finanzas/templates/finanzas/dashboard_superadmin.html` ahora muestra un botón
amarillo **"Mantenimiento"** junto al de "Bloquear Dashboard".

## Operación

### Lanzar un diagnóstico

1. Login con un usuario `superuser=True`.
2. Abrir `/finanzas/superadmin/` (introducir la clave maestra si aplica).
3. Click en **"Mantenimiento"**.
4. (Opcional) Elegir una institución específica en el dropdown.
5. Click **"Iniciar diagnóstico ahora"**.
6. Esperar 15–60s viendo el log fluir en vivo.

### Si Celery no está corriendo

El POST a `mantenimiento_ejecutar` detecta la excepción al encolar, marca
la ejecución como `FALLIDO`, escribe el motivo en `error_excepcion`, y
muestra `messages.error` al usuario con el mensaje:

> "No se pudo encolar el diagnóstico: <motivo>. Verifica que Celery esté corriendo."

### Si el WebSocket no conecta (Channels caído)

El template detecta el `onerror`/`onclose` y muestra el mensaje:

> "Error de WebSocket. Recarga la página."

La ejecución sigue corriendo en Celery y se persiste correctamente en BD,
solo se pierde el feedback en vivo. Recargando se ve el log final completo.

### Auditoría

Cada ejecución queda en `EjecucionHealthCheck`. Útil para:

- Detectar **regresiones**: comparar dos ejecuciones consecutivas.
- Saber **quién** lanzó cuándo cada diagnóstico.
- Tener histórico del estado de salud de la plataforma a lo largo del tiempo.

Se puede consultar también desde el admin de Django:
`/admin/finanzas/ejecucionhealthcheck/`.

## Sincronía con el CLI

`python manage.py verificar_admisiones_health` y el dashboard ejecutan
**exactamente la misma función** (`ejecutar_health_check` del service). Si
arreglas o agregas un nuevo paso al service, **ambos lo verán inmediatamente**.

## Extender con nuevos chequeos

1. Editar `admisiones/services/health_check.py`.
2. Agregar una función `_check_X(emit, ...)` que use `emit(NIVEL, mensaje)`.
3. Llamarla en `ejecutar_health_check` con su encabezado:
   ```python
   emit(NIVEL_INFO, "Verificando X…", paso="9/9", titulo="X")
   _check_X(emit)
   ```
4. Actualizar `PASOS_TOTALES = 9` (y los encabezados anteriores a "n/9").
5. Actualizar la guía visual en `mantenimiento_dashboard.html`.

## Limitaciones conocidas

- No hay **scheduling automático** (cron) — el diagnóstico se ejecuta
  manualmente. Si se quisiera correrlo cada N horas, se podría usar
  `celery-beat` apuntando a la misma tarea.
- No hay **alertas** (email/SMS/Slack) cuando un diagnóstico falla. Quedará
  como mejora futura si el negocio lo necesita.
