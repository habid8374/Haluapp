# Acceso a actividades evaluativas y cuestionarios

Este documento describe la **política de autorización** compartida entre `gestion_academica` y `cuestionarios` tras la fase de endurecimiento (2026).

## Modelo de datos

- **`ActividadCalificable`** (`gestion_academica`): actividad por curso, con `institucion` y enlace al curso (grado + periodo).
- **`Cuestionario`** (`cuestionarios`): relación **OneToOne** con `ActividadCalificable` (`related_name='cuestionario'`).
- Pueden coexistir preguntas “interactivas” en GA (`Pregunta`) y cuestionario en la app `cuestionarios`; la UI prioriza el cuestionario cuando existe.

## Helpers centralizados (`gestion_academica.utils`)

| Función | Uso |
|--------|-----|
| `estudiante_en_curso_actividad(estudiante, actividad)` | Comprueba misma institución, mismo grado que el curso de la actividad y que el curso pertenezca al **periodo académico activo** del estudiante. Requiere `actividad.curso` cargado (p. ej. `select_related('curso', 'institucion')`). |
| `actividades_calificables_accesibles_para_usuario(user)` | QuerySet acotado para la API de detalle de actividad interactiva (estudiante / docente / staff con institución / superusuario). |
| `docente_asignado_a_actividad(user, actividad)` | El docente está en `curso.docentes_asignados`. |

## `gestion_academica` (resumen)

- **`resolver_actividad_page`**: unificada; valida estudiante + `estudiante_en_curso_actividad`; si hay `Cuestionario` redirige a `cuestionarios:iniciar_cuestionario`; si no hay preguntas inline, redirige al dashboard.
- **`DetalleActividadAPIView` / `EnviarRespuestasAPIView` / `CalendarioEventosAPIView`**: usan el queryset helper o la misma regla de curso; permiso de mora `EstaAlDiaPermission` donde aplica.
- **Agenda / calendario**: enlaces coherentes (cuestionario → iniciar; preguntas inline → resolver; adjunto → URL).
- **Multi-tenant UI**: uso de `institucion_asociada` en staff (no `institucioneducativa`).

## `cuestionarios` (resumen)

- **`IniciarCuestionarioView`**: mora (`redirect_si_moroso_estudiante`), solo estudiante, `estudiante_en_curso_actividad` en GET y POST; cuestionario acotado por `institucion_id` de la actividad.
- **`ResolverCuestionarioView` / `ResolverCuestionarioAPIView`**: misma validación de curso vía actividad del intento; API bloquea mora y exige perfil estudiante.
- **`CuestionarioAPIView` GET**: superusuario, docente asignado, estudiante en curso, o **staff** con `institucion_asociada` igual a la de la actividad (solo lectura JSON).
- **`EditorCuestionarioView` / POST cuestionario`**: superusuario o docente del curso; `institucion` por defecto usa `institucion_asociada` o la de la actividad.
- **`ToggleCuestionarioActivoView`**: superusuario sin filtro extra; resto `creado_por` + institución.
- **`GenerarPreguntasIAView`**: superusuario o creador que sigue siendo docente del curso de la actividad.
- **`CuestionarioListView`**: superusuario ve todo; resto filtra por `institucion_asociada` (sin institución → vacío).

## Intentos en actividades interactivas (`IntentoActividad`)

- **Varios intentos terminados**: se eliminó `unique_together` `(estudiante, actividad, estado)` y se añadió un **índice único parcial**: solo puede haber **un** registro `en_progreso` por par estudiante–actividad; sí puede haber varios `completado` o `tiempo_agotado` hasta el máximo configurado.
- **Default recomendado**: `ActividadCalificable.numero_intentos_permitidos` por defecto **5** (adecuado para etapa escolar); **máximo 20** a nivel modelo (evaluaciones especiales).
- **Lógica en vista**: solo se cuenta un intento nuevo si **no** hay sesión `en_progreso` activa; al reanudar la misma sesión no se consume un cupo extra.

## Misma política de mora (funciones vs decorador)

- `requiere_pagos_al_dia` delega en `redirect_si_moroso_estudiante` para no duplicar mensajes.
- Las vistas en `cuestionarios` llaman a `redirect_si_moroso_estudiante(request)` al inicio de GET/POST de estudiante.

## Coordinación sin perfil `Docente`

- Vistas pensadas solo para **docente** (p. ej. editor de cuestionario por `curso__docentes_asignados`) pueden fallar si un **coordinador** no tiene `user.docente`. Donde haga falta, usar `hasattr(request.user, "docente")`, ramas para `is_staff` + `institucion_asociada`, o rutas dedicadas de coordinación.

## Referencias cruzadas

- Bloqueo financiero del estudiante: [`BLOQUEO_POR_MORA.md`](BLOQUEO_POR_MORA.md).
- Deprecación Gemini: [`GEMINI_SDK.md`](GEMINI_SDK.md).
