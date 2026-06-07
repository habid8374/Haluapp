# Patrón: feedback en vivo para tareas IA (Celery)

> En HALU, las tareas que invocan a la IA (Gemini) corren en Celery y pueden
> tardar 15–60s. Si la vista web simplemente "redirige y espera", el usuario
> no sabe si la tarea está corriendo, falló, o se quedó atascada. Este
> documento describe el patrón que aplicamos para dar feedback visible al
> usuario sin necesidad de WebSocket.

## Por qué polling y no WebSocket aquí

WebSocket es ideal cuando hay **muchos** eventos intermedios (ej. health-check
con 8 pasos). En el planeador de clases IA solo hay 1 transición real
(GENERANDO → COMPLETADO/FALLIDO), así que **polling cada 3s** ofrece mejor
ROI: menos código, sin dependencias adicionales, y suficientemente rápido
para que el usuario no note el delay.

## Anatomía del patrón

### 1. Modelo con campo de estado y de error

```python
class PlaneacionClase(models.Model):
    class EstadoGeneracion(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        GENERANDO = "GENERANDO", "Generando"
        COMPLETADO = "COMPLETADO", "Completado"
        FALLIDO = "FALLIDO", "Fallido"

    estado_generacion = models.CharField(max_length=20, choices=EstadoGeneracion.choices)
    error_generacion = models.TextField(blank=True, default="")
    # ... campos del modelo ...
```

### 2. Vista que dispara: marca GENERANDO y encola Celery

```python
def planeacion_detalle_view(request, pk):
    planeacion = get_object_or_404(PlaneacionClase, pk=pk, docente=request.user.docente)
    if request.method == 'POST':
        planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.GENERANDO
        planeacion.error_generacion = None
        planeacion.save()
        generar_contenido_planeacion_task.delay(planeacion.id)
        messages.info(request, "La IA ha comenzado a generar tu planeación.")
        return redirect('gestion_academica:planeacion_detalle', pk=pk)
    return render(request, 'planeacion_detalle.html', {'planeacion': planeacion})
```

### 3. Tarea Celery que escribe el estado al terminar

```python
@shared_task(bind=True, max_retries=3, soft_time_limit=150)
def generar_contenido_planeacion_task(self, planeacion_id):
    try:
        planeacion = PlaneacionClase.objects.get(pk=planeacion_id)
        # ... llamar a la IA ...
        planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.COMPLETADO
        planeacion.save()
    except Exception as e:
        planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.FALLIDO
        planeacion.error_generacion = str(e)
        planeacion.save()
        raise self.retry(exc=e)
```

### 4. Endpoint de polling enriquecido

**Importante**: el endpoint debe devolver TODO lo que el frontend necesita
para mostrar el toast final, no solo el estado:

```python
@login_required
@never_cache
def get_planeacion_status_api(request, pk):
    planeacion = PlaneacionClase.objects.get(pk=pk)
    estado = str(planeacion.estado_generacion or "").strip().upper()
    return JsonResponse({
        'status': estado,
        'detalles_count': planeacion.detalles_clase.count(),
        'error_generacion': planeacion.error_generacion or "",
        'mensaje': "...",  # mensaje listo para mostrarse como toast
    })
```

### 5. Frontend: estado GENERANDO con UX rica

El template renderiza UN bloque distinto por cada estado. El estado
GENERANDO debe tener:

- **Spinner animado** y barra de progreso aproximada (5% → 95% con el tiempo).
- **Mensaje rotativo** que cambia cada 4.5s para dar sensación humana de
  progreso ("Conectando con la IA…", "Generando estructura…", etc.).
- **Timer**: tiempo transcurrido en segundos.
- **Tiempo estimado** (rango): "15–60s".
- **Botón "Detener generación"** que llama a una vista POST que marca el
  estado como FALLIDO.

### 6. Script de polling

```javascript
const POLL_INTERVAL_MS = 3000;
const HARD_TIMEOUT_SECS = 240;

function checkStatus() {
    fetch(statusUrl).then(r => r.json()).then(data => {
        const estado = (data.status || '').trim().toUpperCase();
        if (estado === 'COMPLETADO') {
            mostrarToast('success', '¡Éxito!', data.mensaje);
            setTimeout(() => window.location.reload(), 1500);
        } else if (estado === 'FALLIDO') {
            mostrarToast('danger', 'Error', data.mensaje);
            setTimeout(() => window.location.reload(), 3500);
        }
    });
}
setInterval(checkStatus, POLL_INTERVAL_MS);
checkStatus();
```

### 7. Toasts Bootstrap dinámicos

Ver `templates/gestion_academica/planeacion_detalle.html` para el código
completo de creación dinámica de toasts. Los puntos clave:

- Contenedor fijo: `<div class="position-fixed bottom-0 end-0 p-3" style="z-index: 1080;">`.
- Crear el HTML del toast con `insertAdjacentHTML`, instanciar
  `new bootstrap.Toast(el, { delay: 6000 })` y `.show()`.
- Colores: `bg-success` (éxito), `bg-danger` (error), `bg-warning text-dark`
  (timeout).

## Errores comunes

### "El polling sigue corriendo aunque la tarea terminó"

Usar una bandera `polling = true|false` y verificar al inicio de cada
`checkStatus()`. Una vez que cambia el estado, poner `polling = false`.

### "El usuario recarga durante GENERANDO y se queda sin polling"

El template SOLO incluye el `<script>` cuando `estado_generacion == 'GENERANDO'`
(`{% if planeacion.estado_generacion == 'GENERANDO' %}`). Cuando se recarga,
si el estado ya cambió, no se intenta polling — se muestra el bloque
correspondiente al nuevo estado.

### "El usuario quiere cancelar pero la tarea sigue ejecutándose en Celery"

El botón "Detener generación" solo cambia el `estado_generacion` en BD a
FALLIDO. La tarea Celery sigue corriendo (no se puede matar de forma segura)
pero al terminar verá que el estado ya no es GENERANDO y simplemente no
modificará nada. Esto evita race conditions.

Para tareas verdaderamente cancelables, usar `task.revoke(terminate=True)`
con el `task_id` guardado en el modelo (patrón ya implementado para
`LoteImportacionAspirantes`).

## Aplicar a otras tareas IA en HALU

Otras tareas Celery que se beneficiarían de este patrón:
- `analizar_propuesta_candidato_task` (gestion_academica/tasks.py)
- `generar_propuesta_horario_task` (gestion_academica/tasks.py)
- `analizar_plagio_tarea_task` (gestion_academica/tasks.py)

El patrón es siempre el mismo: agregar `estado_generacion` y `error_generacion`
al modelo, endpoint de polling, JS con toasts.
