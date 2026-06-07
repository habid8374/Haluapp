# Health-Check Operacional

Comando: `python manage.py verificar_admisiones_health`

Este comando recorre 7 áreas críticas y reporta `[OK]`, `[WARN]` o `[ERR]`
para cada elemento. Salida con exit code 1 si hay errores.

---

## Uso

```bash
# Verificar todo
python manage.py verificar_admisiones_health

# Solo una institución
python manage.py verificar_admisiones_health --institucion 1

# Modo estricto: warnings también fallan
python manage.py verificar_admisiones_health --strict
```

---

## Pasos verificados

### `[1/7] Redis (broker)`

Verifica que Redis acepta `PING` en `CELERY_BROKER_URL`.

**Errores comunes**:
- `CELERY_BROKER_URL no está definido en settings.` → revisar `.env`.
- `No se pudo conectar a Redis (...): ConnectionRefusedError` → arrancar Redis o revisar firewall.

### `[2/7] Celery (workers)`

Pinguea workers vivos y verifica que `admisiones.procesar_importacion_aspirantes` esté registrada.

**Errores comunes**:
- `No hay workers Celery respondiendo.` → arrancar `celery -A proyecto_colegio worker`.
- `Tarea NO está registrada en el worker` → revisar que `admisiones.tasks` esté en el `include` de `proyecto_colegio/celery.py`.

### `[3/7] Django Channels (capa de canal)`

Hace `group_send` sintético para validar que la capa Redis Channels funciona.
Si falla, los WebSockets de progreso de importación masiva no funcionarán.

### `[4/7] Plantillas críticas`

Verifica que las plantillas de admisiones existan:
- `admisiones/portal_postulante.html`
- `admisiones/portal_postulante_pagado.html`
- `admisiones/pago_procesando.html`
- `admisiones/lote_progreso.html`
- `admisiones/importar_aspirantes.html`
- `admisiones/dashboard.html`
- `emails/bienvenida_aspirante.html`

### `[5/7] URLs nombradas críticas`

Verifica que `reverse()` resuelve las URLs que el portal y los correos usan.

### `[6/7] Configuración por institución (multi-tenant)`

Para cada institución (o la indicada con `--institucion`):

- **SMTP**: que `email_host`, `email_host_user`, `email_host_password` estén configurados.
  - Si los 3 están vacíos: `[WARN]` (cae al SMTP global del `.env`).
  - Si uno está parcial: `[WARN]` (configuración inconsistente).
- **Mercado Pago**: que el access_token activo (test/prod según `mp_modo_produccion`) y el `mp_webhook_secret` estén configurados.
  - **Sin webhook_secret = `[ERR]`**: todas las notificaciones MP serán rechazadas con HTTP 401.

### `[7/7] Conceptos de Pago por nivel`

Para cada nivel de escolaridad asignado a algún Grado:

- **Inscripción**: debe haber exactamente 1 ConceptoPago con `es_pago_inscripcion=True` para ese nivel.
- **Matrícula**: debe haber exactamente 1 ConceptoPago con `es_pago_matricula=True` para ese nivel.
- **Pensiones**: debe haber al menos 10 ConceptoPago con `es_pago_pension=True` para ese nivel.

**Si reporta `[ERR]`**: ejecutar `python manage.py crear_conceptos` (idempotente).

---

## Integración con monitoreo

### CRON cada 5 min (alerta si falla)

```bash
*/5 * * * * cd /opt/halu/halu_plataform && \
    .venv/bin/python manage.py verificar_admisiones_health --strict \
    || /usr/local/bin/notify-admin "HALU health-check failed"
```

### CI antes de deploy

```yaml
# .github/workflows/deploy.yml
- name: Health-check post-migration
  run: |
    python manage.py migrate --noinput
    python manage.py verificar_admisiones_health --strict
```

---

## Salida ejemplo

```
=== HEALTH-CHECK ADMISIONES ===

[1/7] Redis (broker)
  [OK]   Redis responde PING en redis://localhost:6379/0.

[2/7] Celery (workers)
  [OK]   Workers Celery vivos: ['celery@host01']
  [OK]   Tarea `admisiones.procesar_importacion_aspirantes` registrada.

[3/7] Django Channels (capa de canal)
  [OK]   Channel layer responde (RedisChannelLayer).

[4/7] Plantillas críticas
  [OK]   Plantilla 'admisiones/portal_postulante.html' encontrada.
  ...

[5/7] URLs nombradas críticas
  [OK]   URL 'admisiones:dashboard_admisiones' resuelve a /admisiones/dashboard/.
  ...

[6/7] Configuración por institución (multi-tenant)
  -> ESCUELA DE PRUEBA (id=1)
  [OK]       SMTP configurado (smtp.gmail.com, user=plataforma@halu.com).
  [OK]       Mercado Pago [SANDBOX]: access_token configurado.
  [OK]       Mercado Pago: webhook_secret configurado.

[7/7] Conceptos de Pago (inscripción + matrícula) por nivel
  -> ESCUELA DE PRUEBA (id=1)
  [OK]       [Inscripción] Nivel 'Preescolar': 1 concepto configurado.
  [OK]       [Matrícula]   Nivel 'Preescolar': 1 concepto configurado.
  [OK]       [Pensiones]   Nivel 'Preescolar': 10 ConceptoPago de pensión.

==================================================
OK: 0 errores, 0 warnings.
```
