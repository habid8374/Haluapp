# HALU Plataforma SaaS Multi-institución

Backend Django + Celery + Channels para colegios. Gestión académica,
admisiones, finanzas, e-learning, todo aislado por institución.

---

## Documentación

| Archivo | Tema |
|---|---|
| [`docs/PRODUCCION.md`](docs/PRODUCCION.md) | **Guía completa de despliegue, comandos, backups, monitoreo** |
| [`docs/CONCEPTOS_PAGO.md`](docs/CONCEPTOS_PAGO.md) | Generación automática de Conceptos de Pago al crear Niveles |
| [`docs/MATRICULA_Y_PENSIONES.md`](docs/MATRICULA_Y_PENSIONES.md) | Flujo aspirante → matrícula → 10 mensualidades |
| [`docs/HEALTH_CHECK.md`](docs/HEALTH_CHECK.md) | Comando `verificar_admisiones_health` |
| [`admisiones/README.md`](admisiones/README.md) | Módulo admisiones (importación masiva, MP, lotes) |

---

## Quickstart desarrollo

```bash
git clone <repo>
cd halu_plataform
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # Linux/Mac
pip install -r requirements.txt

cp .env.example .env             # editar credenciales
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

En otra terminal:

```bash
celery -A proyecto_colegio worker -l INFO --pool=solo  # Windows
# celery -A proyecto_colegio worker -l INFO -c 4       # Linux
```

---

## Motor de base de datos

- **Producción**: PostgreSQL 14+. Configurar via `.env`: `DB_HOST`,
  `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`.
- **Fallback dev**: `USE_SQLITE=1` cae a SQLite (`db.sqlite3`).

---

## Multiinstitucional (SaaS)

- BD compartida; aislamiento por FK `institucion` en los modelos.
- Credenciales **por institución** (no en `settings.py`):
  - SMTP (correo de bienvenida, citas, cambios de estado).
  - Mercado Pago (token + webhook secret).
  - Google/Gemini (asistente IA).
- Cada institución tiene sus propios `NivelEscolaridad`, `Grado`,
  `ConceptoPago`, `PeriodoAcademico`, `Estudiantes`, `Aspirantes`, etc.

---

## Comandos operativos clave

```bash
# Health-check completo (recomendado en cron cada 5 min)
python manage.py verificar_admisiones_health --strict

# Backfill de Conceptos de Pago para Niveles antiguos
python manage.py crear_conceptos

# Reconciliación de pagos perdidos (webhook caído)
python manage.py reconciliar_pagos_mercadopago --institucion 1 --desde 2026-05-01 --hasta 2026-05-12

# Sincronizar matrículas pendientes
python manage.py sincronizar_pagos_matricula
```

Detalle completo en [`docs/PRODUCCION.md`](docs/PRODUCCION.md).
