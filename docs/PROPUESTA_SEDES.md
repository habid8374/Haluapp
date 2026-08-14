# Propuesta de arquitectura — Sedes en HALU

> **Estado:** DISEÑO APROBADO · implementación **aplazada** (a la espera de un caso real multi-sede).
> Documento de referencia; no hay cambios de código todavía.
> Alineado al **DUE–SIMAT** y al **Formulario Único Censal C-600 (2024)** del DANE.
> Versión visual: artefacto «Sedes en HALU» — https://claude.ai/code/artifact/0fca06a0-7265-47b2-a75b-83611f48a984

---

## 1. El problema de hoy

Hoy la sede es un **atributo suelto**, no una estructura. Eso genera cuatro tensiones que se agravan con instituciones oficiales grandes (varias sedes):

1. **La sede está duplicada** en cuatro modelos — `Estudiante.sede`, `Grupo.sede`, `CaracterizacionEstudiante.sede`, `Aspirante.sede` — y solo se reconcilian **al exportar** el SIMAT (gana el grupo). No hay una única fuente de verdad.
2. **La jornada vive en 4 lugares** (`Sede.jornada_principal`, `Grupo.jornada`, `CaracterizacionEstudiante.jornada`, `Aspirante.jornada`), cada uno con su propia copia de las mismas opciones; ninguna manda a nivel de base de datos.
3. **Datos que oficialmente son de la sede viven en la institución:** municipio/ETC, calendario A/B, sector oficial/no oficial, prestación del servicio, zona. Hoy todas las sedes comparten obligatoriamente los de la institución, aunque el MEN permite que difieran.
4. **Cosas que deberían poder filtrarse por sede no tienen esa dimensión:** docentes, aulas, asistencia, tableros. El rector no puede ver «la sede B» ni una sede puede ofrecer niveles/jornadas distintos de otra.

---

## 2. La verdad oficial (DUE · SIMAT · C-600)

El formulario C-600 del DANE es explícito: **«el formulario es por cada planta física»**. La estructura real es una jerarquía de cinco niveles, y casi todo lo identitario cuelga de la **sede**, no de la institución:

```
Establecimiento educativo   (código DANE 12 díg · lo jurídico)
        └── Sede             (planta física · 12 díg + consecutivo 2 díg = 14)
              └── Jornada     (mañana, tarde, nocturna, única, completa, fin de semana)
                    └── Nivel / Grado  (preescolar, básica, media, CLEI)
                          └── Grupo
                                └── Estudiante
```

El C-600 captura **por sede**: nombre y código DANE de sede, NIT, teléfono y correo propios, departamento/municipio y Secretaría de Educación, **zona urbana/rural**, dirección, **sector** oficial/no oficial y naturaleza jurídica, acto administrativo, **modalidad de prestación del servicio**, y una **matriz de jornadas × niveles × calendario (A/B)** que dice qué ofrece esa sede — además de carácter (académico/técnico…), bilingüismo, etnoeducación y población especial.

---

## 3. Principio rector

**Independiente hacia abajo, consolidado hacia arriba.**

- El **establecimiento** guarda solo lo global (NIT, razón social, rector, DANE del establecimiento, credenciales Brevo/IA, un solo SIMAT).
- Cada **sede** es dueña de su identidad SIMAT y de su **oferta** (qué jornadas y niveles ofrece).
- El **grupo** (grado + jornada) es la **única fuente** de la sede y jornada del estudiante.
- **Docentes y aulas** se asignan por sede para poder filtrar y reportar.

### El eje que ordena todo: el nivel de escolaridad

En los colegios oficiales lo típico es **repartir las sedes por nivel** (una sede de preescolar/primaria, otra de secundaria, otra de media — p. ej. el colegio de 3 sedes en Sabanalarga). Por eso la relación clave es **Sede ↔ Niveles ofrecidos**: define la oferta de la sede, guía a qué sede va cada estudiante según su grado, contra qué sede valida el SIMAT y a qué sedes se asigna un docente. El nivel de escolaridad —no la sede— es también lo que **ata las finanzas**.

---

## 4. Quién es dueño de qué

| Dato | Hoy | Propuesta | Nota |
|---|---|---|---|
| NIT, razón social, rector, credenciales Brevo/IA | Institución | **institución** | Queda igual — es lo global |
| Código DANE del establecimiento (12) | Institución | **institución** | Identidad jurídica única |
| Código DANE de sede + consecutivo | Sede | **sede** | Ya está bien modelado |
| Zona urbana/rural | Sede | **sede** | Ya está |
| Municipio/ETC, dirección, teléfono, email | Institución | **sede** (default institución) | Una sede puede estar en otro municipio |
| Sector, calendario A/B, prestación del servicio | Institución | **sede** (default institución) | El C-600 los pide por sede |
| Jornadas y niveles ofrecidos | — (no existe) | **sede** | Nueva matriz Sede × jornada × nivel |
| Jornada del estudiante | 4 modelos | **grupo** | Fuente única; los demás se derivan/deprecan |
| Sede del estudiante | 4 modelos | **grupo → derivada** | Sale del grupo: una fuente, sin contradicciones |
| Niveles ofrecidos por la sede | — (no existe) | **sede ↔ nivel** | El eje: guía estudiante, docente, SIMAT y finanzas |
| Docente | Institución | **sede (M2M)** | Puede enseñar en varias sedes (según el nivel) |
| Aula | Institución | **sede** | Un salón pertenece a una sede |
| Asistencia, tableros, reportes | Institución | filtran por **sede** | Vía grupo→sede, sin duplicar FKs |
| Materias, períodos, calificaciones, niveles de escolaridad | Institución | **institución** | La pedagogía no cambia por sede |
| Valores de matrícula/pensión | Institución | **nivel de escolaridad** | Iguales en todas las sedes (oficial: sin cobro) |

---

## 5. Qué implica de verdad «crear una sede»

Debería ser un asistente que capture lo que el DANE exige y **habilite en cascada** el resto del sistema:

1. **Identidad** — nombre, código DANE de sede (12), consecutivo automático (01/02/03…), acto administrativo o licencia, ¿principal o anexa?
2. **Ubicación** — departamento y municipio DANE, zona urbana/rural, dirección, teléfono y correo de la sede (default = institución).
3. **Naturaleza y servicio** — sector oficial/no oficial, naturaleza jurídica, modalidad de prestación del servicio, calendario A/B.
4. **Oferta educativa** — matriz del C-600: qué jornadas y qué niveles/grados ofrece la sede. Esto es lo que después permite crear grupos válidos.
5. **Consecuencias en cascada** — habilita grupos por jornada/grado, permite matricular aspirantes hacia esa sede, aparece en el selector de sede, y genera su propio bloque en el Anexo 6A con su DANE y consecutivo.

---

## 6. Implicaciones SIMAT

**Se arregla solo:**
- El Anexo 6A ya usa DANE establecimiento + DANE sede + consecutivo + jornada → queda 100 % correcto cuando cada sede tenga sus datos.
- El reporte se puede generar **por sede o consolidado**.
- Un aspirante se matricula hacia **sede + jornada + grado** → grupo de esa sede.

**Hay que reforzar:**
- El validador pasa a verificar **por sede**: DANE de 12 díg, consecutivo, zona, y que los grupos usen solo jornadas/niveles que la sede declaró ofrecer.
- Coherencia: no permitir un grupo «Media – nocturna» en una sede que no ofrece esa combinación.
- La sede principal (01) sigue siendo obligatoria y no borrable.

---

## 7. Cómo se ve para el colegio (UX)

- **Vista institución (rector):** consolidado de todas las sedes — total de estudiantes y KPIs desglosados por sede, tabla de sedes con su matrícula/jornadas/estado SIMAT, reporte consolidado o por sede, botón «entrar a la sede».
- **Vista sede (coordinador de sede):** todo filtrado a su sede — sus grupos, estudiantes, matrícula, asistencia, docentes, aulas, su propio Anexo 6A. No ve otras sedes.
- **Pieza de unión:** un **selector de sede** en la barra superior, visible para roles con más de una sede.
- **Rol nuevo `coordinador_sede`:** se asigna a una o varias sedes de forma configurable (en cualquier orden), no queda amarrado a una sola.

---

## 8. Decisiones confirmadas

1. **Sede del estudiante → derivada del grupo.** El estudiante se matricula en un grupo y su sede sale de ahí automáticamente: una sola fuente de verdad, imposible que se contradiga, SIMAT siempre coherente.
2. **Municipio, sector y calendario → pueden diferir por sede.** Se modelan en la sede, con el dato de la institución como valor por defecto.
3. **Docente → puede estar en varias sedes (M2M).** Como las sedes suelen repartirse por nivel, la asignación sigue esa realidad.
4. **Coordinador → por sede, con asignación configurable.** Una o varias sedes en cualquier orden; no es un rol rígido de una sola sede.
5. **Finanzas → atadas al nivel de escolaridad, iguales en todas las sedes.** Oficial: sin cobro. Privado: todo va por nivel, así que no varía por sede. Se queda como está — sin fase de finanzas por sede.

---

## 9. Ruta de migración — aditiva, sin romper nada

Nada de esto es un «big bang». Se hace por fases; cada una es compatible hacia atrás y el sistema sigue funcionando igual mientras se completa.

| Fase | Qué hace | Riesgo |
|---|---|---|
| **A · Datos a la sede** | Mover/duplicar municipio, sector, calendario, prestación y contacto a la Sede, con default = institución. | Aditivo · 0 cambios de UX |
| **B · Fuente única** | El grupo manda sede + jornada; sincronizar estudiante y ficha desde el grupo; deprecar las copias. | Quita duplicados |
| **C · Oferta por sede** | Matriz Sede × jornada × nivel; validar grupos contra lo que la sede ofrece. | Fiel al C-600 |
| **D · Scoping** | Sede en aula y docente (M2M); coordinador con sedes asignables; filtros y selector de sede en tableros/asistencia. | Rol coord. sede |
| **E · Consolidación** | Tableros del rector con desglose por sede y validador/reporte SIMAT por sede. | Rector + SIMAT |

**Punto de arranque recomendado cuando se retome:** la **Fase A** es la más segura (solo agrega campos a la sede con el valor de la institución por defecto, sin cambiar nada de lo que ya funciona).

---

## 10. Estado actual del código (referencia)

- `Sede` — `simat/models.py:92` (institucion, nombre, codigo_dane_sede, consecutivo, zona, jornada_principal, es_principal, activa). Auto-creación de sede principal vía `Sede.asegurar_principal` en `simat/signals.py`.
- CRUD de sedes ya existe en UI: `simat/urls.py` (`lista_sedes`, `crear_sede`, `editar_sede`, `eliminar_sede`) + templates `simat/sedes_lista.html`, `simat/sede_form.html`.
- `sede` FK en: `gestion_academica.Grupo.sede`, `gestion_academica.Estudiante.sede`, `gestion_academica.CaracterizacionEstudiante.sede`, `admisiones.Aspirante.sede`.
- Derivación en exportador: `_sede_efectiva` / `_jornada_efectiva` / `_grupo_de` en `simat/views.py` (grupo gana).
- Campos SIMAT hoy en `finanzas.InstitucionEducativa`: `codigo_dane`, `simat_municipio_etc`, `simat_calendario`, `simat_sector`, `simat_prestacion_servicio`, `simat_consecutivo_sede_automatico`, property `es_multisede`.
- Sin dimensión de sede hoy: `Docente`, `Aula`, `Grado`, `Curso`, `RegistroAsistencia`, finanzas (`NivelEscolaridad`/`ConceptoPago`).

---

**Fuentes oficiales:** Guía DUE–SIMAT–EVI (MEN) · Formulario Único Censal C-600 2024 (DANE).
