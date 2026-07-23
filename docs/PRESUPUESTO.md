# Presupuesto de la Plataforma

Este documento distingue dos tipos de gasto:

1. **Gastos fijos de la plataforma** — los paga el dueño de HALU, no dependen de qué colegio esté conectado.
2. **Gastos variables por institución** — cada colegio paga los suyos con sus propias credenciales, nunca desde una cuenta compartida (ver regla de credenciales de comunicación en `CLAUDE.md`).

Las cifras de este documento son **estimaciones**, no facturas reales. Si tienes las facturas de Railway/Cloudflare a mano, reemplaza los rangos por los valores reales y actualiza este archivo.

---

## 1. Gastos fijos de la plataforma (dueño)

Infraestructura compartida por todas las instituciones — no escala 1:1 con el número de colegios hasta que el tráfico crezca de forma significativa.

| Concepto | Servicio | Estimado mensual (USD) |
|---|---|---|
| Hosting web (Django + Channels) | Railway | $5–20 |
| Worker de Celery + Beat | Railway | $5–15 |
| Base de datos PostgreSQL | Railway (plugin) | $5–15 |
| Redis (colas Celery + WebSockets) | Railway (plugin) | $5–10 |
| Almacenamiento de archivos | Cloudflare R2 | $1–5 (bajo volumen inicial) |
| Dominio `haluplataform.com` | Registrador | ~$1–2/mes (prorrateado anual) |
| Monitoreo de errores | Sentry | $0 (plan gratuito alcanza al inicio) |
| **Total aproximado** | | **≈ $22–67/mes** |

> Estas cifras son rangos típicos para esta combinación de servicios con tráfico bajo (del orden de un colegio de ~200-300 estudiantes). No están tomadas de una factura real de este proyecto.

### Servicios Railway detectados en el repo

- `railway.celery.json` → worker + beat combinado (`celery -A proyecto_colegio worker --beat`)
- `railway.beat.json` → beat por separado (verificar si ambos están activos o si uno es redundante)
- Servicio web (Daphne/Django, no versionado en un `railway.*.json` propio)

---

## 2. Gastos variables por institución (cada colegio, NO el dueño)

Por la arquitectura multi-tenant, estas credenciales viven en `InstitucionEducativa` y cada colegio configura las suyas. Si una institución no configura algo opcional, esa función simplemente no se activa para ella — nunca se usa una cuenta de respaldo compartida.

| Concepto | Campo en `InstitucionEducativa` | ¿Obligatorio? |
|---|---|---|
| Google Gemini (IA: asistente, calificaciones, convivencia) | `google_api_key` | Sí — obligatorio para crear la institución |
| Claude / Anthropic (respaldo automático de Gemini) | `claude_api_key` | No — opcional, solo se usa si Gemini falla |
| Brevo (correo transaccional) | `brevo_api_key` | No — opcional, SMTP propio como respaldo |
| Mercado Pago (comisión por pago procesado) | `mp_access_token_prod` | Depende de si el colegio usa pagos digitales |

### Estimado de IA para un colegio de ~210 estudiantes

- **Gemini 2.5 Flash** es muy económico. Para el volumen de un solo colegio (asistente HALU, sugerencias de refuerzo, análisis de convivencia, planeador IA), el gasto típico ronda **$1–5 USD/mes**.
- **Claude como respaldo** (`claude_api_key`) solo se consume cuando Gemini falla. Con Haiku 4.5 (~$1 / $5 por millón de tokens de entrada/salida) el costo adicional sería marginal — probablemente **menos de $1 USD/mes**, salvo que Gemini falle de forma constante (lo que sería señal de revisar la configuración de esa institución, no de que Claude sea caro).
- Precios de referencia (verificar vigencia antes de presupuestar a largo plazo):
  - Claude Haiku 4.5: ~$1.00 / $5.00 por millón de tokens (entrada/salida)
  - Claude Sonnet 5: ~$2.00 / $10.00 por millón de tokens (precio introductorio vigente hasta 2026-08-31), luego $3.00 / $15.00

> **Nunca comprar API keys de terceros/revendedores** (marketplaces tipo G2A y similares). Ese tipo de oferta suele ser clave robada o de cuenta ajena — riesgo de revocación repentina y de incidente de seguridad para el colegio que dependa de ella. Las claves se obtienen directamente desde `console.anthropic.com` (Claude) o Google AI Studio (Gemini).

---

## 3. Resumen

**Lo que sale de tu bolsillo como dueño de la plataforma:** los ~$22–67/mes de infraestructura (sección 1).

**Lo que no te cuesta nada:** el consumo de IA de cada colegio — cada institución trae su propia clave de Gemini (obligatoria) y, opcionalmente, su propia clave de Claude como respaldo. Así está diseñado a propósito: obliga a cada colegio a tener su propia cuenta y evita que el consumo de uno afecte el plan de otro.

---

## Próximos pasos sugeridos

- Reemplazar los rangos de la sección 1 por las cifras reales de las facturas de Railway y Cloudflare R2.
- Si el número de instituciones crece de forma significativa, revisar si conviene un plan Railway superior (más CPU/RAM para el worker de Celery) — eso sí sería un gasto fijo adicional del dueño.
- Confirmar si `railway.beat.json` y el `--beat` dentro de `railway.celery.json` están corriendo ambos a la vez (duplicaría las tareas programadas) o si uno de los dos está en desuso.
