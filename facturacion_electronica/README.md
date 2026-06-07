# Módulo de Facturación Electrónica (Factus / DIAN)

Documentación completa del módulo `facturacion_electronica`: qué es, cómo se
activa, cómo se configura y **cómo se conecta con la emisión de facturas cuando
un usuario paga**.

---

## 1. ¿Qué es y por qué existe?

En Colombia la **facturación electrónica ante la DIAN es obligatoria**. Una factura
legal necesita: XML firmado, **CUFE**, validación ante la DIAN y representación
gráfica (PDF) con QR. La plataforma **no** hace esto por sí sola: delega en un
**proveedor tecnológico autorizado**, en este caso **Factus** (`developers.factus.com.co`),
que recibe un JSON, genera el XML, lo firma, obtiene el CUFE y lo valida ante la DIAN.

> **Importante:** los *recibos* y *órdenes de pago* que ya genera el sistema son
> documentos **internos** (no fiscales). La factura electrónica es el documento
> **legal**. Este módulo **suma** la capa fiscal; no reemplaza los recibos.

Es un **módulo opcional de pago adicional**: cada institución lo activa por
separado (la API de Factus tiene costo por documento/paquete).

---

## 2. Arquitectura del módulo

```
facturacion_electronica/
├── models.py     → ConfiguracionFactus (credenciales + switch) · FacturaElectronica (registro/auditoría)
├── services.py   → FactusClient: OAuth2 (token en caché ~55min), crear/consultar factura
├── payload.py    → construye el JSON de la factura desde un PagoRegistrado
├── forms.py      → formulario de credenciales
├── views.py      → configuracion · probar_conexion · lista_facturas · emitir_factura
├── urls.py       → /finanzas/facturacion-electronica/...
├── admin.py      → gestión + switch `activo` (propietario)
└── templates/    → configuracion.html · lista_facturas.html
```

### Modelos
- **`ConfiguracionFactus`** (1 por institución): `client_id`, `client_secret`,
  `username`, `password` (todos **encriptados**), `ambiente` (SANDBOX/PRODUCCION),
  `numbering_range_id`, contador `facturas_emitidas`, y el interruptor **`activo`**.
  - `.credenciales_completas` → True si tiene las 4 credenciales.
  - `.operativo` → True si `activo` + credenciales + `numbering_range_id`.
- **`FacturaElectronica`**: vínculo a `PagoRegistrado`/`Estudiante`, `reference_code`
  (idempotente), `estado` (PENDIENTE/VALIDADA/RECHAZADA/ERROR), `numero`, `cufe`,
  `url_pdf`, `url_xml`, `json_enviado`, `json_respuesta`, `mensaje`. Trazabilidad
  total para auditorías DIAN.

---

## 3. Activación (monetización del adicional)

El módulo NO funciona hasta que el **propietario de la plataforma** lo activa,
tras el pago del cliente:

1. Admin de Django → **Configuraciones Factus** → la institución → marcar **`activo = True`**.
2. El contador `facturas_emitidas` registra el consumo (base para cobrar el adicional).

Mientras `activo = False`: la institución puede **configurar credenciales**, pero
**no aparece el botón "Emitir factura"** ni se puede emitir.

---

## 4. Configuración paso a paso (institución)

Acceso: **Finanzas → sidebar → "Facturación Electrónica" → Configuración**
(`/finanzas/facturacion-electronica/configuracion/`).

1. **Obtener credenciales** en el panel de Factus (`developers.factus.com.co`):
   `client_id`, `client_secret`, `username`, `password`.
2. **Obtener el rango de numeración** autorizado por la DIAN (`numbering_range_id`)
   — se consulta en Factus (`GET /v2/numbering-ranges`).
3. En la página de configuración: pegar credenciales, elegir **ambiente Sandbox**,
   poner el `numbering_range_id`, **Guardar**.
4. Clic en **"Probar conexión con Factus"** → debe decir *"Conexión exitosa"*
   (esto solo obtiene un token; no emite nada).
5. El propietario marca `activo = True`.

---

## 5. Catálogos a mapear (en `payload.py`)

Factus usa catálogos con IDs. Los valores por defecto están marcados con `TODO`
y deben verificarse en sandbox con los endpoints:

| Catálogo | Endpoint Factus | Uso |
|---|---|---|
| Municipios | `GET /v2/municipalities` | `municipality_id` del cliente |
| Tributos | `GET /v2/tributes` | IVA / excluido |
| Unidades de medida | `GET /v2/measurement-units` | `unit_measure_id` |
| Métodos de pago | `GET /v2/payment-methods` | `payment_method_code` |
| Tipos de documento | `GET /v2/identification-documents` | CC/NIT/TI del cliente |

> ⚠️ **Educación formal = EXCLUIDA de IVA.** En `payload.py` el ítem va con
> `tax_rate: "0.00"` e `is_excluded: 1`. No cambiar sin asesoría tributaria.

---

## 6. CÓMO SE CONECTA CON LA EMISIÓN AL PAGAR (lo central)

### Flujo actual de pago (NO cambia)
1. Usuario paga → **efectivo** (registro manual) o **Mercado Pago** (webhook confirma).
2. Se crea/actualiza un `PagoRegistrado` y la cuenta queda `PAGADO`.
3. Se generan recibo/orden interna (PDF). **Esto sigue igual.**

### Capa nueva: emisión de la factura electrónica
Sobre ese mismo `PagoRegistrado` se emite la factura legal. Hay **dos modos**:

#### Modo A — Manual (actual / recomendado para empezar)
- En **Finanzas → Historial del estudiante**, cada pago tiene el botón
  **"Factura electrónica"** (visible solo si el módulo está `operativo`).
- Al hacer clic (POST a `facturacion_electronica:emitir_factura`):
  1. Se crea/recupera una `FacturaElectronica` con `reference_code = "PAGO-{id}"` (**idempotente**).
  2. `payload.construir_payload_desde_pago()` arma el JSON (cliente + ítem educativo excluido de IVA).
  3. `FactusClient.crear_factura()` autentica (token en caché) y hace `POST /v2/bills/validate`.
  4. Factus valida ante la DIAN y devuelve **número + CUFE + PDF + XML**.
  5. Se guardan en `FacturaElectronica` (estado `VALIDADA`) y sube el contador `facturas_emitidas`.

#### Modo B — Automático (IMPLEMENTADO ✓)
Emite la factura apenas se confirma el pago, sin intervención. Ya está conectado:
- **Efectivo:** en `finanzas.views.registrar_pago`, tras `pago.save()`, llama a
  `facturacion_electronica.emision.disparar_emision_automatica(pago)`.
- **Mercado Pago:** en `finanzas_mercadopago_webhook`, tras crear el `PagoRegistrado`,
  mediante `transaction.on_commit(...)` (solo emite si el pago realmente quedó guardado).
- Ambos encolan la tarea Celery **`emitir_factura_async(pago_id)`**.

**Interruptor del Modo B:** el campo `ConfiguracionFactus.emision_automatica`
(checkbox en la página de Configuración). Si está **apagado**, los hooks son
**no-op** total: solo se emite con el botón manual (Modo A). Esto permite tener
el Modo B "listo pero desactivado".

> Recomendación: validar varias facturas con el **botón manual** en sandbox, y
> cuando estés conforme, encender **"Emisión automática"** en la configuración.

> **Esquema validado en sandbox (status 201):** `payment_details` es un array
> `[{payment_form, payment_method_code, amount}]`; el cliente usa
> `identification_document_code` con códigos DIAN (13=CC, 31=NIT); los ítems usan
> `unit_measure_code`, `standard_code` y `taxes:[{code, rate}]`. La educación va
> `is_excluded=1` con `taxes:[{code:"01", rate:"0.00"}]`. Ver `payload.py`.

### Diagrama resumido
```
Pago (efectivo / MP)
      │
      ▼
PagoRegistrado  ──►  Recibo interno (PDF)        [ya existía]
      │
      ▼  (botón manual  /  Celery automático)
construir_payload_desde_pago()
      │
      ▼
FactusClient.crear_factura()  ──►  POST /v2/bills/validate
      │
      ▼
Factus firma XML + CUFE + valida DIAN
      │
      ▼
FacturaElectronica (VALIDADA): número, CUFE, PDF, XML  ──►  descargables en el listado
```

---

## 7. Flujo técnico detallado

### Autenticación (OAuth2 password grant)
```
POST {base}/oauth/token
  grant_type=password & client_id & client_secret & username & password
→ { access_token, expires_in }   (token dura ~1h; se cachea ~55 min)
```
`base` = `https://api-sandbox.factus.com.co` (sandbox) o `https://api.factus.com.co` (prod).

### Crear y validar factura
```
POST {base}/v2/bills/validate
Authorization: Bearer <token>
Body JSON: { numbering_range_id, reference_code, payment_method_code, customer{...}, items[...] }
→ { data: { bill: { number, cufe, public_url (PDF), ... } } }
```
El `FactusClient` reintenta una vez si el token expiró (401/403).

---

## 8. Notas Crédito y Débito (IMPLEMENTADO ✓, validado en sandbox)

Una factura electrónica **NO se borra**. Para corregirla se emite una nota:
- **Nota Crédito** (`POST /v2/credit-notes/validate`): anula o reduce la factura
  (devolución, anulación, descuento). Códigos DIAN: 1=Devolución, 2=Anulación,
  3=Rebaja, 4=Ajuste de precio, 5=Otros.
- **Nota Débito** (`POST /v2/debit-notes/validate`): incrementa la factura
  (intereses, cargos). Códigos DIAN: 1=Intereses, 2=Gastos, 3=Cambio valor, 4=Otros.

**Cómo se usa:** en **Facturación Electrónica → listado**, cada factura VALIDADA
muestra los botones **NC** y **ND**. Se abre un modal para elegir el motivo (código
de corrección) y se emite. La nota reutiliza el cliente e ítems de la factura
original y queda enlazada vía `FacturaElectronica.documento_origen`.

**Esquema validado:** la nota requiere `numbering_range_id` (rango propio de NC/ND),
`reference_code`, `bill_number` (número de la factura original), `correction_concept_code`,
`payment_details`, `customer`, `items`. Las notas usan **CUDE** (no CUFE), que se
guarda en el mismo campo `cufe`. Configura los rangos en la página de Configuración
(`numbering_range_id_nota_credito` / `_debito`).

### 8.1 Sincronización contable automática (al validar la nota)
- **Nota Crédito (anulación):** marca el `PagoRegistrado` de origen como `anulado=True`
  (no se borra, queda en historial). `monto_pagado_actual` excluye pagos anulados → la
  cuenta **vuelve a quedar pendiente/vencida** con su saldo restaurado. ✅ Validado.
- **Nota Débito (cargo adicional):** aumenta `monto_asignado` de la cuenta de origen por
  el monto indicado → genera **saldo pendiente adicional**. ✅ Lógica lista.
- Es **seguro**: el ajuste contable solo se aplica si la nota se **validó** en la DIAN.
  Si Factus rechaza la nota, queda en ERROR y **no** se toca la contabilidad.

### 8.2 ⚠️ Endpoint de Nota Débito (pendiente de confirmar)
En el sandbox, `POST /v2/debit-notes/validate` responde **405** (la ruta existe pero no
acepta POST), y las variantes dan 404. La doc de Factus bloquea el scraping, así que el
**endpoint exacto de creación de nota débito debe confirmarse con Factus** (soporte/doc).
La UI, la lógica y la contabilidad ya están listas: cuando se conozca la ruta correcta,
es **cambiar 1 línea** en `services.crear_nota_debito`. Mientras tanto, la nota débito
falla de forma controlada (estado ERROR, sin afectar la contabilidad).
La **nota crédito funciona end-to-end** (es la que cubre anulaciones/devoluciones).

---

## 9. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| No aparece el botón "Factura electrónica" | Módulo no `operativo` | Verificar `activo=True` + credenciales + `numbering_range_id` |
| "Probar conexión" falla 401 | Credenciales mal | Re-copiar client_id/secret/usuario/contraseña |
| Factura `RECHAZADA` | Catálogos/datos del cliente | Revisar `json_respuesta` en el admin; ajustar `payload.py` |
| Error de IVA | Concepto no marcado como excluido | Confirmar `is_excluded=1`, `tax_rate=0.00` |
| 403 al entrar a Configuración | Falta permiso | Usa `finanzas.change_institucioneducativa` (igual que Pasarelas de Pago) |

---

## 10. Checklist salida a producción

- [ ] Probadas varias facturas en **sandbox** y validadas por DIAN
- [ ] Catálogos de `payload.py` verificados (municipio, tributo, etc.)
- [ ] Datos tributarios del acudiente/estudiante completos (o "consumidor final")
- [ ] Rango de numeración de **producción** cargado
- [ ] Cambiar `ambiente` a **PRODUCCION** y volver a "Probar conexión"
- [ ] Decidir Modo A (manual) o Modo B (automático)
- [ ] (Opcional) Implementar notas crédito para anulaciones

---

## 11. Rutas del módulo

| Vista | URL | Acceso |
|---|---|---|
| Configuración | `/finanzas/facturacion-electronica/configuracion/` | `finanzas.change_institucioneducativa` |
| Probar conexión | `.../configuracion/probar/` (POST) | idem |
| Listado de facturas | `/finanzas/facturacion-electronica/facturas/` | login |
| Emitir factura | `.../emitir/<pago_id>/` (POST) | `finanzas.add_pagoregistrado` + módulo `operativo` |
