# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ⚠️ REGLA CRÍTICA: SOFTWARE MULTI-INSTITUCIÓN

**ESTE ES UN SAAS MULTI-INSTITUCIÓN. ESTA REGLA ES INNEGOCIABLE Y APLICA A CADA LÍNEA DE CÓDIGO.**

Cada módulo, vista, modelo o modificación DEBE respetar el aislamiento por institución:

1. **Modelos**: Todo modelo que almacene datos de una institución DEBE tener:
   ```python
   institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
   ```

2. **Vistas**: Obtener la institución del usuario y filtrar SIEMPRE:
   ```python
   institucion = request.user.institucion_asociada  # campo correcto en User
   # Nunca usar request.user.institucion
   ```

3. **Querysets**: SIEMPRE filtrar por institución:
   ```python
   Modelo.objects.filter(institucion=institucion, ...)
   ```

4. **get_object_or_404**: SIEMPRE incluir el filtro de institución:
   ```python
   obj = get_object_or_404(Modelo, pk=pk, institucion=institucion)
   ```

5. **Creación de objetos**: SIEMPRE incluir la institución:
   ```python
   Modelo.objects.create(..., institucion=institucion)
   ```

6. **Superusuario**: El superusuario puede ver todo — omite el filtro solo si `request.user.is_superuser`.

---

## Stack Tecnológico

- **Backend**: Django 5.2, Python 3.12
- **Base de datos**: PostgreSQL (SQLite solo en tests locales con `USE_SQLITE=1`)
- **Cache/Cola**: Redis + Celery
- **IA**: Google Gemini (via `google-generativeai`, modelo `gemini-2.5-flash`)
- **Frontend**: Bootstrap 5 + Bootstrap Icons (`bi-*`)
- **Templates**: Django template language, base: `base_academico.html`
- **Tiempo real**: Django Channels + Redis (WebSockets)
- **Almacenamiento**: Cloudflare R2 / AWS S3 (o local en dev)
- **Pagos**: Mercado Pago (webhooks con firma HMAC-SHA256)
- **Encriptación de campos**: Fernet (`FERNET_KEY`)
- **Monitoreo**: Sentry (opcional, vía `SENTRY_DSN`)

## Comandos de Desarrollo

```bash
# Entorno virtual
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Linux/Mac

# Dependencias
pip install -r requirements.txt

# Base de datos
python manage.py makemigrations
python manage.py migrate

# Servidor
python manage.py runserver

# Celery (en terminal separada)
celery -A halu_plataform worker --loglevel=info

# Shell
python manage.py shell

# Tests locales con SQLite (sin PostgreSQL)
USE_SQLITE=1 python manage.py migrate
USE_SQLITE=1 python manage.py runserver
```

---

## Arquitectura del Proyecto

```
halu_plataform/
├── halu_plataform/          # Configuración Django (settings, urls raíz, celery)
├── gestion_academica/       # App principal académica
│   ├── models.py            # Todos los modelos académicos en un solo archivo
│   ├── signals.py           # Señales post_save (IA, permisos, notificaciones)
│   ├── apps.py              # Conecta signals y PagoRegistrado al arrancar
│   ├── views/               # Vistas modularizadas
│   │   ├── __init__.py      # Re-exporta todo: from .modulo import *
│   │   ├── _main.py         # Vistas principales (18 000+ líneas)
│   │   ├── ia.py            # Planeador IA con Gemini
│   │   ├── planeacion_semanal.py  # Mallas curriculares y planes semanales
│   │   └── api_movil.py     # Endpoints API v1 para móvil (57 endpoints)
│   ├── urls.py              # Todas las URLs bajo /academico/
│   ├── utils.py             # Funciones auxiliares compartidas
│   ├── templatetags/
│   │   └── gestion_academica_filters.py  # Filtros: get_item, etc.
│   └── templates/gestion_academica/
├── simulacros/              # Banco de preguntas ICFES y simulacros Saber
├── piar/                    # Planes Individuales de Ajuste Razonable (Decreto 1421)
├── admisiones/              # Portal de postulantes, importación y matrícula
├── finanzas/                # Finanzas, InstitucionEducativa, pagos, Mercado Pago
├── platform_control/        # Panel superadmin (oculto, acceso triple-clic)
├── docs/
│   └── API_REFERENCE.md     # Referencia completa de endpoints REST y WebSocket
└── templates/
    └── base_academico.html  # Template base con sidebars por rol
```

### Modularización de Vistas

Cuando se añade un nuevo módulo de vistas en `gestion_academica`:
1. Crear `gestion_academica/views/nuevo_modulo.py`
2. Añadir al final de `views/__init__.py`: `from .nuevo_modulo import *`
3. Registrar las URLs en `urls.py`

Para módulos nuevos independientes (como `simulacros` o `piar`):
1. Crear la app con `python manage.py startapp nombre`
2. Añadir a `INSTALLED_APPS` en `settings.py`
3. Incluir las URLs en `halu_plataform/urls.py` con `namespace`

---

## Sistema de Diseño HALU PULSE

**OBLIGATORIO** en todos los templates:

```django
{% extends "base_academico.html" %}

{% block titulo %}Título{% endblock %}

{% block extrastyles %}{{ block.super }}
<style>/* estilos adicionales */</style>
{% endblock %}

{% block contenido %}
<!-- Hero Banner — SIEMPRE con style="color:#fff" explícito en h2 y p -->
<div style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); border-radius:18px; padding:2rem; color:white; margin-bottom:1.5rem;">
  <h2 style="color:#fff;"><i class="bi bi-icon-aqui"></i> Título</h2>
  <p style="color:#fff;">Descripción</p>
</div>
<!-- Contenido en cards Bootstrap -->
{% endblock %}

{% block extra_js %}{{ block.super }}
<script>/* scripts adicionales */</script>
{% endblock %}
```

### Nombres de bloques en `base_academico.html`
| Bloque | Uso |
|---|---|
| `titulo` | `<title>` de la página |
| `extrastyles` | CSS adicional (siempre incluir `{{ block.super }}`) |
| `contenido` | Contenido principal de la página |
| `extra_js` | JS adicional al final (siempre incluir `{{ block.super }}`) |

> **Atención:** Los nombres son `titulo`, `extrastyles` y `contenido` — NO `title`, `extra_css` ni `content`.

- `{{ block.super }}` es **obligatorio** en `extrastyles` y `extra_js`
- **Bootstrap 5 sobreescribe `color` heredado en `<h2>`** — siempre poner `style="color:#fff"` explícito en cada `<h2>` y `<p>` dentro de un hero con fondo oscuro
- Gradientes: indigo-violeta (`#4f46e5 → #7c3aed`) para coordinador, azul oscuro (`#0d3b66 → #1d4ed8`) para académico, verde para docente, naranja para estudiante
- Siempre usar Bootstrap Icons (`bi bi-*`)

---

## Roles de Usuario

> **IMPORTANTE:** El campo en `Usuario` es `rol` (NOT `cargo`, NOT `role`). El CLAUDE.md anterior decía `cargo` — eso es incorrecto.

| Rol (`rol`) | Dashboard URL name | Descripción |
|---|---|---|
| `coordinador` | `dashboard_coordinador` | Gestiona mallas, supervisa planes, horarios, reportes |
| `docente` | `dashboard_docente` | Planes semanales, deberes, actividades, libro de notas |
| `estudiante` | `dashboard_estudiante` | Consulta notas, deberes, simulacros |
| `familiar` | `dashboard_familiar` (o portal_familiar) | Ve notas y pagos del hijo |
| `admin_institucion` | Admin panel | Configura la institución |

```python
# Correcto — siempre usar .rol
rol = getattr(user, 'rol', '') or ''

# Helpers estándar usados en simulacros y piar:
def _es_docente_o_coordinador(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('docente', 'coordinador', 'admin_institucion') or user.is_superuser

def _es_estudiante(user):
    return (getattr(user, 'rol', '') or '') == 'estudiante'

def _es_coordinador_o_admin(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('coordinador', 'admin_institucion') or user.is_superuser
```

### Grupos de Permisos Django (migración 0039)

Los grupos se crean automáticamente en la migración `0039_setup_permission_groups`. El signal `sincronizar_usuario_a_grupo_por_rol` añade automáticamente cada `Usuario` a su grupo al guardar.

| Grupo Django | Rol | Permisos incluidos |
|---|---|---|
| `docentes` | `docente` | view/add/change/delete deber, add/view/change registroasistencia, `acceso_libro_notas_docente`, view/add/change/delete actividadcalificable, add/view/change lecciondiaria, view/add/change/delete tipoactividad, view/add/change plansemanal, view/change entregadeber |
| `estudiantes` | `estudiante` | `ver_mis_deberes`, `puede_realizar_entrega_deber`, add/view entregadeber |
| `coordinadores` | `coordinador` | Todo lo de docentes + view registroasistenciadocente |
| `familiares` | `familiar` | `ver_deberes_estudiante_familiar` (en deber y entregadeber) |

```python
# ROL_GRUPO_MAP en signals.py
ROL_GRUPO_MAP = {
    'docente': 'docentes',
    'estudiante': 'estudiantes',
    'coordinador': 'coordinadores',
    'familiar': 'familiares',
}
```

---

## Módulo de Planeación Curricular

### Malla Curricular (coordinador)
- **Una sola malla** por materia + grado + año lectivo + institución (`unique_together`)
- Estructura colombiana: organizada por **períodos académicos** (1°–4°), NO por semanas/meses
- Campos clave por ítem: `eje_tematico`, `logro`, `ebc` (Estándares Básicos de Competencias), `dba` (Derechos Básicos de Aprendizaje), `competencias`, indicadores por nivel (`indicador_bajo/basico/alto/superior`), `metodologia`, `recursos`, `evaluacion`, `tiempo_semanas`
- Niveles de desempeño colombianos: Bajo (1–2.9), Básico (3–3.9), Alto (4–4.5), Superior (4.6–5)

### Plan Semanal (docentes)
- Flujo de estados: `BORRADOR → ENVIADO → APROBADO / CON_OBSERVACIONES`
- La semana siempre se normaliza al lunes: `d - timedelta(days=d.weekday())`
- Items pueden convertirse en `Deber` o `ActividadCalificable` directamente
- La conversión crea el objeto y lo enlaza via `OneToOneField` (`item.deber` o `item.actividad`)

---

## Módulo Simulacros (`simulacros/`)

**URL base:** `/simulacros/` · **Namespace:** `simulacros`

### Modelos

| Modelo | Descripción | Multi-tenant |
|---|---|---|
| `BancoPregunta` | Pregunta individual del banco ICFES | `institucion=NULL` → pública; `institucion=X` → privada |
| `OpcionPregunta` | Opción A/B/C/D de una pregunta | Via BancoPregunta |
| `Simulacro` | Examen compuesto de preguntas del banco | `institucion` FK obligatorio |
| `PreguntaSimulacro` | Through model Simulacro↔BancoPregunta (guarda `orden`) | Via Simulacro |
| `IntentoSimulacro` | Intento de un estudiante en un simulacro | `institucion` FK obligatorio |
| `RespuestaSimulacro` | Respuesta individual por pregunta en un intento | Via IntentoSimulacro |

**Choices importantes:**
- `grado_nivel`: `GRADO_3`, `GRADO_5`, `GRADO_7`, `GRADO_9`, `GRADO_11`
- `area`: `LECTURA_CRITICA`, `MATEMATICAS`, `CIENCIAS_NATURALES`, `SOCIALES`, `INGLES`, `LENGUAJE`, `FILOSOFIA`
- `nivel_dificultad`: `BASICO`, `MEDIO`, `ALTO`
- `estado` (Simulacro): `BORRADOR`, `PUBLICADO`, `CERRADO`

**Constraints:**
- `OpcionPregunta`: `unique_together = [['pregunta', 'letra']]`
- `PreguntaSimulacro`: `unique_together = [['simulacro', 'pregunta']]`
- `IntentoSimulacro`: `unique_together = [['simulacro', 'estudiante']]` — un intento por estudiante

**Métodos clave:**
- `Simulacro.esta_disponible()` → estado==PUBLICADO y fecha_inicio ≤ now ≤ fecha_cierre
- `IntentoSimulacro.calcular_y_guardar_puntaje()` → calcula % de aciertos, marca `completado=True`, guarda `fin`

### URLs

| Name | Path | Acceso |
|---|---|---|
| `banco_preguntas` | `banco/` | Docente/Coord |
| `crear_pregunta` | `banco/nueva/` | Docente/Coord |
| `editar_pregunta` | `banco/<pk>/editar/` | Docente/Coord |
| `eliminar_pregunta` | `banco/<pk>/eliminar/` | Docente/Coord (solo preguntas propias) |
| `importar_preguntas` | `banco/importar/` | Docente/Coord |
| `plantilla_excel` | `banco/plantilla/` | Docente/Coord |
| `generar_ia` | `banco/generar-ia/` | Docente/Coord (POST, JSON) |
| `guardar_ia` | `banco/guardar-ia/` | Docente/Coord (POST, JSON, máx 10 preguntas) |
| `lista_simulacros` | `` (root) | Docente/Coord |
| `crear_simulacro` | `nuevo/` | Docente/Coord |
| `editar_simulacro` | `<pk>/editar/` | Docente/Coord |
| `cambiar_estado` | `<pk>/estado/` | Docente/Coord |
| `eliminar_simulacro` | `<pk>/eliminar/` | Docente/Coord |
| `resultados_simulacro` | `<pk>/resultados/` | Docente/Coord |
| `simulacros_estudiante` | `mis-simulacros/` | Estudiante |
| `resolver_simulacro` | `resolver/<pk>/` | Estudiante |
| `resultado_intento` | `resultado/<pk>/` | Estudiante |

### Lógica de negocio
- Preguntas públicas (`es_publica=True, institucion=NULL`) son visibles a todas las instituciones (sembradas en migración `0002_seed_banco_preguntas`)
- Importación Excel: valida extensión `.xlsx`, content-type, y tamaño máx 5 MB antes de parsear
- Generación IA: respuesta de Gemini se valida con schema antes de enviarse al cliente (A03/A08)
- `imagen_url`: solo esquemas `http://` o `https://` permitidos (validación explícita)
- `resultado_intento` filtra por `institucion` — cross-tenant bloqueado (A01)

---

## Módulo PIAR (`piar/`)

**URL base:** `/piar/` · **Namespace:** `piar`  
**Marco legal:** Decreto 1421 de 2017 (Colombia) — inclusión educativa obligatoria

### Modelos

**`PIAR`** — Plan Individual de Ajuste Razonable
- FK: `institucion`, `estudiante`, `grado` (nullable), `docente_lider` (nullable)
- `unique_together = [['estudiante', 'año_lectivo']]` — un PIAR por estudiante por año
- `condicion` choices: `COG` (cognitiva), `MOT` (motora), `VIS` (visual), `AUD` (auditiva), `MUL` (múltiple), `APR` (aprendizaje), `CON` (TDAH/conducta), `TAL` (talento excepcional), `OTR` (otra)
- `estado` choices: `BORRADOR`, `ACTIVO`, `CERRADO`
- Campos de compromisos: `compromisos_familia`, `compromisos_docentes`, `compromisos_institucion`

**`AjustePIAR`** — Ajuste por materia y período
- FK: `piar`, `materia` (nullable)
- `periodo`: 1–4 (períodos académicos colombianos)
- `alcanzado` (Boolean): seguimiento de logro del ajuste

### URLs

| Name | Path | Acceso |
|---|---|---|
| `lista_piars` | `` | Docente/Coord |
| `crear_piar` | `nuevo/` | Solo Coord/Admin |
| `detalle_piar` | `<pk>/` | Docente/Coord |
| `editar_piar` | `<pk>/editar/` | Solo Coord/Admin |
| `eliminar_piar` | `<pk>/eliminar/` | Solo Coord/Admin |
| `crear_ajuste` | `<piar_pk>/ajuste/nuevo/` | Docente/Coord |
| `editar_ajuste` | `<piar_pk>/ajuste/<ajuste_pk>/editar/` | Docente/Coord |
| `eliminar_ajuste` | `<piar_pk>/ajuste/<ajuste_pk>/eliminar/` | Docente/Coord (con verificación de rol) |
| `actualizar_seguimiento` | `<piar_pk>/ajuste/<ajuste_pk>/seguimiento/` | Docente/Coord (AJAX, JsonResponse) |

### Lógica de negocio
- `IntegrityError` al crear PIAR duplicado (mismo estudiante+año) → se captura y muestra mensaje amigable
- `eliminar_ajuste` verifica rol explícitamente (no solo login) antes de borrar
- `actualizar_seguimiento` es un endpoint AJAX que actualiza `seguimiento` y `alcanzado` y devuelve `{"ok": true}`

---

## Módulo Admisiones (`admisiones/`)

**URL base:** `/admisiones/` · **Namespace:** `admisiones`

### Modelos principales

**`Aspirante`** — Postulante al colegio
- `unique_together = [['institucion', 'numero_documento']]`
- `estado` workflow: `INSCRITO → EN_PROCESO → ADMITIDO → APROBADO_MATRICULA → MATRICULADO` (o `RECHAZADO`)
- `access_token` (UUID): acceso al portal sin login (URL pública segura)
- Método `procesar_inscripcion_completa()` → `@transaction.atomic`, crea `Usuario` + `Estudiante` (inactivo), genera cuenta de inscripción
- Método `matricular()` → `@transaction.atomic`, activa estudiante, cambia `rol='estudiante'`, crea matrícula + 10 pensiones vía `sincronizar_cuentas_automaticas()`

**`DocumentoRequerido`** — Tipo de documento que la institución solicita
- `unique_together = [['institucion', 'nombre']]`
- M2M: `grados_aplicables`

**`DocumentoEntregado`** — Documento subido por el aspirante
- `unique_together = [['aspirante', 'documento_requerido']]`
- `save()` auto-asigna `institucion` desde `aspirante`

**`HorarioDisponible`** — Slot para entrevistas/exámenes
- `unique_together = [['institucion', 'fecha_hora_inicio', 'tipo_cita']]`
- Property `esta_disponible`: `cupos_ocupados < cupos_disponibles`

**`LoteImportacionAspirantes`** — Tarea de importación masiva desde Excel
- `estado`: `PENDIENTE → EN_PROCESO → COMPLETADO / FALLIDO / CANCELADO`
- `task_id`: UUID de la tarea Celery
- `dry_run`: validación sin persistencia
- Almacena errores en `errores` (JSONField)

### Lógica de negocio
- Importación masiva: Celery task procesa fila a fila, actualiza contadores en tiempo real, soporta `cancelacion_solicitada`
- `matricular()` NO revierte si falla la sincronización de pensiones — devuelve `ResultadoSincronizacionCuentas` para que la UI informe
- Webhook Mercado Pago en `/admisiones/pago/webhook_mp/` — verificación HMAC-SHA256 (`X-Signature`)

---

## Señales (`gestion_academica/signals.py`)

| Signal | Trigger | Qué hace |
|---|---|---|
| `sincronizar_usuario_a_grupo_por_rol` | `Usuario` post_save | Añade user al grupo Django según `rol` (ROL_GRUPO_MAP). Idempotente. |
| `sugerir_material_de_refuerzo` | `Calificacion` post_save | Si nota < mínimo aprobación → genera consejo IA (Gemini) + crea `Notificacion` |
| `analizar_observacion_convivencia` | `AnotacionObservador` post_save | Clasifica TIPO I/II/III (Ley 1620) con Gemini; abre `CasoConvivencia` automático para II/III; notifica coordinadores por Notificacion + WebSocket |
| `analizar_propuesta_candidato` | `Candidato` post_save | Analiza propuesta electoral con Gemini, guarda en `analisis_ia` |
| `gestionar_notificacion_documento_listo` | `SolicitudDocumento` pre_save | Detecta cambio a `LISTO_DESCARGA` → envía correo al egresado |
| `notificar_nuevo_ticket_a_superadmin` | `TicketSoporte` post_save | Envía correo a `SOFTWARE_CONTACT_EMAIL` usando SMTP de la institución |
| `crear_registros_asistencia_por_clase` | `RegistroAsistencia` post_save | Si estado=PRESENTE → crea registros por cada curso del día del alumno |
| `crear_conceptos_pago_para_nivel` | `NivelEscolaridad` post_save | Sincroniza ConceptoPago estándar (inscripción + matrícula + 10 pensiones); `transaction.on_commit` |
| `asignar_permisos_portal_al_guardar_familiar` | `Familiar` post_save | Asigna permisos del portal familiar al usuario vinculado |
| `notificar_docente_nueva_cita_reunion` | `CitaReunion` post_save | Crea Notificacion + evento WebSocket para el docente de la cita |
| `_enviar_correo_pago_recibido` | `PagoRegistrado` post_save | Solo pagos Mercado Pago → encola `notificar_pago_recibido.delay()` via Celery |

---

## ⚠️ REGLA CRÍTICA: CERO DIÁLOGOS DEL NAVEGADOR

**NUNCA usar diálogos nativos del navegador.** Está PROHIBIDO en todo el proyecto:
- ❌ `confirm('¿Estás seguro?')`
- ❌ `alert('Mensaje')`
- ❌ `prompt('Ingresa valor')`
- ❌ `onsubmit="return confirm(...)"`

**SIEMPRE usar el sistema de UI de la plataforma:**
- ✅ **Confirmaciones de eliminación** → Modal Bootstrap con botón de confirmar dentro de `<form method="post">`
- ✅ **Notificaciones de éxito/error** → `messages.success/error` de Django (ya integrado en `base_academico.html`)
- ✅ **Inputs dinámicos** → Modales Bootstrap con formularios internos

**Patrón estándar para confirmar eliminación:**
```html
<!-- Botón que abre el modal -->
<button type="button" class="btn-eliminar"
        data-bs-toggle="modal" data-bs-target="#modalEliminar"
        data-action="{% url 'app:vista_delete' item.pk %}"
        data-nombre="{{ item.nombre }}">
  <i class="bi bi-trash-fill"></i> Eliminar
</button>

<!-- Modal único para toda la página -->
<div class="modal fade" id="modalEliminar" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header border-0 pb-0">
        <div style="width:48px;height:48px;border-radius:50%;background:#fef2f2;display:flex;align-items:center;justify-content:center;">
          <i class="bi bi-exclamation-triangle-fill" style="color:#dc2626;font-size:1.2rem;"></i>
        </div>
        <button type="button" class="btn-close ms-auto" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body pt-2">
        <h5 class="fw-800 mb-1">¿Eliminar este elemento?</h5>
        <p id="modal-eliminar-nombre" class="text-muted mb-0" style="font-size:.85rem;"></p>
        <p class="text-danger mt-2 mb-0" style="font-size:.78rem;"><i class="bi bi-info-circle me-1"></i>Esta acción no se puede deshacer.</p>
      </div>
      <div class="modal-footer border-0">
        <button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cancelar</button>
        <form id="form-eliminar" method="post">
          {% csrf_token %}
          <button type="submit" class="btn btn-danger btn-sm"><i class="bi bi-trash-fill me-1"></i>Sí, eliminar</button>
        </form>
      </div>
    </div>
  </div>
</div>

<script>
document.querySelectorAll('[data-bs-target="#modalEliminar"]').forEach(btn => {
  btn.addEventListener('click', function() {
    document.getElementById('form-eliminar').action = this.dataset.action;
    document.getElementById('modal-eliminar-nombre').textContent = this.dataset.nombre || '';
  });
});
</script>
```

---

## Patrones Críticos

### Helper para institución en vistas
```python
def _get_institucion(request):
    return getattr(request.user, 'institucion_asociada', None)
```

### Filtro `get_item` en templates
Para acceder a diccionarios con claves dinámicas en templates:
```django
{% load gestion_academica_filters %}
{{ mi_dict|get_item:variable_clave }}
```

### Notificaciones
```python
Notificacion.objects.create(
    destinatario=usuario,   # campo es 'destinatario', no 'usuario'
    mensaje="Cuerpo",
    enlace="/ruta/opcional/",
    institucion=institucion,
)
```

### Importación de `Group` en ia.py
```python
from django.contrib.auth.models import Group  # Ya añadido — no duplicar
```

### WebSocket — notificación en tiempo real a un usuario
```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(
    f"user_{user.pk}",
    {
        "type": "send_notification",
        "kind": "tipo_evento",
        "title": "Título",
        "message": "Mensaje",
        "url": "/ruta/",
        "severity": "info",  # info | warning | danger | success
    }
)
```

---

## Variables de Entorno

### Obligatorias en producción

| Variable | Descripción |
|---|---|
| `SECRET_KEY` | Clave secreta Django |
| `FERNET_KEY` | Clave de cifrado para credenciales SMTP de instituciones (base64) |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` | Conexión PostgreSQL |
| `REDIS_URL` | Redis para Django Channels (default: `redis://127.0.0.1:6379/3`) |
| `CELERY_BROKER_URL` | Redis para Celery (default: `redis://localhost:6379/0`) |
| `CELERY_RESULT_BACKEND` | Redis para resultados Celery (default: `redis://localhost:6379/1`) |
| `SUPERADMIN_MASTER_PASSWORD` | Clave maestra del panel `/halu-control/` |

### Opcionales / por funcionalidad

| Variable | Descripción | Default |
|---|---|---|
| `DEBUG` | Modo debug | `False` |
| `ALLOWED_HOSTS` | Hosts permitidos (comma-separated) | localhost, 127.0.0.1, *.ngrok, *.trycloudflare |
| `CSRF_TRUSTED_ORIGINS` | Orígenes CSRF adicionales | *.ngrok-free.app, *.trycloudflare.com |
| `USE_SQLITE` | Fuerza SQLite (solo tests locales) | unset |
| `DB_SSLMODE` | SSL mode PostgreSQL | unset |
| `DB_CONN_MAX_AGE` | Pool de conexiones (segundos) | `60` |
| `AWS_STORAGE_BUCKET_NAME` | Bucket S3/R2 para archivos | unset (usa local) |
| `AWS_ACCESS_KEY_ID` | AWS/R2 access key | unset |
| `AWS_SECRET_ACCESS_KEY` | AWS/R2 secret key | unset |
| `AWS_S3_REGION_NAME` | Región S3 | `auto` |
| `AWS_S3_ENDPOINT_URL` | Endpoint Cloudflare R2 | unset |
| `EMAIL_HOST` | SMTP server global (fallback) | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_USE_TLS` | Usar TLS | `True` |
| `EMAIL_HOST_USER` | Usuario SMTP | `''` |
| `EMAIL_HOST_PASSWORD` | Password SMTP | `''` |
| `BREVO_API_KEY` | API key de Brevo (email transaccional) | `''` |
| `BREVO_SENDER_EMAIL` | Email verificado en Brevo | `''` |
| `BREVO_SENDER_NAME` | Nombre del remitente Brevo | `Halu Plataforma` |
| `SENTRY_DSN` | URL de Sentry para monitoreo de errores | `''` |
| `GIT_COMMIT` | Tag de release (para Sentry) | `unknown` |
| `CELERY_WORKER_CONCURRENCY` | Procesos worker Celery | `4` |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | Prefetch de tareas | `1` |

> **Nota sobre Gemini:** Cada institución almacena su propia `google_api_key` en la BD (campo cifrado con Fernet), NO en variables de entorno globales. Se obtiene con `finanzas.institucion_credentials.google_api_key(institucion)`.

---

## Panel de Control del Propietario (`platform_control`)

| Concepto | Valor |
|---|---|
| URL base | `/halu-control/` |
| App Django | `platform_control/` |
| Namespace de URLs | `platform_control` |
| Autenticación | `is_superuser` de Django **+** clave maestra (`SUPERADMIN_MASTER_PASSWORD`) |

### Acceso oculto — triple clic en el logo
Desde `/login/`: **3 clics rápidos sobre el logo** (< 700 ms) → redirige a `/halu-control/login/`

```js
// En gestion_academica/templates/registration/login.html
(function () {
  var clicks = 0, timer;
  function bindLogo(el) {
    if (!el) return;
    el.addEventListener('click', function () {
      clicks++;
      clearTimeout(timer);
      timer = setTimeout(function () { clicks = 0; }, 700);
      if (clicks >= 3) { clicks = 0; window.location.href = '/halu-control/login/'; }
    });
  }
  bindLogo(document.querySelector('.school-brand img'));
  bindLogo(document.querySelector('.form-header img'));
})();
```

> **No agregar ningún enlace visible** que apunte a este panel.

### Vistas disponibles
| Vista | URL | Descripción |
|---|---|---|
| `dashboard` | `/halu-control/` | KPIs globales, ingresos, config MP |
| `login_view` | `/halu-control/login/` | Login con clave maestra |
| `lock_view` | `/halu-control/lock/` | Cierra la sesión del panel |
| `toggle_institucion` | `/halu-control/institucion/<pk>/toggle/` | Activa/desactiva institución |
| `tickets_view` | `/halu-control/soporte/` | Todos los tickets de soporte |
| `ticket_detail_view` | `/halu-control/soporte/<ticket_id>/` | Detalle y respuesta de ticket |
| `cerrar_ticket_view` | `/halu-control/soporte/<ticket_id>/cerrar/` | Cierra un ticket |
| `mantenimiento_dashboard` | `/halu-control/mantenimiento/` | Health-check del sistema |
| `mantenimiento_ejecutar` | `/halu-control/mantenimiento/ejecutar/` | Lanza diagnóstico Celery |
| `mantenimiento_detalle` | `/halu-control/mantenimiento/<pk>/` | Log en vivo via WebSocket |
| `mantenimiento_estado_api` | `/halu-control/mantenimiento/<pk>/estado/` | Endpoint JSON de estado |

---

## Migraciones Relevantes

| Migración | App | Descripción |
|---|---|---|
| `0027_malla_curricular_plan_semanal` | gestion_academica | Crea `MallaCurricular`, `ItemMalla`, `PlanSemanal`, `ItemPlanSemanal` |
| `0028_itemmalla_estructura_colombiana` | gestion_academica | Estructura colombiana completa (EBC, DBA, indicadores por nivel) |
| `0039_setup_permission_groups` | gestion_academica | Crea grupos Django (docentes/estudiantes/coordinadores/familiares) y asigna permisos |
| `0001_initial` | simulacros | Crea todos los modelos del módulo de simulacros |
| `0002_seed_banco_preguntas` | simulacros | Siembra 108 preguntas públicas ICFES (es_publica=True, institucion=NULL) |
| `0001_initial` | piar | Crea `PIAR` y `AjustePIAR` |

---

## Dependencias entre Módulos

```
simulacros  ←  finanzas.InstitucionEducativa
            ←  gestion_academica.Estudiante, Usuario
            ←  google.generativeai (Gemini — generación de preguntas IA)
            ←  openpyxl (importación/exportación Excel)

piar        ←  finanzas.InstitucionEducativa
            ←  gestion_academica.Estudiante, Grado, Materia, Usuario

admisiones  ←  finanzas.InstitucionEducativa, CuentaPorCobrarEstudiante, ConceptoPago
            ←  gestion_academica.Grado, Usuario, Estudiante, NivelEscolaridad
            ←  Mercado Pago API
            ←  Celery (importación masiva async)

gestion_academica.signals
            ←  google.generativeai (análisis IA de calificaciones, convivencia, propuestas)
            ←  django.channels (WebSocket push de notificaciones)
            ←  Celery (emails async: inasistencia, pagos)
            ←  finanzas.PagoRegistrado, CuentaPorCobrarEstudiante
```

---

## Referencia de API

Ver `docs/API_REFERENCE.md` para la documentación completa de todos los endpoints REST, WebSockets y Webhooks (80+ endpoints).
