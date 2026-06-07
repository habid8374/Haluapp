# Módulo `admisiones`

Plataforma SaaS multi-institución para gestión de admisiones escolares.

Este documento es la guía operativa y de QA. Léelo antes de pasar a producción
o de tocar el módulo en profundidad.

---

## 1. Capacidades del módulo

- **Portal del postulante** (público vía UUID `access_token`):
  - Ver estado de admisión.
  - Pagar inscripción y matrícula vía Mercado Pago.
  - Subir documentos requeridos.
  - Agendar y cancelar entrevistas.

- **Backoffice** (autenticado por permisos Django):
  - Crear aspirantes manualmente o por **importación masiva Excel** con
    progreso en vivo, dry-run, cancelación y reintento.
  - Pipeline visual y dashboard.
  - Revisión de documentos entregados.
  - Admisión, matriculación y reversión.
  - Exportación a Excel de matriculados.

- **Pagos Mercado Pago**:
  - Preferencias creadas con timeout + reintentos + auditoría.
  - Webhook idempotente con verificación estricta de firma por institución.
  - Reconciliación bajo demanda (`reconciliar_pagos_mercadopago`).
  - Auditoría completa: tablas `WebhookEventoMercadoPago` y `LlamadaMercadoPago`.

- **Multi-tenant SaaS**:
  - Cada `InstitucionEducativa` tiene credenciales propias (SMTP + MP).
  - Toda query filtra por `institucion=` (verificado).
  - Constraint física `UNIQUE(institucion, numero_documento)` en `Aspirante`.

---

## 2. Dependencias externas (deben estar arriba)

| Componente | Para qué | Cómo verificar |
|---|---|---|
| **PostgreSQL** | BD principal | `python manage.py migrate` sin errores |
| **Redis** | Broker Celery + Channels | `python manage.py verificar_admisiones_health` |
| **Celery worker** | Importación masiva, futuras tareas | `celery -A proyecto_colegio worker -l INFO` |
| **Daphne / ASGI** | WebSocket (progreso en vivo) | Usar Daphne en prod, no `runserver` |
| **SMTP por institución** | Correos del aspirante | Configurar en admin de cada `InstitucionEducativa` |
| **Mercado Pago** | Pasarela de pagos | Configurar credenciales test/prod + webhook secret por institución |

### Comandos típicos para arrancar local (Windows / venv activo)

```powershell
# Terminal 1: servidor
python manage.py runserver

# Terminal 2: worker Celery (Windows requiere --pool=solo)
celery -A proyecto_colegio worker -l INFO --pool=solo
```

En producción usar Daphne/Uvicorn (ASGI) para que los WebSockets funcionen,
y un proceso supervisor (systemd/supervisor) para Celery.

---

## 3. Comandos de operación del módulo

### Importación masiva (operadores)
La operación normal está en la UI: **Admisiones → Importar Aspirantes**.
La tarea Celery `admisiones.procesar_importacion_aspirantes` procesa el
archivo en background y reporta progreso.

### Auditoría de duplicados de documento (recomendado pre-deploy)
```powershell
python manage.py detectar_duplicados_aspirantes
python manage.py detectar_duplicados_aspirantes --institucion 3
python manage.py detectar_duplicados_aspirantes --excel /tmp/dup.xlsx
python manage.py detectar_duplicados_aspirantes --exit-on-error  # útil en CI
```

### Reconciliación de pagos Mercado Pago (cierre de día)
```powershell
python manage.py reconciliar_pagos_mercadopago --desde 2026-05-01 --dry-run
python manage.py reconciliar_pagos_mercadopago --desde 2026-05-01
python manage.py reconciliar_pagos_mercadopago --institucion 3 --desde 2026-05-01 --hasta 2026-05-12
```

### Sandbox para QA (NO usar en producción)
```powershell
python manage.py seed_admisiones_demo --institucion 1
python manage.py seed_admisiones_demo --institucion 1 --grado "Sexto"
python manage.py seed_admisiones_demo --institucion 1 --reset
```

### Health-check operativo
```powershell
python manage.py verificar_admisiones_health
python manage.py verificar_admisiones_health --institucion 1
python manage.py verificar_admisiones_health --strict
```

---

## 4. Variables de entorno (`.env`)

Mínimas para que el módulo funcione:

```bash
# BD
DATABASE_URL=postgres://...

# Redis (broker Celery + Channels)
CELERY_BROKER_URL=redis://localhost:6379/0
REDIS_URL=redis://127.0.0.1:6379

# Celery (opcional, defaults razonables)
CELERY_WORKER_CONCURRENCY=4              # 1 si usas SQLite
CELERY_WORKER_PREFETCH_MULTIPLIER=1

# Email backend (institución usa el suyo, esto es el global)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend  # dev
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend  # prod
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=no-reply@halu.com
```

Las credenciales por institución (SMTP, Mercado Pago) se configuran en el
admin de Django bajo `Finanzas → Instituciones Educativas`.

---

## 5. Configuración inicial de una institución nueva (multi-tenant)

1. Crear la `InstitucionEducativa` en el admin.
2. Configurar SMTP (host, port, user, password, use_tls).
3. Configurar Mercado Pago:
   - `mp_access_token_test` (siempre).
   - `mp_access_token_prod` (cuando salga a vivo).
   - `mp_webhook_secret` (obligatorio, sin esto las notificaciones se rechazan).
   - `mp_modo_produccion` desmarcado al inicio (sandbox), marcado al ir a vivo.
4. Crear al menos un `Grado` en `gestion_academica`.
5. Crear los `DocumentoRequerido` necesarios (admin de admisiones).
6. Crear `HorarioDisponible` para entrevistas.
7. En el panel de Mercado Pago del cliente, registrar la URL de webhook con
   el parámetro de institución:
   ```
   https://tu-dominio.com/admisiones/pago/webhook_mp/?institucion_id=N
   ```
8. Correr `python manage.py verificar_admisiones_health --institucion N` para
   confirmar que todo está en orden.

---

## 6. Checklist de QA manual antes de producción

Marca cada paso después de probarlo manualmente con datos `seed_admisiones_demo`.

### A. Salud operativa
- [ ] `verificar_admisiones_health` reporta 0 errores.
- [ ] `detectar_duplicados_aspirantes --exit-on-error` sale con código 0.
- [ ] `runserver` arranca sin warnings críticos.
- [ ] El worker Celery está corriendo y procesa una tarea de prueba.

### B. Importación masiva
- [ ] Descargar plantilla Excel desde la UI.
- [ ] Subir un archivo en **modo simulación** y verificar que reporta errores
      sin crear aspirantes.
- [ ] Subir un archivo válido y ver el progreso en vivo (barra y contadores).
- [ ] Cancelar un lote a la mitad → estado pasa a `CANCELADO`, las filas ya
      creadas se conservan.
- [ ] Reintentar un lote `FALLIDO` o `CANCELADO` → crea un nuevo lote.
- [ ] Descargar el Excel de errores de un lote con filas fallidas.
- [ ] Verificar que un Aspirante creado tiene FK `lote_importacion` correcta.

### C. Portal del postulante
- [ ] Acceder al portal con `?token=<uuid>` válido funciona.
- [ ] Acceder con token inválido devuelve 404.
- [ ] El aspirante puede pagar inscripción → MP sandbox.
- [ ] Después de pagar, el aspirante pasa a `ADMITIDO` (vía webhook).
- [ ] El aspirante puede subir documentos válidos (PDF, JPG, PNG dentro de límites).
- [ ] Documentos inválidos (extensión, tamaño, MIME) son rechazados con mensaje claro.
- [ ] El aspirante puede agendar y **cancelar** entrevista (POST + CSRF).

### D. Mercado Pago
- [ ] La preferencia se crea (vista `crear_preferencia_mercadopago`).
- [ ] El usuario es redirigido al checkout de MP.
- [ ] Tras pagar en sandbox, el webhook llega y crea `PagoRegistrado`.
- [ ] Reenviar el mismo webhook (mismo `data.id` + body) NO crea un segundo `PagoRegistrado`.
- [ ] Webhook con firma inválida devuelve HTTP 401 y queda registrado en
      `WebhookEventoMercadoPago` con `firma_valida=False`.
- [ ] `LlamadaMercadoPago` registra cada `preference.create` y `payment.get`.
- [ ] `reconciliar_pagos_mercadopago --dry-run` no crea nada y reporta consistencia.

### E. Aislamiento multi-tenant
- [ ] Un usuario de la Institución A NO puede ver lotes de la Institución B
      (`/admisiones/importar/lote/<id>/` devuelve 404).
- [ ] Importar un Excel desde la Institución A crea aspirantes solo en A.
- [ ] El webhook con `?institucion_id=A` solo busca cuentas de A.
- [ ] El comando `reconciliar_pagos_mercadopago --institucion A` solo toca A.
- [ ] El comando `seed_admisiones_demo --institucion A` no crea nada en B.

### F. Backoffice
- [ ] Dashboard `/admisiones/dashboard/` carga sin errores.
- [ ] Pipeline `/admisiones/pipeline/` carga y permite cambiar estados.
- [ ] Revisión de documentos `/admisiones/revision-documentos/` lista y permite revisar.
- [ ] Matricular un aspirante `APROBADO_MATRICULA` con cuenta `PAGADO` lo
      pasa a `MATRICULADO` y crea `Estudiante` activo.
- [ ] Revertir matriculación funciona y el aspirante vuelve al estado anterior.
- [ ] Exportar matriculados a Excel produce un archivo válido.

---

## 7. Modelos clave

| Modelo | Qué representa |
|---|---|
| `Aspirante` | Postulante; FK a `lote_importacion`, `estudiante_creado`, `usuario`. |
| `LoteImportacionAspirantes` | Job de importación masiva con progreso, errores, task_id. |
| `DocumentoRequerido` | Tipo de documento que pide la institución (M2M con `Grado`). |
| `DocumentoEntregado` | Lo que sube el aspirante. |
| `HorarioDisponible` | Slot de cita disponible. |
| `CitaAgendada` | Cita reservada por un aspirante. |
| `CuentaPorCobrarEstudiante` | (en `finanzas`) cuenta del aspirante a pagar. |
| `PagoRegistrado` | (en `finanzas`) confirmación de pago. |
| `WebhookEventoMercadoPago` | (en `finanzas`) auditoría de notificaciones MP entrantes. |
| `LlamadaMercadoPago` | (en `finanzas`) auditoría de llamadas salientes a MP. |

---

## 8. Flujo de estados del aspirante

```
INSCRITO ──► (paga inscripción ó admin lo aprueba) ──► ADMITIDO
ADMITIDO ──► (agenda + entrevista + revisión docs) ──► EN_PROCESO
EN_PROCESO ──► (admin aprueba) ──► APROBADO_MATRICULA
APROBADO_MATRICULA ──► (paga matrícula) ──► MATRICULADO
              ó ──► (admin rechaza) ──► RECHAZADO
```

Las transiciones automáticas las dispara el webhook de MP (al ver pago
aprobado) y el comando `matricular_aspirante` (vía `aspirante.matricular()`).

---

## 9. Auditoría / debugging

| Pregunta | Dónde mirar |
|---|---|
| ¿Por qué no llegó el correo de bienvenida? | Logs + `EMAIL_BACKEND` + SMTP de la institución. |
| ¿Por qué un webhook devolvió 401? | Admin → `Eventos webhook Mercado Pago` → `firma_valida=False`. |
| ¿MP duplicó un pago? | Admin → `Eventos webhook Mercado Pago` (filtro `data_id`); el segundo evento debería decir "ya procesado". |
| ¿La importación está colgada? | Admin → `Lotes de importación de aspirantes` → ver `estado`, `errores`, `mensaje_error_general`. |
| ¿Por qué un aspirante no aparece en el listado del coordinador? | Verificar `institucion` del aspirante vs `institucion_asociada` del usuario. |
| ¿Por qué falla `payment.get`? | Admin → `Llamadas Mercado Pago` filtrar por `accion=payment.get` y ver `error_mensaje`. |

---

## 10. Pendientes futuros (no bloqueantes para producción)

- Dashboard "Salud MP" en `dashboard_financiero.html` con métricas de
  webhooks/llamadas (latencia, tasa de error últimas 24h).
- Cron nocturno para `reconciliar_pagos_mercadopago` por institución.
- Tests automatizados (pytest-django) que cubran:
  - Idempotencia del webhook.
  - Cancelación de lote.
  - Aislamiento SaaS (un usuario no puede ver datos ajenos).
- Migración a `google.genai` (ya hay `FutureWarning`).
