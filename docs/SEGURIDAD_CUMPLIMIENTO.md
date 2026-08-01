# Seguridad y Cumplimiento — HALU Plataforma Escolar

Mapeo de los controles técnicos implementados en el software contra
**OWASP Top 10 (2021)**, **ISO/IEC 27001:2022 (Anexo A)** y **NIST SP 800-53 /
NIST CSF**.

> **Alcance.** Este documento cubre los controles **a nivel de código y
> configuración** de la aplicación. ISO/IEC 27001 y NIST incluyen además
> controles **organizativos** (política de seguridad, gestión de riesgos,
> continuidad, formación, gestión de proveedores, respuesta a incidentes) que
> son responsabilidad de la organización y **no** viven en el código; aquí solo
> se documenta la parte técnica que la plataforma implementa.

Multi-institución (SaaS): el aislamiento por institución es la regla
innegociable del sistema (ver `CLAUDE.md`) y es el pilar del control de acceso.

---

## OWASP Top 10 (2021)

### A01:2021 — Pérdida de control de acceso (Broken Access Control)
- **Aislamiento multi-institución** en toda vista/queryset por
  `request.user.institucion_asociada`; superusuario exento. Helper
  `get_filtered_queryset` y `_get_institucion`.
- **Django admin** blindado con `InstitucionScopedAdminMixin`
  (`proyecto_colegio/admin_mixins.py`): `get_queryset`, FKs/M2M y campo de
  institución acotados; `save_model` fuerza la institución; filtros por
  institución ocultos. `SuperuserOnlyAdminMixin` para modelos globales.
- **Permisos por rol** (grupos Django, migración 0039) + `permission_required`
  en vistas sensibles.
- **`get_object_or_404` con filtro de institución** en los accesos por pk
  (bloquea IDOR entre colegios). Auditoría realizada sobre vistas, API móvil,
  simulacros, PIAR, admisiones, finanzas, mensajería y módulos de juegos.
- **Bloqueo de estudiante** y **módulo financiero** aplicados por middleware,
  no solo por UI (`BloqueoEstudianteMiddleware`, `ModuloFinancieroMiddleware`).
- Estado: **cubierto**. Recomendación continua: mantener `institucion` en todo
  modelo/vista nuevos (regla del proyecto).

### A02:2021 — Fallos criptográficos (Cryptographic Failures)
- **Contraseñas con Argon2** (`PASSWORD_HASHERS`, `settings.py`).
- **Cifrado de campos sensibles** con Fernet (`FERNET_KEY`): credenciales SMTP,
  API keys de institución (Gemini/Claude), etc.
- **HTTPS forzado** en producción: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`
  (1 año), `HSTS_INCLUDE_SUBDOMAINS`, `HSTS_PRELOAD`.
- **Cookies seguras**: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `SESSION_COOKIE_HTTPONLY`, `SameSite=Lax`.
- Credenciales y llaves **solo por variables de entorno** (no en el código);
  `SECRET_KEY`/`FERNET_KEY` con *fail-fast* en producción.
- Estado: **cubierto**.

### A03:2021 — Inyección (Injection)
- **ORM de Django** parametrizado en todo el acceso a datos (sin SQL crudo con
  interpolación de entrada del usuario).
- **Autoescape de plantillas** Django (protección XSS por defecto).
- **Validación de entradas** en formularios (`ModelForm`/`clean`), incluida la
  validación multi-institución de FKs (materia↔nivel, etc.).
- **Respuestas de IA (Gemini)** validadas por esquema antes de enviarse al
  cliente (simulacros, planeador).
- Estado: **cubierto**. Brecha residual: **CSP** (ver recomendaciones).

### A04:2021 — Diseño inseguro (Insecure Design)
- **Defensa en profundidad**: reglas de acceso replicadas en middleware, vistas
  y admin; validaciones `clean()` además del filtrado de querysets.
- **Principio de menor privilegio** por rol y por grupo.
- **Fail-closed** en rate-limiting (`RATELIMIT_FAIL_OPEN = False`).
- Estado: **cubierto en lo aplicable**.

### A05:2021 — Configuración de seguridad incorrecta (Security Misconfiguration)
- `DEBUG` controlado por entorno; `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`
  restringidos (túneles solo en desarrollo).
- Cabeceras: `X_FRAME_OPTIONS='DENY'`, `SECURE_CONTENT_TYPE_NOSNIFF`,
  `SECURE_REFERRER_POLICY='same-origin'`, `Cross-Origin-Opener-Policy`
  (default `same-origin` en Django 5.2).
- `SECURE_PROXY_SSL_HEADER` configurado para el proxy TLS.
- Estado: **cubierto**. Brechas residuales: **CSP** y **Permissions-Policy**
  (ver recomendaciones — requieren despliegue cuidadoso).

### A06:2021 — Componentes vulnerables y desactualizados
- Django 5.2 (rama con soporte) y dependencias fijadas en `requirements.txt`.
- Recomendación: revisión periódica de dependencias (p. ej. `pip-audit` /
  Dependabot) — control **organizativo/CI**, fuera del código.
- Estado: **parcial** (depende de proceso de actualización).

### A07:2021 — Fallos de identificación y autenticación
- **MFA**: app `autenticacion_2fa` (TOTP) + `passkeys` (WebAuthn) con
  `Verificacion2FAMiddleware`.
- **Anti-bots / anti-fuerza bruta**: Cloudflare **Turnstile** en logins
  (`TurnstileMiddleware`) + **rate-limiting** (django-ratelimit, fail-closed).
- **Contraseñas**: mínimo 10, validadores de similitud, comunes y numéricas.
- **Sesiones**: expiración a 7 días, backend `cached_db`, cookies HttpOnly/Secure.
- **Recuperación de contraseña** por institución (sin cuentas compartidas).
- Estado: **cubierto**.

### A08:2021 — Fallos de integridad de software y datos
- **CSRF** activo (`CsrfViewMiddleware`) en todos los formularios.
- **JWT** (API móvil) firmados con `SECRET_KEY`.
- **Webhooks Mercado Pago** verificados con firma **HMAC-SHA256**.
- Estado: **cubierto**.

### A09:2021 — Fallos de registro y monitoreo (Logging & Monitoring)
- **Auditoría** de acciones (`auditoria.AuditoriaMiddleware`, `RegistroAuditoria`).
- **Auditoría específica** de acciones sobre pagos (`AuditoriaAccionPago`).
- **Sentry** para captura de errores en producción (`SENTRY_DSN`).
- Estado: **cubierto**. Recomendación: alertas sobre eventos de seguridad
  (múltiples fallos de login, cambios de permisos) — mejora futura.

### A10:2021 — Falsificación de solicitudes del lado del servidor (SSRF)
- Salida a internet acotada a integraciones conocidas (Brevo/SMTP por
  institución, Mercado Pago, Gemini/Claude, R2/S3). `imagen_url` en simulacros
  restringida a `http/https`.
- Estado: **bajo riesgo**. Recomendación: validar/limitar cualquier futura
  funcionalidad que reciba URLs del usuario para peticiones del servidor.

---

## ISO/IEC 27001:2022 — Anexo A (controles técnicos aplicables)

| Control (Anexo A) | Cómo lo cubre el software |
|---|---|
| A.5.15 Control de acceso | Roles + grupos + aislamiento multi-institución |
| A.5.16 Gestión de identidades | Cuentas por usuario/rol; superusuario separado |
| A.5.17 Información de autenticación | Argon2; validadores; recuperación por institución |
| A.5.18 Derechos de acceso | `permission_required`, mixins de admin, menor privilegio |
| A.8.2 Acceso privilegiado | Panel superadmin con clave maestra aparte |
| A.8.3 Restricción de acceso a la información | `get_object_or_404` + filtro por institución |
| A.8.5 Autenticación segura | MFA (TOTP/WebAuthn) + Turnstile + rate-limit |
| A.8.9 Gestión de la configuración | Config por entorno; cabeceras de seguridad |
| A.8.12 Prevención de fuga de datos | Aislamiento por institución; credenciales no compartidas |
| A.8.15 Registro (logging) | Auditoría + Sentry |
| A.8.24 Uso de criptografía | HTTPS/HSTS; Fernet en campos sensibles |
| A.8.28 Codificación segura | ORM parametrizado; autoescape; validación; CSRF |

> Controles organizativos de ISO 27001 (A.5 políticas, A.6 personas, A.7 físicos,
> gestión de riesgos e ISMS) **no aplican al código** y deben gestionarse a
> nivel institucional.

---

## NIST — SP 800-53 (familias) y CSF (funciones)

| NIST 800-53 (familia) | Implementación |
|---|---|
| AC (Access Control) | Roles, grupos, aislamiento multi-institución, IDOR-safe |
| IA (Identification & Authentication) | MFA TOTP/WebAuthn, contraseñas robustas |
| SC (System & Communications Protection) | TLS/HSTS, cookies seguras, HMAC webhooks, cifrado Fernet |
| SI (System & Information Integrity) | CSRF, validación de entrada/IA, Sentry |
| AU (Audit & Accountability) | Middleware de auditoría + auditoría de pagos |
| CM (Configuration Management) | Config por entorno, cabeceras, fail-fast de claves |

**NIST CSF:** *Identify* (inventario de datos por institución), *Protect*
(acceso, cifrado, MFA), *Detect* (auditoría, Sentry), *Respond/Recover*
(procesos organizativos, respaldos — fuera del código).

---

## Brechas residuales y recomendaciones (priorizadas)

1. **Content-Security-Policy (CSP)** — *OWASP A03/A05.* Hoy no hay CSP. Mitiga
   XSS de forma fuerte, pero la plataforma usa **estilos y scripts inline** y
   algún CDN (Bootstrap/FullCalendar), por lo que una CSP estricta **rompería la
   UI**. Plan seguro: introducir CSP en modo **Report-Only** con endpoint de
   reporte, migrar inline a archivos/nonces gradualmente y luego hacerla
   *enforcing*. Requiere trabajo dedicado y pruebas; **no** se activa de golpe.
2. **Permissions-Policy** — *OWASP A05.* No se añade una política restrictiva
   porque el login **biométrico/passkeys** usa `camera`/`publickey-credentials`;
   una política mal ajustada los rompería. Definir una lista blanca por feature
   antes de activarla.
3. **Gestión de dependencias** — *OWASP A06.* Añadir `pip-audit`/Dependabot en
   CI para alertar de CVEs.
4. **Alertas de seguridad** — *OWASP A09.* Alertar sobre múltiples fallos de
   login y cambios de permisos, además del registro actual.
5. **`security.txt`** (RFC 9116) — canal de divulgación responsable
   (ISO A.5.5 / NIST). Bajo esfuerzo.

> Estas recomendaciones son mejoras incrementales; las **1 y 2 exigen despliegue
> cuidadoso** para no degradar funcionalidades existentes (biometría, UI).
