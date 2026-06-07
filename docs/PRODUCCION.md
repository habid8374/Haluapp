# Guía de Despliegue y Operación en Producción

Esta guía cubre el despliegue de HALU en un servidor de producción y la
configuración multi-institución (modelo SaaS).

---

## 1. Requisitos del servidor

| Componente | Versión mínima | Notas |
|---|---|---|
| Python | 3.12 | Probado con 3.12 y 3.14 |
| PostgreSQL | 14 | Recomendado en producción (no SQLite) |
| Redis | 6 | Broker de Celery + Channels (WebSockets) |
| Node | — | No se requiere; los assets son estáticos |
| Servidor ASGI | Daphne / Uvicorn | Para WebSockets de Channels |
| Servidor proxy | Nginx | Termina TLS, sirve `/static/` y `/media/` |

Las dependencias Python están en `requirements.txt`. Instalación:

```bash
python -m venv .venv
.venv/Scripts/activate     # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

---

## 2. Variables de entorno

Copia `.env.example` a `.env` y completa:

```bash
cp .env.example .env
```

### 2.1 Bloque obligatorio

| Variable | Descripción |
|---|---|
| `SECRET_KEY` | Generar uno nuevo y mantenerlo secreto |
| `DEBUG` | `False` en producción |
| `ALLOWED_HOSTS` | Dominios separados por coma |
| `DATABASE_URL` | DSN PostgreSQL (`postgres://user:pass@host:5432/db`) |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` |
| `CHANNELS_REDIS_URL` | `redis://localhost:6379/1` |

### 2.2 Bloque correo (SMTP global de fallback)

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=plataforma@halu.com
EMAIL_HOST_PASSWORD=app-password
DEFAULT_FROM_EMAIL=plataforma@halu.com
```

> ⚠ **Importante**: cada institución puede sobrescribir SMTP en su propio
> `InstitucionEducativa` (campos `email_host_*`). Si están configurados,
> se usan en lugar de los globales — esto permite que cada colegio envíe
> con su propio correo (y firma).

### 2.3 Bloque Celery

```env
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_PREFETCH_MULTIPLIER=1
```

* En **SQLite** (dev) usar `CELERY_WORKER_CONCURRENCY=1` para evitar
  *"database is locked"*.
* En **PostgreSQL** (producción) puedes subir a `4–8` según CPU del host.

---

## 3. Migraciones

**Orden recomendado** la primera vez en producción (BD vacía):

```bash
python manage.py migrate
```

**Si ya tienes datos** y vienes de una versión anterior:

```bash
# 1. Activar el entorno virtual
.venv\Scripts\activate

# 2. Aplicar todas las migraciones pendientes
python manage.py migrate

# 3. (Solo si traes datos legacy con conceptos sin nivel) backfill:
python manage.py crear_conceptos
```

### 3.1 Migraciones críticas recientes

| Migración | Qué hace |
|---|---|
| `admisiones.0005` | UNIQUE(institucion, numero_documento) en Aspirante. Aborta si hay duplicados. Antes ejecutar `manage.py detectar_duplicados_aspirantes`. |
| `admisiones.0006` | Agrega `LoteImportacionAspirantes.filas_con_advertencia` y reorganiza `errores`. |
| `finanzas.0008` | `WebhookEventoMercadoPago` y `LlamadaMercadoPago` (auditoría). |
| `finanzas.0009` | Nuevo flag `ConceptoPago.es_pago_pension`. **Sin este flag, las mensualidades NO se generan.** |

### 3.2 Si la migración `admisiones.0005` aborta

Significa que tu BD tiene aspirantes duplicados por (institución, documento).
Ejecuta primero:

```bash
python manage.py detectar_duplicados_aspirantes --exit-on-error
```

Limpia o fusiona los duplicados desde el admin de Django, y vuelve a correr `migrate`.

---

## 4. Configuración multi-institución (SaaS)

Cada `InstitucionEducativa` es un tenant. Los datos se aíslan por FK
`institucion`. Para preparar una nueva institución:

### 4.1 Datos básicos

1. **Crear `InstitucionEducativa`** desde admin Django: nombre, NIT, dirección,
   logo, dominio.

2. **Configurar SMTP** (campos `email_host_*` en la institución). Si no se
   configura, se usa el SMTP global del `.env`. **Sin SMTP no se envían
   correos** (bienvenida, cita, cambio de estado, recuperación de cuenta).

3. **Configurar Mercado Pago**:
   - `mp_modo_produccion`: `True` cuando el colegio quiera salir a producción.
   - `mp_access_token_test` / `mp_access_token_prod`: tokens del cabildo MP.
   - `mp_webhook_secret`: firma del webhook (obligatoria; sin esto **todas**
     las notificaciones se rechazan con HTTP 401).
   - URL del webhook a configurar en el panel MP del cliente:
     `https://<tu-dominio>/admisiones/pago/webhook_mp/`

4. **Crear `PeriodoAcademico`** con `activo=True` y `año_escolar=AAAA`.
   Este define el año lectivo que se usará para generar los Conceptos de
   Pago automáticos y las mensualidades.

5. **Crear `NivelEscolaridad`** (Preescolar, Primaria, Secundaria, etc.)
   con sus `valor_inscripcion_estandar`, `valor_matricula_estandar` y
   `valor_pension_estandar`. **Al guardar el nivel, una signal genera
   automáticamente los 12 ConceptoPago (1 inscripción + 1 matrícula + 10
   pensiones)** — ver [`CONCEPTOS_PAGO.md`](CONCEPTOS_PAGO.md).

6. **Crear `Grado`** (Pre-jardín, Transición, 1°, 2°, etc.) y asignar a
   cada uno su `nivel_escolaridad`. **Sin nivel asignado al grado, los
   aspirantes no podrán generar cuenta de pago de inscripción.**

### 4.2 Validar que la configuración esté completa

Ejecuta el health-check:

```bash
python manage.py verificar_admisiones_health --institucion <id>
```

Debe reportar `OK: 0 errores`. Ver detalle de cada paso en
[`HEALTH_CHECK.md`](HEALTH_CHECK.md).

---

## 5. Procesos del backend

En producción se levantan **3 procesos**:

### 5.1 ASGI (web)

```bash
daphne -b 0.0.0.0 -p 8000 proyecto_colegio.asgi:application
```

Nginx debe pasar `/ws/` con upgrade WebSocket a este puerto.

### 5.2 Celery worker (tareas asíncronas)

```bash
celery -A proyecto_colegio worker -l INFO --pool=solo   # Windows
celery -A proyecto_colegio worker -l INFO -c 4          # Linux
```

Tareas registradas (deben aparecer en el ping inicial):
- `admisiones.procesar_importacion_aspirantes`

### 5.3 Celery beat (opcional, para tareas programadas)

```bash
celery -A proyecto_colegio beat -l INFO
```

> Hoy no hay schedules registrados explícitamente. Si añades reportes
> diarios o reconciliación automática de MP, irían aquí.

---

## 6. Comandos operativos

| Comando | Cuándo usarlo |
|---|---|
| `python manage.py migrate` | Aplicar migraciones pendientes |
| `python manage.py crear_conceptos` | **Backfill** de ConceptoPago para Niveles que ya existían antes de la signal (Fase A) |
| `python manage.py crear_conceptos --institucion 1` | Limitar a una institución |
| `python manage.py crear_conceptos --año 2026` | Forzar un año lectivo distinto al activo |
| `python manage.py detectar_duplicados_aspirantes` | Auditar antes de migración 0005 |
| `python manage.py reconciliar_pagos_mercadopago --institucion <id> --desde YYYY-MM-DD --hasta YYYY-MM-DD` | Buscar pagos aprobados en MP que no se reflejaron en HALU (webhook caído, etc.) |
| `python manage.py sincronizar_pagos_matricula` | Buscar aspirantes pagados pero no matriculados, y matricularlos |
| `python manage.py verificar_admisiones_health` | Health-check operativo. Recomendado en CI/cron diario |
| `python manage.py seed_admisiones_demo --institucion <id>` | Datos demo para QA (NO usar en producción) |
| `python manage.py collectstatic --noinput` | Recolectar archivos estáticos |

---

## 7. Backups

### 7.1 Base de datos

Cron diario:

```bash
pg_dump -Fc -f /backups/halu-$(date +%F).dump halu_db
```

Retención: 30 días. Conservar al menos 1 backup mensual fuera del servidor.

### 7.2 Archivos subidos (`MEDIA_ROOT`)

Sincronizar con S3 / Backblaze:

```bash
aws s3 sync /var/www/halu/media s3://halu-media-backup --delete
```

### 7.3 Archivos importados (lotes Excel)

Quedan en `media/lotes_importacion_aspirantes/`. Útiles para reprocesar y
auditar. **No borrar** hasta que el lote tenga al menos 90 días.

---

## 8. Monitoreo y logs

### 8.1 Logs de aplicación

Por defecto van a stdout/stderr. En producción dirigir a archivos rotados
(p. ej. con `systemd-journal` o `logrotate`).

Niveles importantes:
- `INFO`: éxito de matrícula, sincronización de cuentas, envío de correos
- `WARNING`: configuración faltante (sin SMTP, sin ConceptoPago para nivel X)
- `ERROR`: fallo de pasarela, fallo de envío de correo, error de webhook

### 8.2 Health-check periódico

Recomendado: ejecutar cada 5 minutos como check de salud y emitir alerta
si exit code != 0:

```bash
python manage.py verificar_admisiones_health --strict
```

### 8.3 Auditoría de Mercado Pago

Las llamadas y webhooks quedan registrados en:
- `finanzas.LlamadaMercadoPago`: cada llamada a la API (preferencia, consulta de pago).
- `finanzas.WebhookEventoMercadoPago`: cada notificación recibida (deduplicada por `data_id`).

Acceso por admin Django para investigación post-mortem.

---

## 9. Seguridad

### 9.1 Recomendaciones obligatorias

- `DEBUG=False` en producción.
- TLS habilitado en Nginx (certificados Let's Encrypt).
- `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` activos.
- `ALLOWED_HOSTS` con la lista exacta de dominios.
- Rotar `SECRET_KEY` si se sospecha compromiso (invalida sesiones y tokens).
- Restringir acceso al admin Django por IP o por VPN.
- Mercado Pago: **siempre** configurar `mp_webhook_secret` por institución.

### 9.2 Permisos del usuario admin de cada institución

- Crear un grupo `Admin Institucional` con permisos sobre los modelos que el
  colegio debe gestionar (Estudiantes, Aspirantes, ConceptoPago, etc.) **sin**
  permisos de superusuario.
- Solo HALU debe tener acceso a `is_superuser=True`.

---

## 10. Procedimiento de actualización

```bash
# 1. Activar el venv y entrar al directorio del proyecto
cd /opt/halu/halu_plataform
source .venv/bin/activate

# 2. Pull del nuevo código
git pull origin main

# 3. Instalar dependencias nuevas (si las hay)
pip install -r requirements.txt

# 4. Aplicar migraciones
python manage.py migrate

# 5. Recolectar estáticos
python manage.py collectstatic --noinput

# 6. Reiniciar procesos
sudo systemctl restart halu-asgi
sudo systemctl restart halu-celery

# 7. Verificar salud
python manage.py verificar_admisiones_health --strict
```

---

## 11. Roles del modelo de usuario

El campo `Usuario.rol` controla los menús y los permisos de UI:

| Rol | Descripción |
|---|---|
| `aspirante` | Acceso solo al portal de admisión (token único) |
| `estudiante` | Acceso al dashboard académico (cursos, calificaciones, deberes) |
| `docente` | Acceso a sus cursos, libro de notas, observaciones |
| `coordinador` | Dashboard académico de su institución |
| `staff` (`is_staff=True`) | Acceso al admin Django (limitado por permisos) |
| `superuser` | Acceso total a todas las instituciones (solo HALU) |

---

## 12. Soporte

- Tickets de soporte (modelo `TicketSoporte`) los maneja el superadmin
  desde `/finanzas/superadmin/tickets/`.
- Logs y auditoría: ver sección 8.

Para más detalle del módulo de admisiones, ver
[`../admisiones/README.md`](../admisiones/README.md).
