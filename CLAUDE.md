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
- **Base de datos**: PostgreSQL
- **Cache/Cola**: Redis + Celery
- **IA**: Google Gemini (via `google-generativeai`)
- **Frontend**: Bootstrap 5 + Bootstrap Icons (`bi-*`)
- **Templates**: Django template language, base: `base_academico.html`

## Comandos de Desarrollo

```bash
# Entorno virtual
cd halu_plataform
python -m venv venv
venv\Scripts\activate  # Windows

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
```

---

## Arquitectura del Proyecto

```
halu_plataform/
├── halu_plataform/          # Configuración Django (settings, urls raíz, celery)
├── gestion_academica/       # App principal académica
│   ├── models.py            # Todos los modelos académicos en un solo archivo
│   ├── views/               # Vistas modularizadas
│   │   ├── __init__.py      # Re-exporta todo: from .modulo import *
│   │   ├── _main.py         # Vistas principales (dashboard, cursos, etc.)
│   │   ├── ia.py            # Planeador IA con Gemini
│   │   ├── planeacion_semanal.py  # Mallas curriculares y planes semanales
│   │   └── ...              # Otros módulos
│   ├── urls.py              # Todas las URLs bajo /academico/
│   ├── utils.py             # Funciones auxiliares compartidas
│   ├── templatetags/
│   │   └── gestion_academica_filters.py  # Filtros: get_item, etc.
│   └── templates/gestion_academica/
├── finanzas/                # App de finanzas (contiene InstitucionEducativa)
├── usuarios/                # App de usuarios (contiene el modelo User extendido)
└── templates/
    └── base_academico.html  # Template base con sidebars por rol
```

### Modularización de Vistas

Cuando se añade un nuevo módulo de vistas:
1. Crear `gestion_academica/views/nuevo_modulo.py`
2. Añadir al final de `views/__init__.py`: `from .nuevo_modulo import *`
3. Registrar las URLs en `urls.py`

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
<!-- Hero Banner -->
<div style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); border-radius:18px; padding:2rem; color:white; margin-bottom:1.5rem;">
  <h2><i class="bi bi-icon-aqui"></i> Título</h2>
  <p>Descripción</p>
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
- Gradientes: indigo-violeta (`#4f46e5 → #7c3aed`) para coordinador, otros colores para otros roles
- Siempre usar Bootstrap Icons (`bi bi-*`)

---

## Roles de Usuario

| Rol (`cargo`) | Dashboard | Descripción |
|---|---|---|
| `coordinador` | `dashboard_coordinador` | Gestiona mallas, supervisa planes, horarios |
| `docente` | `dashboard_docente` | Planes semanales, deberes, actividades |
| `estudiante` | `dashboard_estudiante` | Consulta notas, deberes |
| `admin_institucion` | Admin panel | Configura la institución |

El campo en `User` es `cargo` (no `role`). Para elegir cargo en formularios se usa `cargo_elegir`.

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
// Conectar botones al modal
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

### Importación de `Group` en ia.py
```python
from django.contrib.auth.models import Group  # Ya añadido — no duplicar
```

### Filtro `get_item` en templates
Para acceder a diccionarios con claves dinámicas en templates:
```django
{% load gestion_academica_filters %}
{{ mi_dict|get_item:variable_clave }}
```

### Helper para institución en vistas
```python
def _get_institucion(request):
    return getattr(request.user, 'institucion_asociada', None)
```

### Notificaciones
```python
Notificacion.objects.create(
    usuario=docente.usuario,
    titulo="Título",
    mensaje="Cuerpo",
    institucion=institucion,
)
```

---

## Panel de Control del Propietario (`platform_control`)

### Acceso
El panel de control vive en una app Django independiente, completamente separada de `finanzas` y del flujo de los colegios.

| Concepto | Valor |
|---|---|
| URL base | `/halu-control/` |
| App Django | `platform_control/` |
| Namespace de URLs | `platform_control` |
| Autenticación | `is_superuser` de Django **+** clave maestra (`SUPERADMIN_MASTER_PASSWORD` en `.env`) |

### Acceso oculto — triple clic en el logo
Desde la pantalla de login principal (`/login/`) se puede acceder al panel sin revelar la URL ni dejar ningún indicio visual:

**Triple clic rápido sobre el logo** (panel izquierdo o encabezado del formulario) → redirige automáticamente a `/halu-control/login/`

- Los 3 clics deben hacerse en menos de 700 ms.
- Funciona sobre cualquiera de los dos logos visibles en el login.
- No puede ser interceptado por el navegador (a diferencia de combos de teclado como Ctrl+Shift+H que Edge y Firefox reservan para sus propios atajos).

El código está en:
`gestion_academica/templates/registration/login.html` (bloque `<script>` al final del archivo)

```js
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

> **Importante:** No agregar ningún botón, enlace ni indicador visible en el login que apunte a este panel. El acceso debe permanecer invisible para los usuarios de los colegios.

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

### Variable de entorno requerida
```env
SUPERADMIN_MASTER_PASSWORD=tu_clave_secreta_aqui
```

---

## Migraciones Existentes

- `0027_malla_curricular_plan_semanal` — crea `MallaCurricular`, `ItemMalla`, `PlanSemanal`, `ItemPlanSemanal`
- `0028_itemmalla_estructura_colombiana` — reemplaza campos simples con estructura colombiana completa (EBC, DBA, indicadores por nivel)
