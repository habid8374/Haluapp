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

## Fase B — items de bajo riesgo: APLICADOS ✅

- ✅ **N+1 de riesgo académico**: `analizar_riesgo_academico_en_lote()` en
  `gestion_academica/utils.py` calcula todos los pares (estudiante, curso) con
  2 consultas totales (antes 2 por par; ~960 → 4 en el dashboard del director
  de grupo). La usan el contador del dashboard/API, el export a Excel y el
  detalle por estudiante. Equivalencia verificada par a par contra la función
  original.
- ✅ **Asistencia**: consultas por día migradas de `fecha__date` a `fecha_solo`
  (DateField indexado) + índice compuesto `(institucion, fecha_solo, estado)`.
  Migración `gestion_academica/0047` con backfill (`TruncDate`, zona Bogotá).
- ✅ **Paginación** en `lista_notificaciones_view` (25 por página).
- ✅ **Encolados Celery blindados**: todos los `.delay()` de `signals.py` pasan
  por `_delay_seguro` — un broker caído no tumba la operación del usuario.

## Fase B — pendiente (antes de firmar un cliente de 500+)

- **Separar HTTP de WebSockets.** Hoy el web corre como **un solo proceso Daphne**
  (sin `--workers`). Servir HTTP con Gunicorn + workers `uvicorn` y dejar Daphne
  solo para WebSockets, o correr varias instancias tras un balanceador.
  Requiere staging + prueba de carga antes de producción.
- **PgBouncer** (pooling de conexiones a PostgreSQL, modo transaction) — sin esto,
  muchos procesos agotan el `max_connections`. Primer paso más ligero: pool
  nativo de Django 5.2/psycopg3 (`OPTIONS: {"pool": True}`).
- **Prueba de carga** simulando ~300 usuarios concurrentes antes de comprometer SLA.

## Dónde escala mejor

Los puntos de Fase B (Daphne multi-worker, PgBouncer, HA de PostgreSQL) son justo
lo que un escalón tipo **Render** ofrece de forma más limpia que Railway. Ver la
propuesta de infraestructura para 500–1.000 estudiantes.

## Plan a ~3 meses: migración a DigitalOcean + Fase B

Decisión (fecha del commit): cuando llegue el momento de escalar, migrar a
**DigitalOcean** y hacer allí la Fase B. Notas para ese día:

- **Cómputo:** App Platform (PaaS, trae balanceador + réplicas, similar a
  Railway) o Droplets + Managed Databases (más control). El multi-worker web
  (Gunicorn + workers uvicorn) es un cambio de Dockerfile, ya contemplado.
- **PostgreSQL gestionado de DO → incluye PgBouncer (connection pooling).**
  Resuelve nativamente el pendiente de pooling de la Fase B; solo apuntar
  `DB_HOST`/puerto al pool.
- **Redis gestionado de DO** (o Valkey) para caché, sesiones (`cached_db`),
  rate-limit y channel layer. Solo repuntar `REDIS_URL` / `CELERY_BROKER_URL`.
- **Almacenamiento:** se puede **conservar Cloudflare R2** (funciona desde
  cualquier nube; no hay que migrar archivos). Alternativa: DO Spaces.
- **Candados a resolver en la migración (ya documentados arriba):**
  1) sacar `migrate` del arranque por-instancia (paso único de release),
  2) confirmar media en R2/Spaces (no disco local),
  3) separar Celery Beat del worker (`railway.beat.json` sirve de molde),
  4) apuntar el balanceador y subir réplicas del web.
- **Datos:** `pg_dump` de PostgreSQL → restaurar en el Managed DB de DO;
  Redis es efímero (no requiere migración de datos); mover variables de entorno
  y DNS al final.
