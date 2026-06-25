# Conexiones y Seguridad (panel superadmin)

Módulo del panel `/halu-control/` para ver quién está conectado, consultar el
historial de conexiones y responder a incidentes (credenciales robadas, equipos
perdidos). Acceso: **solo superadmin** (`is_superuser` + clave maestra).

URL: `https://app.haluplataform.com/halu-control/` → botón **«Conexiones»**
(`/halu-control/conexiones/`).

## Qué registra

Cada inicio y cierre de sesión queda en el modelo `auditoria.RegistroSesion` con:

- **usuario**, **institución**, **tipo de evento** (LOGIN / LOGOUT / CIERRE_REMOTO / RESET_EMERGENCIA)
- **IP** (resistente a spoofing: toma la IP que añade el proxy de Railway, no la que envía el cliente)
- **dispositivo / navegador** (user-agent), **clave de sesión**, **fecha/hora**
- **ejecutado por** (qué superadmin disparó una acción de seguridad)

Se alimenta automáticamente con las señales `user_logged_in` / `user_logged_out`
(`auditoria/signals.py`). La tabla nace vacía: los registros empiezan desde que
se desplegó el módulo (las conexiones anteriores no existen).

## Las dos secciones

- **Conectados ahora**: sesiones activas reales (de la tabla de sesiones de la
  base de datos) cruzadas con su IP, dispositivo y hora de inicio.
- **Historial**: todos los eventos, con filtros por nombre/correo, institución,
  tipo de evento, IP y rango de fechas. Paginado.

## Acciones de seguridad

| Acción | Qué hace | Cuándo usarla |
|---|---|---|
| **Cerrar una sesión** | Elimina esa sesión concreta (expulsa ese dispositivo). | Una conexión sospechosa puntual. |
| **Cerrar todas las sesiones** | Elimina todas las sesiones activas del usuario. No cambia la contraseña. | Equipo perdido, o forzar un nuevo login. |
| **Bloqueo de emergencia** | Pone una **contraseña temporal aleatoria** (deja fuera a quien tuviera la actual) **y** cierra todas sus sesiones. La contraseña se muestra **una sola vez**. | Credenciales comprometidas / cuenta usurpada. |

Notas:

- El **bloqueo de emergencia no permite** restablecer la contraseña de otro
  super-administrador (evita escaladas de privilegios).
- La contraseña temporal hay que entregarla por un **canal seguro distinto** al
  comprometido; el usuario debe cambiarla al ingresar.
- Todas las acciones quedan **auditadas** en el propio historial (evento +
  responsable + IP + hora).
- La UI usa modales de confirmación de Bootstrap (sin diálogos del navegador),
  conforme a la regla del proyecto.

## Multi-institución

Cada registro guarda su `institucion`. El superadmin ve todas; el filtro por
institución permite acotar el historial.

## Privacidad / legal

Registrar IPs y horarios de conexión de los usuarios (incluye **menores de edad**
y familias) es **dato personal** bajo la **Ley 1581 de 2012 (habeas data)** en
Colombia. Debe estar contemplado en la política de tratamiento de datos de la
institución, con una finalidad legítima (seguridad de la cuenta).

## Archivos relevantes

- `auditoria/models.py` → modelo `RegistroSesion`
- `auditoria/signals.py` → señales de login/logout
- `auditoria/migrations/0002_registrosesion.py`
- `platform_control/views.py` → `conexiones_view`, `cerrar_sesion_remota`,
  `cerrar_sesiones_usuario`, `restablecer_password_emergencia`
- `platform_control/templates/platform_control/conexiones.html`

## Despliegue

La migración `auditoria.0002_registrosesion` es **aditiva** (solo crea la tabla
nueva; no toca datos existentes). El `Dockerfile` ya ejecuta
`python manage.py migrate --no-input` en cada arranque, así que se aplica sola
en el deploy. No requiere ningún paso manual.
