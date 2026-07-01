# Escalado de la plataforma (500–1.000 estudiantes)

Notas técnicas de la auditoría de escalabilidad y de los ajustes aplicados.

## Fase A — aplicada (mejora ya el rendimiento actual)

1. **IA (Gemini) fuera del request.** Las 3 señales de IA (`sugerir_material_de_refuerzo`,
   `analizar_observacion_convivencia`, `analizar_propuesta_candidato`) y el bucle de
   la vista de guardar notas ya **no llaman a Gemini de forma síncrona**; encolan
   tareas Celery (`.delay()` dentro de `transaction.on_commit`). Antes, guardar un
   libro de notas con varios reprobados hacía una llamada de 2–15 s por alumno
   dentro de la petición. Ahora el guardado es inmediato y la IA corre en segundo
   plano. Tareas en `gestion_academica/tasks.py`
   (`sugerir_material_de_refuerzo_task`, `analizar_observacion_convivencia_task`,
   y la ya existente `analizar_propuesta_candidato_task`).
2. **Sesiones en caché.** `SESSION_ENGINE = cached_db` (antes `db`): lee de Redis en
   producción, reduce lecturas a PostgreSQL en cada request autenticado.
3. **Redis obligatorio en producción (fail-fast).** Si falta `REDIS_URL` en
   producción, la app **no arranca** (antes caía en silencio a caché en memoria,
   que rompe el rate-limit y la caché con varios workers). Se permite memoria
   local solo en `DEBUG` o `USE_SQLITE` (dev/tests).
4. **Índices nuevos.** `Estudiante(institucion, activo)` y
   `PagoRegistrado(institucion, fecha_pago)` — consultas calientes de dashboards y
   reportes financieros. Migraciones `gestion_academica/0046_*` y `finanzas/0022_*`.

## Celery Beat — separar del worker (cuando escales el worker)

Hoy el worker corre `celery ... worker --beat` (`railway.celery.json`): worker y
scheduler en el mismo proceso. **Con 1 réplica funciona bien.** Pero si escalas el
worker a **más de 1 réplica**, tendrás **schedulers duplicados** (los backups y
tareas programadas se ejecutarían N veces).

Cutover cuando llegue ese momento (paso manual en Railway):
1. Crear un **servicio nuevo** en Railway usando `railway.beat.json` (arranca
   `celery -A proyecto_colegio beat`).
2. Quitar `--beat` del comando del worker en `railway.celery.json`
   (dejar `celery -A proyecto_colegio worker --loglevel=info --concurrency=2`).

Así el scheduler queda en un único proceso y el worker puede replicarse sin
duplicar tareas.

## Fase B — pendiente (antes de firmar un cliente de 500+)

- **Separar HTTP de WebSockets.** Hoy el web corre como **un solo proceso Daphne**
  (sin `--workers`). Servir HTTP con Gunicorn + workers `uvicorn` y dejar Daphne
  solo para WebSockets, o correr varias instancias tras un balanceador.
- **PgBouncer** (pooling de conexiones a PostgreSQL, modo transaction) — sin esto,
  muchos procesos agotan el `max_connections`.
- **N+1 de riesgo académico** (`gestion_academica/utils.py`
  `calcular_estado_academico_curso`): hace 2 consultas por par estudiante×curso;
  invocado desde `dashboard_docente` y el export de riesgo. Precomputar en 2
  consultas por grado y trabajar en memoria.
- **Asistencia:** indexar/usar `fecha_solo` (DateField) en `RegistroAsistencia` en
  vez de `fecha__date` sobre el DateTimeField, con índice
  `(institucion, fecha_solo, estado)`.
- **Paginación** en `lista_notificaciones_view`.
- **Prueba de carga** simulando ~300 usuarios concurrentes antes de comprometer SLA.

## Dónde escala mejor

Los puntos de Fase B (Daphne multi-worker, PgBouncer, HA de PostgreSQL) son justo
lo que un escalón tipo **Render** ofrece de forma más limpia que Railway. Ver la
propuesta de infraestructura para 500–1.000 estudiantes.
