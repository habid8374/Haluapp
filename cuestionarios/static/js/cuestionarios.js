// static/js/cuestionarios.js

document.addEventListener('DOMContentLoaded', function () {
    console.log("cuestionarios.js cargado y ejecutándose.");

    const actividadId = document.getElementById('actividad-id')?.value;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    if (!actividadId || !csrfToken) {
        console.error("No se encontró el ID de la actividad o el token CSRF. El editor no puede funcionar.");
        return;
    }

    const apiUrl = `/cuestionarios/api/${actividadId}/`;
    let cuestionarioData = {};

    const editorPreguntas = document.getElementById('editor-preguntas');
    const btnAgregarPregunta = document.getElementById('btn-agregar-pregunta');
    const btnGuardar = document.getElementById('btn-guardar');
    const toggleActivo = document.getElementById('toggle-activo');

    // --- RENDERIZADO DE LA INTERFAZ ---

    function renderizarOpcion(opcion, pregunta) {
        const opcionId = opcion.id || `new_${Date.now()}_${Math.random()}`;
        const esCorrectaChecked = opcion.es_correcta ? 'checked' : '';
        const inputType = pregunta.tipo === 'seleccion_multiple' ? 'checkbox' : 'radio';
        const inputName = pregunta.tipo === 'seleccion_multiple' ? `correcta_${opcionId}` : `correcta_${pregunta.id || 'new'}`;

        return `
            <div class="input-group mb-2 opcion-item" data-opcion-id="${opcionId}">
                <div class="input-group-text">
                    <input class="form-check-input mt-0" type="${inputType}" name="${inputName}" ${esCorrectaChecked}>
                </div>
                <input type="text" class="form-control opcion-texto" value="${opcion.texto || ''}" placeholder="Texto de la opción">
                <button class="btn btn-outline-danger btn-sm btn-eliminar-opcion" type="button" title="Eliminar Opción"><i class="fas fa-trash"></i></button>
            </div>
        `;
    }

    function renderizarPregunta(pregunta) {
        const preguntaId = pregunta.id || `new_${Date.now()}_${Math.random()}`;
        const opcionesHtml = (pregunta.opciones || []).map(op => renderizarOpcion(op, pregunta)).join('');
        const showOptions = !['texto_libre', 'emparejamiento'].includes(pregunta.tipo);

        const preguntaCard = document.createElement('div');
        preguntaCard.className = 'list-group-item pregunta-card mb-3 p-3 border rounded';
        preguntaCard.dataset.preguntaId = preguntaId;
        preguntaCard.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="fw-bold">Pregunta</span>
                <button class="btn btn-sm btn-outline-danger btn-eliminar-pregunta" type="button">Eliminar Pregunta</button>
            </div>
            <textarea class="form-control mb-2 enunciado" placeholder="Escribe el enunciado...">${pregunta.enunciado || ''}</textarea>
            <div class="row align-items-end">
                <div class="col-md-6">
                    <label class="form-label small">Tipo de Pregunta</label>
                    <select class="form-select form-select-sm tipo-pregunta">
                        <option value="opcion_multiple" ${pregunta.tipo === 'opcion_multiple' ? 'selected' : ''}>Opción Única</option>
                        <option value="seleccion_multiple" ${pregunta.tipo === 'seleccion_multiple' ? 'selected' : ''}>Selección Múltiple</option>
                        <option value="verdadero_falso" ${pregunta.tipo === 'verdadero_falso' ? 'selected' : ''}>Verdadero/Falso</option>
                        <option value="texto_libre" ${pregunta.tipo === 'texto_libre' ? 'selected' : ''}>Texto Libre</option>
                        <option value="emparejamiento" ${pregunta.tipo === 'emparejamiento' ? 'selected' : ''}>Emparejamiento</option>
                    </select>
                </div>
                <div class="col-md-4">
                    <label class="form-label small">Puntaje</label>
                    <input type="number" class="form-control form-control-sm puntaje" value="${pregunta.puntaje || 1}" min="1">
                </div>
            </div>
            <div class="opciones-container mt-3 ${showOptions ? '' : 'd-none'}">${opcionesHtml}</div>
            <button class="btn btn-sm btn-outline-success btn-agregar-opcion mt-2 ${showOptions ? '' : 'd-none'}" type="button"><i class="fas fa-plus"></i> Agregar Opción</button>
        `;
        editorPreguntas.appendChild(preguntaCard);
        renumerarPreguntas();
    }

    function renumerarPreguntas() {
        document.querySelectorAll('.pregunta-card').forEach((card, index) => {
            card.querySelector('.fw-bold').textContent = `Pregunta #${index + 1}`;
        });
    }

    function renderizarCuestionario() {
        document.getElementById('titulo').value = cuestionarioData.titulo;
        document.getElementById('descripcion').value = cuestionarioData.descripcion;
        document.getElementById('tiempo-limite').value = cuestionarioData.tiempo_limite;
        document.getElementById('intentos-permitidos').value = cuestionarioData.intentos_permitidos;
        document.getElementById('mostrar-respuestas').checked = cuestionarioData.mostrar_respuestas;
        toggleActivo.checked = cuestionarioData.activo;

        editorPreguntas.innerHTML = '';
        cuestionarioData.preguntas.sort((a, b) => a.orden - b.orden).forEach(renderizarPregunta);
    }

    // --- LÓGICA DE EVENTOS ---

    function agregarPregunta() {
        const nuevaPregunta = {
            enunciado: '', tipo: 'opcion_multiple', puntaje: 1, orden: cuestionarioData.preguntas.length,
            opciones: [{ texto: '', es_correcta: true, orden: 0 }, { texto: '', es_correcta: false, orden: 1 }]
        };
        cuestionarioData.preguntas.push(nuevaPregunta);
        renderizarPregunta(nuevaPregunta);
    }

    function guardarCuestionario() {
        btnGuardar.disabled = true;
        btnGuardar.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Guardando...';

        const dataToSave = {
            titulo: document.getElementById('titulo').value,
            descripcion: document.getElementById('descripcion').value,
            tiempo_limite: parseInt(document.getElementById('tiempo-limite').value) || 0,
            intentos_permitidos: parseInt(document.getElementById('intentos-permitidos').value) || 1,
            mostrar_respuestas: document.getElementById('mostrar-respuestas').checked,
            activo: toggleActivo.checked,
            preguntas: []
        };

        document.querySelectorAll('.pregunta-card').forEach((card, index) => {
            const pregunta = {
                id: card.dataset.preguntaId.startsWith('new_') ? null : parseInt(card.dataset.preguntaId),
                enunciado: card.querySelector('.enunciado').value,
                tipo: card.querySelector('.tipo-pregunta').value,
                puntaje: parseInt(card.querySelector('.puntaje').value) || 1,
                orden: index,
                opciones: []
            };

            if (['opcion_multiple', 'seleccion_multiple', 'verdadero_falso', 'emparejamiento'].includes(pregunta.tipo)) {
                card.querySelectorAll('.opcion-item').forEach((opcionEl, opIndex) => {
                    const input = opcionEl.querySelector('input[type=radio], input[type=checkbox]');
                    pregunta.opciones.push({
                        id: opcionEl.dataset.opcionId.startsWith('new_') ? null : parseInt(opcionEl.dataset.opcionId),
                        texto: opcionEl.querySelector('.opcion-texto').value,
                        es_correcta: input.checked,
                        orden: opIndex
                    });
                });
            }
            dataToSave.preguntas.push(pregunta);
        });

        fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify(dataToSave)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Cuestionario guardado exitosamente.');
                window.location.reload();
            } else {
                alert('Error al guardar: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Ocurrió un error de red. Revisa la consola para más detalles.');
        })
        .finally(() => {
            btnGuardar.disabled = false;
            btnGuardar.innerHTML = '<i class="fas fa-save me-1"></i> Guardar Cambios';
        });
    }

    function cargarDatos() {
        fetch(apiUrl).then(res => res.json()).then(data => {
            cuestionarioData = data;
            renderizarCuestionario();
        }).catch(err => console.error('Error al cargar:', err));
    }

    // Event Listeners
    btnAgregarPregunta.addEventListener('click', agregarPregunta);
    btnGuardar.addEventListener('click', guardarCuestionario);
    
    editorPreguntas.addEventListener('click', function(e) {
        const preguntaCard = e.target.closest('.pregunta-card');
        if (!preguntaCard) return;

        if (e.target.closest('.btn-eliminar-pregunta')) {
            preguntaCard.remove();
            renumerarPreguntas();
        }
        if (e.target.closest('.btn-agregar-opcion')) {
            const preguntaId = preguntaCard.dataset.preguntaId;
            const tipoPregunta = preguntaCard.querySelector('.tipo-pregunta').value;
            const nuevaOpcion = { texto: '', es_correcta: false, orden: preguntaCard.querySelectorAll('.opcion-item').length };
            preguntaCard.querySelector('.opciones-container').insertAdjacentHTML('beforeend', renderizarOpcion(nuevaOpcion, {id: preguntaId, tipo: tipoPregunta}));
        }
        if (e.target.closest('.btn-eliminar-opcion')) {
            e.target.closest('.opcion-item').remove();
        }
    });

    editorPreguntas.addEventListener('change', function(e) {
        if (e.target.classList.contains('tipo-pregunta')) {
            const preguntaCard = e.target.closest('.pregunta-card');
            const opcionesContainer = preguntaCard.querySelector('.opciones-container');
            const btnAgregarOpcion = preguntaCard.querySelector('.btn-agregar-opcion');
            const tipoSeleccionado = e.target.value;

            const showOptions = !['texto_libre', 'emparejamiento'].includes(tipoSeleccionado);
            opcionesContainer.classList.toggle('d-none', !showOptions);
            btnAgregarOpcion.classList.toggle('d-none', !showOptions);
            
            if (tipoSeleccionado === 'verdadero_falso') {
                opcionesContainer.innerHTML = [
                    renderizarOpcion({ texto: 'Verdadero', es_correcta: true, orden: 0 }, {id: preguntaCard.dataset.preguntaId, tipo: tipoSeleccionado}),
                    renderizarOpcion({ texto: 'Falso', es_correcta: false, orden: 1 }, {id: preguntaCard.dataset.preguntaId, tipo: tipoSeleccionado})
                ].join('');
            }
        }
    });

    cargarDatos();
});
</script>
<!-- ▲▲▲ FIN DEL JAVASCRIPT INTEGRADO ▲▲▲ -->
{% endblock %}