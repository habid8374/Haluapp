# Plan: Selector de Idiomas (Plataforma Multi-idioma)

> **Estado: PENDIENTE — no implementar hasta que un colegio bilingüe lo necesite
> o el propietario lo pida explícitamente.** Este documento es solo la hoja de
> ruta acordada; ningún código de este plan ha sido escrito todavía.

## Objetivo

Permitir que colegios verdaderamente bilingües (ej. inglés/español) puedan
cambiar el idioma de toda la plataforma, sin afectar a los colegios que solo
operan en español (la mayoría).

## Enfoque técnico

Usar el framework de internacionalización (i18n) nativo de Django —
`gettext` — en vez de una solución externa.

### 1. Motor de traducción
- Envolver cada texto visible:
  - Templates: `{% trans "..." %}` / `{% blocktrans %}`.
  - Python (verbose_name, help_text, choices, `messages.success/error`,
    mensajes de `Notificacion`, etc.): `gettext_lazy` como `_("...")`.
- Extraer con `python manage.py makemessages -l en`.
- Traducir los `.po` generados (primera pasada asistida por IA, luego
  revisión humana si el colegio lo requiere).
- Compilar con `python manage.py compilemessages`.

### 2. Selector de idioma (UI)
- Dropdown simple en el nav (`base_academico.html`), visible SOLO si la
  institución tiene el multi-idioma habilitado (ver punto 4).
- Reutiliza la vista estándar de Django `django.views.i18n.set_language`
  (ya viene incluida, solo hay que registrar la URL) — sin diálogos nativos,
  un simple `<form method="post">` con el patrón de UI ya establecido en el
  proyecto.

### 3. Preferencia por usuario (no solo por sesión)
- Nuevo campo en `Usuario`: `idioma_preferido` (choices: `es`, `en`, ...),
  para que un docente o familiar no tenga que volver a elegir el idioma
  cada vez que entra.
- Un middleware (o señal en el login) activa `translation.activate(...)`
  al inicio de cada request según:
  1. `idioma_preferido` del usuario (si está logueado y lo tiene definido),
  2. si no, idioma de la sesión/cookie (`django.utils.translation` estándar),
  3. si no, idioma del navegador (`Accept-Language`).

### 4. Control por institución (multi-tenant)
- Campo nuevo en `InstitucionEducativa`, ej. `idiomas_habilitados`
  (lista/M2M de idiomas activos para esa institución).
- El selector de idioma en el nav solo se muestra si la institución tiene
  más de un idioma habilitado — los colegios monolingües no ven ningún
  cambio en su interfaz.

### 5. Casos que NO son solo "texto plano" (fáciles de olvidar)
- **PDFs** (constancias, boletines, certificados): se generan renderizando
  un template `xhtml2pdf` fuera del ciclo normal de request/response, así
  que hay que activar el idioma manualmente (`translation.activate(idioma)`)
  antes de llamar a `pisa.CreatePDF`.
- **Contenido generado por IA (Gemini)**: los prompts hoy piden
  explícitamente la respuesta en español (sugerencias de refuerzo, análisis
  de convivencia, planeador IA, etc.). Habría que parametrizar el idioma de
  salida en cada prompt según el idioma activo del usuario/institución.
- **Correos transaccionales**: igual que los PDFs, deben activar el idioma
  correcto antes de renderizar el asunto/cuerpo del correo.
- **JavaScript inline** con texto quemado (alertas, validaciones en el
  cliente) necesita su propio mecanismo (`JavaScriptCatalog` de Django o
  data-attributes con el texto ya traducido desde el template).

## Estrategia de rollout (evitar "todo o nada")

Dado el tamaño del código (decenas de miles de líneas, casi todo en español
sin envolver en tags de traducción), **no conviene traducir toda la
plataforma de una sola vez**. Plan sugerido:

1. Construir primero la base técnica (selector, campo de idioma por
   usuario, campo de habilitación por institución, middleware) — sin
   traducir nada todavía. Esto no rompe nada para los colegios actuales.
2. Elegir un módulo de alto impacto para la primera traducción real — por
   ejemplo, el portal de familiares o el dashboard del estudiante — y
   envolver/traducir solo ese módulo.
3. Ir agregando módulos según la necesidad real del colegio bilingüe
   (priorizando lo que sus usuarios ven más), en vez de bloquear el
   lanzamiento hasta tener el 100% traducido.

## Disparador para activar este plan

Retomar este trabajo cuando:
- Un colegio bilingüe confirme que lo necesita, **o**
- El propietario (habid8374) lo pida explícitamente.

En ese momento, empezar por el paso 1 (base técnica) de la sección
"Estrategia de rollout".
