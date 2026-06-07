# Documentación HALU – Plataforma SaaS Multi-institución

Esta carpeta concentra la documentación operativa del backend Django de HALU.
Cada documento cubre un aspecto distinto del despliegue y mantenimiento.

| Documento | Tema |
|---|---|
| [`PRODUCCION.md`](PRODUCCION.md) | Guía completa de despliegue, configuración por institución, migraciones, comandos operativos |
| [`CONCEPTOS_PAGO.md`](CONCEPTOS_PAGO.md) | Cómo se generan automáticamente los Conceptos de Pago a partir de Niveles de Escolaridad |
| [`MATRICULA_Y_PENSIONES.md`](MATRICULA_Y_PENSIONES.md) | Flujo completo: aspirante → matrícula → 10 pensiones del año lectivo |
| [`BLOQUEO_POR_MORA.md`](BLOQUEO_POR_MORA.md) | Fase C – Bloqueo real del portal del estudiante por mensualidades vencidas |
| [`HEALTH_CHECK.md`](HEALTH_CHECK.md) | Comando `verificar_admisiones_health` y qué reporta cada paso |
| [`DASHBOARD_MANTENIMIENTO.md`](DASHBOARD_MANTENIMIENTO.md) | Dashboard de mantenimiento del super-admin (health-check en vivo desde la UI) |
| [`FEEDBACK_TAREAS_IA.md`](FEEDBACK_TAREAS_IA.md) | Patrón de feedback en vivo para tareas IA (Celery + polling + toasts) |
| [`ACCESO_ACTIVIDADES_Y_CUESTIONARIOS.md`](ACCESO_ACTIVIDADES_Y_CUESTIONARIOS.md) | Reglas compartidas de acceso: actividades calificables, APIs y cuestionarios |
| [`GEMINI_SDK.md`](GEMINI_SDK.md) | Aviso deprecación `google.generativeai` y plan de migración a `google.genai` |

## Documentación específica por módulo

- [`../admisiones/README.md`](../admisiones/README.md) – Módulo de admisiones (aspirantes, importación masiva, Mercado Pago, lotes)
