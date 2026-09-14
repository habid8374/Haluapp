# Migración Railway → DigitalOcean + Fase B + Multi-sede

> **Disparador:** posible entrada simultánea de ~500 estudiantes en 2 colegios
> privados + un colegio público de ~1.900 estudiantes. Este volumen cruza el
> umbral que `docs/ESCALADO.md` marcó como *"antes de firmar un cliente de
> 500+"* — así que la migración de infraestructura y los pendientes de Fase B
> dejan de ser opcionales, y hay que resolver la pregunta de sedes múltiples
> antes de prometer fecha al colegio público.
>
> Este documento une tres cosas que hasta ahora vivían en documentos
> separados (`docs/ESCALADO.md`, `PRODUCCION_GUIA.md`, `docs/PROPUESTA_SEDES.md`)
> en una sola guía operativa, en el orden en que hay que ejecutarlas.

---

## 0. Qué NO hay que migrar

Para no perder tiempo resolviendo cosas que ya están resueltas:

- **Media/archivos** — ya viven en Cloudflare R2, no en el servidor. Cero
  migración de archivos.
- **Correo/IA por institución** — Brevo, SMTP, Gemini/Claude son credenciales
  guardadas por institución en la base de datos, no en el servidor. Se mueven
  solos con el `pg_dump`/`pg_restore`.
- **Aislamiento público/privado** — ya funciona en código
  (`finanzas.mixins._finanzas_no_disponible`, `ModuloFinancieroMiddleware`):
  el colegio público nunca genera tráfico de pagos/facturación. Reduce la
  carga real que hay que dimensionar para los 1.900 estudiantes.

---

## 1. Arquitectura elegida en DigitalOcean

Decisión ya registrada en `docs/ESCALADO.md`: **Droplet + PostgreSQL
gestionado + Redis gestionado**, no App Platform.

**Por qué Droplet y no App Platform:** ya existe un playbook completo y
probado para VPS (`PRODUCCION_GUIA.md` — systemd, Nginx, Daphne, Celery,
backups) escrito para Hostinger. Un Droplet de DO es el mismo Ubuntu con el
mismo stack: se reutiliza ese documento casi literal, solo cambia el
proveedor. App Platform obligaría a rehacer el patrón de despliegue desde
cero (build packs, Dockerfile distinto, sin systemd) por una ganancia que
no compensa dado que el equipo ya domina el modelo VPS.

**Por qué PostgreSQL y Redis gestionados y no auto-alojados en el mismo
Droplet:** el PostgreSQL gestionado de DO **incluye PgBouncer** — resuelve
de fábrica el pendiente de connection pooling de la Fase B (sección 2.2)
sin instalar ni mantener nada. Redis gestionado evita perder sesiones/caché
si el Droplet de la app se reinicia.

### 1.1 Dimensionamiento inicial

Referencia (`PRODUCCION_GUIA.md`): el pico real de uso simultáneo en una
plataforma escolar es ~10–15 % del total matriculado.

| Cliente | Estudiantes | Pico concurrente estimado | Genera tráfico de pagos |
|---|---|---|---|
| Colegio privado A | ~250 | ~30–40 | Sí |
| Colegio privado B | ~250 | ~30–40 | Sí |
| Colegio público | ~1.900 | ~190–285 | **No** (finanzas bloqueado) |
| **Total** | **~2.400** | **~250–365** | — |

Esto cae casi exacto en el escalón **KVM 4 (16 GB / 6 vCPU)** de la tabla
de `PRODUCCION_GUIA.md` (hasta 3.000 estudiantes / ~360 concurrentes), y
probablemente con margen extra real porque el público no golpea
Mercado Pago/Finanzas/facturación electrónica.

**Recomendación de arranque:**

| Componente | DO — tamaño inicial | Equivalente |
|---|---|---|
| Droplet (app) | 8 vCPU / 16 GB (Premium AMD o Intel) | ≈ KVM 4 |
| Managed PostgreSQL | 2 vCPU / 4 GB, con PgBouncer activado | — |
| Managed Redis | 1 GB (db separadas: broker/results/cache/channels, igual que hoy) | — |

Ajustar hacia arriba según los resultados de la prueba de carga (sección
2.5) antes de poner en producción al colegio público — es, con diferencia,
el mayor volumen y el más desconocido (patrones de conexión de 1.900
estudiantes al arrancar la jornada).

---

## 2. Fase B — pendientes de código, ANTES de migrar

`docs/ESCALADO.md` los marcó como requisito para clientes de 500+. Se hacen
sobre el código actual (funcionan igual en Railway) y viajan ya resueltos a
DO — no hay que migrar y luego arreglar, se arregla primero.

### 2.1 Separar HTTP de WebSockets

**Problema actual:** `Dockerfile` arranca un único proceso Daphne sin
`--workers` para TODO (HTTP + WebSockets). Daphne no reparte HTTP entre
varios procesos por sí solo.

**Cambio:**
- HTTP → Gunicorn con workers `uvicorn` (`gunicorn.workers.UvicornWorker` o
  el paquete `uvicorn-worker`). `gunicorn` ya está en `requirements.txt`;
  falta agregar `uvicorn[standard]`.
- WebSockets (`/ws/`) → se quedan en Daphne, exclusivamente.
- Nginx (o el balanceador de DO) enruta `/ws/` a Daphne y todo lo demás a
  Gunicorn, igual que ya describe `PRODUCCION_GUIA.md` sección 3
  (`location /ws/` vs `location /`).

**Verificación:** con `ab`/`hey` o el mismo script de la sección 2.5,
confirmar que una ráfaga de HTTP no bloquea las conexiones WS abiertas
(mensajería, notificaciones en tiempo real).

### 2.2 Connection pooling a PostgreSQL

**Problema actual:** sin pooling, cada worker/proceso abre sus propias
conexiones a PostgreSQL; con varios workers Gunicorn + varios workers
Celery + Beat, se agota `max_connections` bajo carga.

**Resuelto por la elección de infraestructura:** el PostgreSQL gestionado
de DO trae PgBouncer (modo *transaction*) integrado. Solo hay que apuntar
`DB_HOST`/`DB_PORT` al endpoint del pool en vez del de la base directa —
sin instalar ni operar nada aparte.

Alternativa más ligera si por algún motivo no se usa el pool gestionado:
pool nativo de Django 5.2 + psycopg3 (`DATABASES['default']['OPTIONS'] =
{"pool": True}`).

### 2.3 Separar Celery Beat del worker

**Problema actual:** `railway.celery.json` arranca
`celery -A proyecto_colegio worker --beat --loglevel=info --concurrency=2`
— worker y scheduler en el mismo proceso. Con 1 réplica no hay problema,
pero si el worker escala a más de 1 réplica, el scheduler se duplica y las
tareas programadas (boletines, avisos, alertas PIAR, backups) se ejecutan
N veces.

**Cambio (plantilla ya existe, `railway.beat.json`):**
1. Servicio nuevo, solo Beat: `celery -A proyecto_colegio beat --loglevel=info`.
2. Quitar `--beat` del comando del worker, dejar
   `celery -A proyecto_colegio worker --loglevel=info --concurrency=<N>`.

En DO esto es un segundo `systemd` service (`halu-beat.service`, mismo
patrón que `halu-celery.service` en `PRODUCCION_GUIA.md` sección 3, sin el
flag `--beat`) — el worker puede escalar a 2+ réplicas sin duplicar nada.

### 2.4 Sacar `migrate`/`collectstatic` del arranque por-instancia

**Problema actual:** `/start.sh` (dentro del `Dockerfile`) corre
`python manage.py migrate --no-input` y `collectstatic` en **cada** arranque
del contenedor. Con 1 instancia no pasa nada; con varias réplicas
detrás de un balanceador (para repartir la carga de 2.400 estudiantes),
varias instancias corren `migrate` en paralelo al desplegar — riesgo de
migraciones a medio aplicar o bloqueos de tabla concurrentes.

**Cambio:** `migrate` y `collectstatic` pasan a ser un paso único de
*release*, no parte del arranque de cada réplica:
- Manual/simple: ejecutarlos a mano (o vía script) **antes** de reiniciar
  los servicios `halu@{1,2,3}`, como ya describe el "Procedimiento de
  actualización" de `docs/PRODUCCION.md` sección 10.
- `/start.sh` queda solo con: `exec daphne ...` / `exec gunicorn ...`.

De paso, aprovechar el cambio de `Dockerfile` para corregir
`python:3.10-slim` → `python:3.12-slim` (CLAUDE.md documenta 3.12 como la
versión del proyecto; el Dockerfile quedó desalineado).

### 2.5 Prueba de carga

Nunca se hizo formalmente. Antes de poner en producción a los 2 colegios
privados + el público:

- Simular ~300 usuarios concurrentes (el pico estimado de la tabla de la
  sección 1.1) con Locust/k6, mezclando: HTTP normal (dashboards, notas),
  ráfagas de guardado (libro de notas), y conexiones WS persistentes
  (notificaciones + mensajería).
- Objetivo: tiempo de respuesta HTTP < 800 ms promedio bajo esa carga
  (umbral que ya usa `PRODUCCION_GUIA.md` sección 7 como señal de alerta
  para escalar).
- Correr la prueba **después** de 2.1–2.4, para medir el sistema ya
  corregido, no el actual.

---

## 3. Checklist de migración — Railway → DigitalOcean

Basado en `PRODUCCION_GUIA.md` (adaptado de Hostinger a DO) + los cambios
de la sección 2.

```
PREPARACIÓN
[ ] Cuenta DigitalOcean, proyecto creado
[ ] Droplet Ubuntu 22.04 LTS, 8 vCPU / 16 GB, en el mismo datacenter que
    el PostgreSQL/Redis gestionados (misma VPC, latencia mínima)
[ ] PostgreSQL gestionado (2 vCPU/4 GB), pool PgBouncer activado
[ ] Redis gestionado (1 GB)
[ ] Dominio: registro DNS A apuntando al Droplet (TTL bajo, 300 s, para
    poder revertir rápido si algo falla)

CÓDIGO (hacer ANTES de tocar el servidor nuevo)
[ ] Sección 2.1 — Gunicorn+uvicorn para HTTP, Daphne solo para /ws/
[ ] Sección 2.3 — Celery Beat en servicio separado
[ ] Sección 2.4 — migrate/collectstatic fuera del arranque
[ ] Dockerfile: python:3.10-slim → python:3.12-slim
[ ] requirements.txt: agregar uvicorn[standard]
[ ] Probar TODO esto primero en Railway (son cambios de código, no de
    proveedor — deben funcionar igual antes de migrar servidor)

SISTEMA BASE (Droplet)
[ ] apt install nginx python3-pip python3-venv git certbot
    python3-certbot-nginx build-essential libpq-dev
    (Redis y PostgreSQL NO se instalan local — son los gestionados de DO)

CÓDIGO EN EL DROPLET
[ ] git clone del repo en /var/www/halu_plataform
[ ] venv + pip install -r requirements.txt
[ ] .env con DB_HOST/DB_PORT apuntando al pool PgBouncer de DO,
    REDIS_URL/CELERY_BROKER_URL/CELERY_RESULT_BACKEND apuntando al Redis
    gestionado (mismo esquema de db 0/1/2/3 que ya usa el proyecto)
[ ] Paso de RELEASE (una sola vez, no por réplica):
    python manage.py migrate --no-input
    python manage.py collectstatic --no-input
[ ] python manage.py createsuperuser

DATOS — pg_dump / pg_restore
[ ] En Railway: pg_dump -Fc -f halu_migracion.dump <DATABASE_URL_railway>
[ ] Transferir el dump al Droplet (o directo a un túnel hacia el managed DB)
[ ] pg_restore -d <DATABASE_URL_do_managed> halu_migracion.dump
[ ] Verificar conteos: SELECT count(*) en tablas clave (Usuario,
    Estudiante, InstitucionEducativa, PagoRegistrado) contra origen
[ ] Redis NO se migra — es efímero (sesiones/caché/colas se regeneran solas)

SERVICIOS SYSTEMD (patrón de PRODUCCION_GUIA.md sección 3, con los ajustes)
[ ] halu@.service (template, N workers Gunicorn+uvicorn para HTTP)
[ ] halu-ws.service (Daphne, solo WebSockets)
[ ] halu-celery.service (worker, SIN --beat)
[ ] halu-beat.service (beat, nuevo — sección 2.3)
[ ] systemctl enable + start de los 4

NGINX
[ ] location /ws/ → proxy_pass a Daphne (puerto dedicado)
[ ] location / → proxy_pass a upstream Gunicorn (least_conn, N workers)
[ ] SSL con certbot --nginx

WEBHOOKS A ACTUALIZAR (por institución, dominio nuevo)
[ ] Mercado Pago — portal de admisiones:
    https://<dominio-nuevo>/admisiones/pago/webhook_mp/
[ ] Mercado Pago — finanzas (pensiones/otros conceptos):
    https://<dominio-nuevo>/finanzas/... webhook
[ ] Reconfigurar en el panel de Mercado Pago de CADA institución que ya
    esté en producción (no es automático — corre el riesgo de que un
    pago real no notifique durante la ventana de corte)

CORTE (ventana corta, avisar a los colegios activos)
[ ] Congelar escrituras en Railway (o aceptar una ventana de unos minutos
    de posible pérdida de los últimos pagos/registros — idealmente de
    madrugada, fuera de horario escolar)
[ ] pg_dump final (diferencial desde el primero) + restore
[ ] Cambiar DNS al Droplet de DO
[ ] Confirmar propagación (dig/nslookup) antes de apagar Railway

VERIFICACIÓN FINAL
[ ] https://<dominio> carga
[ ] Login de superusuario + de un usuario de cada rol
[ ] Mensaje → verificar WS en tiempo real
[ ] python manage.py verificar_admisiones_health --strict → OK
[ ] Pago de prueba en modo sandbox de Mercado Pago → factura electrónica
    se dispara si corresponde (lo que se conectó esta sesión)
[ ] systemctl status de los 4 servicios → "active"

ROLLBACK (mientras no se confíe al 100% en DO)
[ ] Mantener Railway activo (sin tráfico) mínimo 7 días tras el corte
[ ] TTL de DNS bajo (300 s) permite revertir en minutos si aparece algo
[ ] Backup del dump pre-migración conservado aparte, no solo en Railway
```

---

## 4. Arquitectura multi-sede — cuándo aplicarla por institución

Diseño completo ya aprobado en `docs/PROPUESTA_SEDES.md` (implementación
aplazada "a la espera de un caso real multi-sede"). El colegio público de
~1.900 estudiantes es, muy probablemente, ese caso real: los colegios
oficiales grandes en Colombia casi siempre reparten sus estudiantes en
varias plantas físicas (sedes) por nivel — preescolar/primaria en una,
secundaria en otra, media en otra.

**Esto es independiente de la migración de servidor.** No depende de estar
en DO ni de la Fase B — es un tema de modelo de datos que aplica igual en
Railway o en DO. No bloquea la migración de infraestructura, pero sí puede
bloquear la fecha de entrega prometida a ese colegio si tiene varias sedes
y el levantamiento de información se hace tarde.

### 4.1 Qué ya existe en código hoy (no es un diseño desde cero)

- Modelo `Sede` ya existe: `simat/models.py:92` (institución, nombre,
  código DANE de sede, consecutivo, zona, jornada principal, es_principal,
  activa), con auto-creación de la sede principal
  (`Sede.asegurar_principal`, `simat/signals.py`).
- CRUD de sedes ya tiene UI: `simat/urls.py`
  (`lista_sedes`/`crear_sede`/`editar_sede`/`eliminar_sede`).
- Ya existe `InstitucionEducativa.es_multisede` (property) — se puede usar
  hoy mismo como bandera de diagnóstico.
- **Lo que falta:** sede como *fuente única* (hoy está duplicada en 4
  modelos: `Estudiante.sede`, `Grupo.sede`, `CaracterizacionEstudiante.sede`,
  `Aspirante.sede`), oferta de jornadas/niveles por sede, dimensión de sede
  en Docente/Aula, filtros por sede en tableros, rol `coordinador_sede`.
  Detalle completo en `docs/PROPUESTA_SEDES.md` secciones 3–8.

### 4.2 Procedimiento de decisión por institución (aplicar en cada onboarding)

Antes de matricular una institución grande (oficial o privada con varias
plantas físicas), preguntar explícitamente en el levantamiento inicial:

1. **¿Tiene más de una sede/planta física con código DANE propio?**
   Si la respuesta es no → seguir con el modelo actual (una sola sede
   `es_principal`, ya se autogenera), sin tocar nada de esta sección.
2. Si la respuesta es sí → revisar cuántas sedes, qué jornadas/niveles
   ofrece cada una, y si hoy reportan un solo Anexo 6A consolidado o uno
   por sede ante el MEN.
3. Marcar la institución como candidata a Fase A de `docs/PROPUESTA_SEDES.md`
   (sección 9 de ese documento) — es la fase más segura: solo agrega
   campos a `Sede` con el valor de la institución como default, **cero
   cambios de UX** para las instituciones que no la necesitan.

### 4.3 Ruta recomendada para el colegio público de 1.900 (si confirma multi-sede)

No hace falta completar las 5 fases (A–E de `docs/PROPUESTA_SEDES.md`)
antes de encenderlo — se puede matricular con el modelo actual (una sede
por defecto) y avanzar las fases en paralelo mientras ya está operando,
igual que dice el propio documento ("aditiva, sin romper nada"). Orden
sugerido si el volumen y la cantidad de sedes lo justifican desde el día 1:

1. **Fase A** (datos a la sede) antes o durante el onboarding — barato y
   sin riesgo, evita retrabajo inmediato.
2. **Fase C** (oferta por sede: matriz jornada × nivel) antes de que
   coordinación empiece a crear grupos — si se salta, se cargan grupos
   que después no calzan con lo que cada sede realmente ofrece según el
   C-600.
3. **Fase B, D, E** (fuente única, scoping de docentes/aulas,
   consolidación del tablero del rector) pueden ir después, con el
   colegio ya operando, sin bloquear la fecha de arranque.

### 4.4 Qué NO cambia por tener multi-sede

Por decisión ya confirmada en `docs/PROPUESTA_SEDES.md` sección 8: los
valores de matrícula/pensión siguen atados al **nivel de escolaridad**, no
a la sede — no hay fase de "finanzas por sede", y para el colegio público
esto es moot de todas formas (oficial = sin cobro, finanzas bloqueado).

---

## 5. Orden de trabajo sugerido

1. Levantamiento con el colegio público: ¿cuántas sedes? (sección 4.2) —
   en paralelo a todo lo demás, no bloquea el resto.
2. Fase B de código (sección 2) — se prueba y valida en Railway, sin
   depender de DO.
3. Preparar Droplet + Managed PostgreSQL + Managed Redis en DO (sección 1).
4. Migración de datos y corte (sección 3), en horario de bajo tráfico.
5. Si el colegio público confirma multi-sede: Fase A de sedes (sección 4.3)
   antes de cargar su estructura completa de grados/grupos.
6. Prueba de carga final ya en DO, con el volumen real de los 3 colegios,
   antes de anunciar la fecha de arranque en producción.

---

*Referencias: `docs/ESCALADO.md` (decisión de migrar a DO), `PRODUCCION_GUIA.md`
(playbook de VPS), `docs/PROPUESTA_SEDES.md` (diseño multi-sede), `docs/PRODUCCION.md`
(operación general, backups, comandos).*
