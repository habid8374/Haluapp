# Halu Plataforma — Referencia de API

> Última actualización: 2025  
> Versión de API: v1  
> Framework: Django REST Framework + Simple JWT

---

## Autenticación

### Métodos soportados

| Método | Uso |
|--------|-----|
| **JWT Bearer** | App móvil y clientes externos |
| **Session** | Navegador web (cookie) |
| **Token DRF** | Integraciones legacy |

### Obtener tokens JWT

```http
POST /api/token/
Content-Type: application/json

{
  "username": "usuario",
  "password": "contraseña"
}
```

**Respuesta:**
```json
{
  "access": "<JWT_ACCESS_TOKEN>",
  "refresh": "<JWT_REFRESH_TOKEN>"
}
```

### Refrescar token

```http
POST /api/token/refresh/
Content-Type: application/json

{
  "refresh": "<JWT_REFRESH_TOKEN>"
}
```

### Usar el token en requests

```http
GET /academico/api/v1/mi-perfil/
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

---

## Códigos de error comunes

| Código | Significado |
|--------|-------------|
| `401` | No autenticado o token expirado |
| `403` | Sin permiso para esta acción |
| `404` | Recurso no encontrado (o de otra institución) |
| `400` | Datos de entrada inválidos |
| `500` | Error interno del servidor |

> **Multi-tenant:** Los endpoints siempre filtran por `institucion_asociada` del usuario. Un 404 puede significar "no existe" o "es de otra institución".

---

## API Académica — `/academico/api/v1/`

### Estudiante

#### `GET /academico/api/v1/mi-perfil/`
Perfil completo del estudiante autenticado.

**Auth:** JWT/Session · **Rol:** `estudiante`

**Respuesta:**
```json
{
  "id": 1,
  "nombre": "Juan Pérez",
  "grado": "Grado 11",
  "foto_url": "https://...",
  "institucion": "Colegio XYZ"
}
```

---

#### `GET /academico/api/v1/estudiante/mis-deberes/`
Lista de deberes asignados al estudiante.

**Auth:** JWT/Session · **Rol:** `estudiante`  
**Permisos requeridos:** `ver_mis_deberes`

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `page` | int | Número de página |
| `limit` | int | Resultados por página |

**Respuesta:**
```json
[
  {
    "id": 12,
    "titulo": "Taller de ecuaciones",
    "materia": "Matemáticas",
    "fecha_limite": "2025-06-20T23:59:00",
    "estado": "PENDIENTE",
    "entregado": false
  }
]
```

---

#### `GET /academico/api/v1/estudiante/mi-boletin/`
Boletín de calificaciones del período.

**Auth:** JWT/Session · **Rol:** `estudiante`

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `periodo_pk` | int | ID del período académico |

---

#### `GET /academico/api/v1/estudiante/mi-horario/`
Horario de clases del estudiante.

**Auth:** JWT/Session · **Rol:** `estudiante`

---

#### `GET /academico/api/v1/estudiante/mi-asistencia/`
Historial de asistencia.

**Auth:** JWT/Session · **Rol:** `estudiante`

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `start_date` | date `YYYY-MM-DD` | Fecha inicio del rango |
| `end_date` | date `YYYY-MM-DD` | Fecha fin del rango |

---

#### `GET /academico/api/v1/estudiante/mi-estado-cartera/`
Estado financiero (deudas, pagos) del estudiante.

**Auth:** JWT/Session · **Rol:** `estudiante` o `familiar`

---

#### `GET /academico/api/v1/estudiante/mis-menciones/`
Reconocimientos y menciones de honor recibidos.

**Auth:** JWT/Session · **Rol:** `estudiante`

---

### Docente

#### `GET /academico/api/v1/dashboard-docente/`
Datos del panel principal del docente.

**Auth:** JWT/Session · **Rol:** `docente`

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `periodo_pk` | int | Período académico |
| `curso_pk` | int | Curso específico (opcional) |

---

#### `GET /academico/api/v1/libro-notas/curso/<curso_pk>/`
Libro de notas de un curso con todos los estudiantes y calificaciones.

**Auth:** JWT/Session · **Rol:** `docente`  
**Permisos:** `acceso_libro_notas_docente`

**Path params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `curso_pk` | int | ID del curso |

---

#### `POST /academico/api/v1/libro-notas/curso/<curso_pk>/guardar/`
Guarda calificaciones en el libro de notas.

**Auth:** JWT/Session · **Rol:** `docente`

**Body:**
```json
{
  "calificaciones": {
    "1": 4.5,
    "2": 3.8,
    "3": 2.1
  }
}
```
> Las claves son `estudiante_id` y los valores son las notas numéricas.

---

#### `POST /academico/api/v1/docente/disponibilidad/`
Registra horarios de disponibilidad para citas con familias.

**Auth:** JWT/Session · **Rol:** `docente`

**Body:**
```json
{
  "fecha": "2025-06-20",
  "hora_inicio": "14:00",
  "hora_fin": "17:00"
}
```

---

### Coordinador

#### `GET /academico/api/v1/dashboard-coordinador/`
KPIs y datos del panel del coordinador.

**Auth:** JWT/Session · **Rol:** `coordinador`

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `periodo_pk` | int | Período académico activo |

---

#### `GET /academico/api/v1/coordinacion/asistencia-diaria/`
Resumen de asistencia del día actual.

**Auth:** JWT/Session · **Rol:** `coordinador`

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `fecha` | date `YYYY-MM-DD` | Fecha (default: hoy) |

---

#### `GET /academico/api/v1/coordinacion/alertas-bienestar/`
Lista de alertas de bienestar estudiantil.

**Auth:** JWT/Session · **Rol:** `coordinador`

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `categoria` | string | Filtrar por categoría de alerta |

---

### Familiar

#### `GET /academico/api/v1/familiar/estudiante/<estudiante_pk>/calificaciones/`
Calificaciones de un estudiante vinculado al familiar.

**Auth:** JWT/Session · **Rol:** `familiar`  
**Permisos:** `ver_calificaciones_estudiante_familiar`

---

#### `GET /academico/api/v1/familiar/estudiante/<estudiante_pk>/deberes/`
Deberes de un estudiante vinculado.

**Auth:** JWT/Session · **Rol:** `familiar`  
**Permisos:** `ver_deberes_estudiante_familiar`

---

### Asistencia

#### `POST /academico/api/registrar-asistencia/`
Registra la asistencia de un estudiante.

**Auth:** JWT/Session · **Rol:** `docente`  
**Permisos:** `add_registroasistencia`

**Body:**
```json
{
  "estudiante_id": 5,
  "estado": "PRESENTE",
  "fecha": "2025-06-14",
  "curso_id": 3
}
```

> **Estados válidos:** `PRESENTE`, `AUSENTE`, `TARDANZA`

---

### Funciones de IA

#### `POST /academico/api/v1/ia/sugerir-nombre-idioma/`
Genera nombres en otro idioma para una actividad (bilingüismo).

**Auth:** JWT/Session · **Rol:** `docente`, `coordinador`

**Body:**
```json
{
  "actividad_id": 12,
  "idioma": "INGLES"
}
```

---

#### `POST /academico/api/generar-resumen-estudiante/<estudiante_pk>/<periodo_pk>/`
Genera con IA un resumen académico del estudiante para el período.

**Auth:** JWT/Session · **Rol:** `coordinador`

---

#### `POST /academico/api/generar-correo-acudiente/<estudiante_pk>/<periodo_pk>/`
Genera con IA un correo personalizado para el acudiente con el resumen del período.

**Auth:** JWT/Session · **Rol:** `coordinador`

---

### Currículum y Planeación

#### `GET /academico/api/dba/`
Devuelve los DBA (Derechos Básicos de Aprendizaje) predefinidos.

**Auth:** JWT/Session

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `grado` | string | Ej: `GRADO_11` |
| `area` | string | Ej: `MATEMATICAS` |
| `periodo` | int | 1, 2, 3 o 4 |

---

#### `POST /academico/api/generar-indicadores/`
Genera indicadores de desempeño con IA a partir de un DBA.

**Auth:** JWT/Session · **Rol:** `coordinador`

**Body:**
```json
{
  "dba_id": 3,
  "competencias": "Razonamiento y argumentación"
}
```

---

#### `GET /academico/api/cursos-por-grado/<grado_id>/`
Lista los cursos/materias de un grado.

**Auth:** JWT/Session

---

## API de Calendario

#### `GET /academico/api/calendario/eventos/`
Eventos del calendario académico.

**Auth:** JWT/Session

**Query params:**

| Param | Tipo | Descripción |
|-------|------|-------------|
| `start_date` | date | Inicio del rango |
| `end_date` | date | Fin del rango |
| `tipo` | string | Tipo de evento (opcional) |

---

## Notificaciones

#### `POST /academico/notificaciones/marcar-leida/`
Marca una notificación como leída.

**Auth:** JWT/Session

**Body:**
```json
{
  "notificacion_id": 42
}
```

---

## Cuestionarios — `/cuestionarios/`

#### `GET /cuestionarios/api/<actividad_pk>/`
Obtiene el cuestionario de una actividad calificable.

**Auth:** JWT/Session · **Rol:** `estudiante`

---

#### `POST /cuestionarios/resolver/api/<intento_pk>/`
Envía las respuestas de un intento de cuestionario.

**Auth:** JWT/Session · **Rol:** `estudiante`  
**Permisos:** `puede_realizar_entrega_deber`

**Body:**
```json
{
  "respuestas": {
    "1": "A",
    "2": "C",
    "3": "B"
  }
}
```

---

#### `POST /cuestionarios/api/generar-preguntas/<cuestionario_pk>/`
Genera preguntas del cuestionario con IA (Gemini).

**Auth:** JWT/Session · **Rol:** `docente`

**Body:**
```json
{
  "tema": "Fracciones y decimales",
  "cantidad": 5,
  "dificultad": "MEDIO"
}
```

---

#### `POST /cuestionarios/api/sugerir-calificacion/<respuesta_pk>/`
Propone una calificación para una respuesta abierta usando IA.

**Auth:** JWT/Session · **Rol:** `docente`

---

## Simulacros — `/simulacros/`

#### `POST /simulacros/generar-ia/`
Genera preguntas tipo ICFES con IA para el banco.

**Auth:** JWT/Session · **Rol:** `docente`, `coordinador`

**Body (multipart/form-data):**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `grado` | string | Ej: `GRADO_11` |
| `area` | string | Ej: `MATEMATICAS` |
| `cantidad` | int | 3, 5 o 10 |
| `dificultad` | string | `BASICO`, `MEDIO`, `ALTO` |
| `csrfmiddlewaretoken` | string | Token CSRF |

**Respuesta:**
```json
{
  "ok": true,
  "grado": "GRADO_11",
  "area": "MATEMATICAS",
  "dificultad": "MEDIO",
  "preguntas": [
    {
      "enunciado": "¿Cuánto es...?",
      "opciones": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correcta": "B",
      "competencia": "Razonamiento",
      "componente": "Numérico"
    }
  ]
}
```

---

#### `POST /simulacros/guardar-ia/`
Guarda en el banco las preguntas generadas por IA.

**Auth:** JWT/Session · **Rol:** `docente`, `coordinador`  
**Content-Type:** `application/json`

**Body:**
```json
{
  "grado": "GRADO_11",
  "area": "MATEMATICAS",
  "dificultad": "MEDIO",
  "preguntas": [ ... ]
}
```

> Máximo 10 preguntas por llamada. El sistema valida el esquema antes de guardar.

---

## Admisiones — `/admisiones/`

#### `POST /admisiones/pago/webhook_mp/`
Webhook de Mercado Pago para pagos de inscripción.

**Auth:** Ninguna (verificación por firma HMAC-SHA256)  
**Header:** `X-Signature: <firma>`

> No llamar directamente. Es exclusivo para Mercado Pago.

---

#### `GET /admisiones/pago/verificar/<cuenta_id>/`
Verifica el estado de un pago de inscripción.

**Auth:** Session

---

## Finanzas — `/finanzas/`

#### `POST /finanzas/webhook/mercadopago/`
Webhook de Mercado Pago para pagos de pensión/matrícula.

**Auth:** Ninguna (verificación por firma HMAC-SHA256)  
**Header:** `X-Signature: <firma>`

> No llamar directamente. Es exclusivo para Mercado Pago.

---

## Mensajería — `/mensajeria/`

#### `GET /mensajeria/api/conversaciones/`
Lista todas las conversaciones del usuario.

**Auth:** JWT/Session

---

#### `GET /mensajeria/api/mensajes/<conversacion_id>/`
Mensajes de una conversación.

**Auth:** JWT/Session

---

#### `POST /mensajeria/api/enviar/`
Envía un mensaje.

**Auth:** JWT/Session

**Body:**
```json
{
  "destinatario_id": 7,
  "texto": "Hola, necesito hablar sobre la tarea."
}
```

---

#### `GET /mensajeria/api/no-leidos/`
Número de mensajes sin leer.

**Auth:** JWT/Session

**Respuesta:**
```json
{ "count": 3 }
```

---

## WebSockets (Tiempo real)

Protocolo: `wss://` en producción, `ws://` en desarrollo.

### Notificaciones

```
wss://app.haluplataform.com/ws/notifications/
```

**Auth:** Cookie de sesión o token en query param  
**Eventos recibidos:**

```json
{
  "type": "send_notification",
  "kind": "cita_reunion_academica",
  "title": "Nueva cita con familia",
  "message": "...",
  "url": "/academico/...",
  "severity": "info"
}
```

**Valores de `severity`:** `info`, `warning`, `danger`, `success`

---

### Mensajería en tiempo real

```
wss://app.haluplataform.com/ws/mensajeria/<conversacion_id>/
```

**Auth:** Cookie de sesión  
**Eventos:**

```json
{ "type": "mensaje_nuevo", "id": 5, "texto": "...", "fecha": "..." }
{ "type": "mensajes_leidos", "conversacion_id": 3 }
```

---

### Health Check (solo superadmin)

```
wss://app.haluplataform.com/ws/healthcheck/<ejecucion_id>/
```

---

## Panel de Control — `/halu-control/`

#### `GET /halu-control/mantenimiento/<pk>/estado/`
Estado de una ejecución de diagnóstico (JSON).

**Auth:** Superusuario + clave maestra  
**Nota:** Solo accesible desde el panel de control interno.

---

## Variables de entorno requeridas

| Variable | Descripción | Obligatoria |
|----------|-------------|-------------|
| `SECRET_KEY` | Clave secreta de Django | ✅ |
| `FERNET_KEY` | Clave de cifrado para credenciales SMTP de instituciones | ✅ |
| `DATABASE_URL` | URL de conexión PostgreSQL | ✅ |
| `REDIS_URL` | URL de Redis (caché + Celery) | ✅ |
| `SUPERADMIN_MASTER_PASSWORD` | Clave maestra del panel Halu Control | ✅ |
| `MP_ACCESS_TOKEN` | Token de Mercado Pago (global fallback) | Recomendada |
| `USE_SQLITE` | `1` para usar SQLite en tests locales | Solo dev |
| `DEBUG` | `True` en desarrollo | Solo dev |

> Cada institución almacena su propia `GOOGLE_API_KEY` para Gemini en la base de datos (campo cifrado con Fernet), no en variables de entorno globales.

---

## Estadísticas de la API

| Métrica | Valor |
|---------|-------|
| Total de endpoints | 80+ |
| Endpoints API v1 móvil | 57 |
| Consumidores WebSocket | 3 |
| Webhooks externos | 2 (Mercado Pago) |
| Métodos de autenticación | 3 (JWT, Session, Token) |
| Módulos con API | 9 |
