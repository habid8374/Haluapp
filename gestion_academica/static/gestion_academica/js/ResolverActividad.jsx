// static/gestion_academica/js/ResolverActividad.jsx

const { useState, useEffect, useRef, StrictMode } = React;

// --- i18n: textos traducidos por Django (ES/EN/FR), inyectados con json_script.
//     Si por algo faltara el bloque, se usa el texto en español de respaldo. ---
const I18N = (() => {
    try { return JSON.parse(document.getElementById('i18n-actividad').textContent); }
    catch (e) { return {}; }
})();
function t(key, fallback, vars) {
    let s = (I18N && I18N[key]) || fallback;
    if (vars) { for (const k in vars) { s = s.split('%(' + k + ')s').join(vars[k]); } }
    return s;
}

// --- Componente de Temporizador ---
function Timer({ initialSeconds, onTimeUp }) {
    const [seconds, setSeconds] = useState(initialSeconds);
    const intervalRef = useRef();

    useEffect(() => {
        if (seconds <= 0) {
            clearInterval(intervalRef.current);
            onTimeUp(); // Llama a la función del padre cuando el tiempo se acaba
        }
    }, [seconds, onTimeUp]);

    useEffect(() => {
        intervalRef.current = setInterval(() => {
            setSeconds(prev => prev - 1);
        }, 1000);
        return () => clearInterval(intervalRef.current);
    }, []);
    
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);

    return (
        <div className={`alert ${seconds < 300 ? 'alert-danger' : 'alert-info'} sticky-top text-center fs-4 shadow`}>
            <i className="bi bi-clock-history me-2"></i>
            {t('tiempoRestante', 'Tiempo restante:')} <strong>{minutes}:{remainingSeconds.toString().padStart(2, '0')}</strong>
        </div>
    );
}

// --- Componente Principal de la Aplicación de Actividad ---
function ActividadApp() {
    // --- OBTENER DATOS DE LA PLANTILLA DJANGO ---
    const appElement = document.getElementById('react-app');
    const apiUrl = appElement.dataset.apiUrl;
    const submitUrl = appElement.dataset.submitUrl;
    const redirectUrl = appElement.dataset.redirectUrl;
    const tiempoInicial = appElement.dataset.tiempoRestante;
    
    // --- ESTADOS DE REACT ---
    const [actividad, setActividad] = useState(null);
    const [respuestas, setRespuestas] = useState({});
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [feedback, setFeedback] = useState({ message: '', type: '' });
    const [showReviewModal, setShowReviewModal] = useState(false);

    // --- EFECTO PARA CARGAR DATOS DE LA ACTIVIDAD ---
    useEffect(() => {
        const token = localStorage.getItem('accessToken');
        if (!token) {
            setFeedback({ message: t('tokenNoEncontrado', 'No se encontró el token de acceso. Por favor, inicia sesión de nuevo.'), type: 'danger' });
            setLoading(false);
            return;
        }

        fetch(apiUrl, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (response.status === 401) throw new Error(t('sesionExpirada', 'Tu sesión ha expirado. Por favor, inicia sesión de nuevo.'));
            if (!response.ok) throw new Error(t('noCargoActividad', 'No se pudo cargar la actividad.'));
            return response.json();
        })
        .then(data => {
            setActividad(data);
            setLoading(false);
        })
        .catch(error => {
            setFeedback({ message: t('errorFatal', 'Error fatal: %(msg)s', { msg: error.message }), type: 'danger' });
            setLoading(false);
        });
    }, [apiUrl]);

    // --- MANEJADORES DE EVENTOS ---
    const handleRespuestaChange = (preguntaId, valor) => {
        setRespuestas(prev => ({ ...prev, [preguntaId]: valor }));
    };

    const handleTimeUp = () => {
        setFeedback({ message: t('tiempoAgotado', '¡Se acabó el tiempo! Tus respuestas serán enviadas automáticamente.'), type: 'warning' });
        setTimeout(() => handleSubmit(), 2000);
    };

    const handleSubmitClick = () => {
        setShowReviewModal(true);
    };

    const handleConfirmSubmit = () => {
        setShowReviewModal(false);
        handleSubmit();
    };

    const handleSubmit = () => {
        setSubmitting(true);
        setFeedback({ message: '', type: '' });

        const csrftoken = document.querySelector('input[name=csrfmiddlewaretoken]')?.value;
        const token = localStorage.getItem('accessToken');

        if (!token) {
            setFeedback({ message: t('sinTokenSesion', 'No se encontró tu token de sesión. No se pueden enviar las respuestas.'), type: 'danger' });
            setSubmitting(false);
            return;
        }

        fetch(submitUrl, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json', 
                'X-CSRFToken': csrftoken,
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ respuestas: respuestas })
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            if (status >= 200 && status < 300) {
                setFeedback({ message: body.message || t('enviadasExito', '¡Respuestas enviadas con éxito! Redirigiendo...'), type: 'success' });
                setTimeout(() => { window.location.href = redirectUrl; }, 2500);
            } else { throw new Error(body.error || t('errorGuardar', 'Ocurrió un error al guardar tus respuestas.')); }
        })
        .catch(error => {
            setFeedback({ message: t('errorEnviar', 'Error al enviar: %(msg)s', { msg: error.message }), type: 'danger' });
        })
        .finally(() => { setSubmitting(false); });
    };
    
    // --- RENDERIZADO ---
    if (loading) { return <div className="text-center p-5"><div className="spinner-border" style={{width: "3rem", height: "3rem"}}></div><p className="mt-3">{t('cargandoExamen', 'Cargando examen...')}</p></div>; }
    if (!actividad) { return <div className="alert alert-danger mx-3">{feedback.message}</div>; }

    const totalPreguntas = actividad.preguntas.length;
    const preguntasRespondidas = Object.values(respuestas).filter(r => r !== '' && r !== null).length;

    return (
        <React.Fragment>
            {tiempoInicial && <Timer initialSeconds={parseInt(tiempoInicial, 10)} onTimeUp={handleTimeUp} />}
            <div className="container py-4">
                <h1>{actividad.titulo}</h1>
                <p className="lead">{actividad.descripcion}</p>
                <div className="progress mb-3" style={{ height: "10px" }}>
                    <div className="progress-bar" role="progressbar" style={{ width: `${(preguntasRespondidas / totalPreguntas) * 100}%` }} ></div>
                </div>
                <p>{t('progreso', 'Progreso: %(done)s de %(total)s preguntas respondidas', { done: preguntasRespondidas, total: totalPreguntas })}</p>
                <hr />

                {actividad.preguntas.map((pregunta, index) => (
                    <div key={pregunta.id} className="card mb-3 shadow-sm">
                        <div className="card-header"><strong>{t('pregunta', 'Pregunta %(n)s', { n: index + 1 })}</strong></div>
                        <div className="card-body">
                            <p className="card-text fs-5" dangerouslySetInnerHTML={{ __html: pregunta.enunciado }}></p>
                            
                            {pregunta.tipo === 'opcion_multiple' && pregunta.opciones.map(opcion => (
                                <div className="form-check" key={opcion.id}>
                                    <input className="form-check-input" type="radio" name={`pregunta-${pregunta.id}`} id={`opcion-${opcion.id}`} onChange={() => handleRespuestaChange(pregunta.id, opcion.id)} checked={respuestas[pregunta.id] === opcion.id} />
                                    <label className="form-check-label" htmlFor={`opcion-${opcion.id}`}>{opcion.texto}</label>
                                </div>
                            ))}

                            {pregunta.tipo === 'respuesta_abierta' && (
                                <textarea className="form-control" rows="4" placeholder={t('placeholderRespuesta', 'Escribe tu respuesta aquí...')} onChange={(e) => handleRespuestaChange(pregunta.id, e.target.value)} value={respuestas[pregunta.id] || ''}></textarea>
                            )}
                        </div>
                    </div>
                ))}
                
                <div className="mt-4">
                    <button 
                        className="btn btn-primary btn-lg" 
                        onClick={handleSubmitClick}
                        disabled={submitting || preguntasRespondidas < totalPreguntas}
                    >
                        {t('revisarEnviar', 'Revisar y enviar respuestas')}
                    </button>
                </div>

                {feedback.message && (<div className={`alert mt-3 alert-${feedback.type}`}>{feedback.message}</div>)}
            </div>

            {/* --- MODAL DE CONFIRMACIÓN DE BOOTSTRAP --- */}
            {showReviewModal && (
                <div className="modal" tabIndex="-1" style={{ display: 'block', backgroundColor: 'rgba(0,0,0,0.5)' }}>
                    <div className="modal-dialog modal-dialog-centered">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h5 className="modal-title">{t('confirmarEnvio', 'Confirmar envío')}</h5>
                                <button type="button" className="btn-close" onClick={() => setShowReviewModal(false)}></button>
                            </div>
                            <div className="modal-body">
                                <p>{t('hasRespondido', 'Has respondido %(done)s de %(total)s preguntas.', { done: preguntasRespondidas, total: totalPreguntas })}</p>
                                <p>{t('confirmacion', '¿Estás seguro de que quieres enviar tus respuestas? Una vez enviadas, no podrás modificarlas.')}</p>
                            </div>
                            <div className="modal-footer">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowReviewModal(false)}>{t('volverRevisar', 'Volver y revisar')}</button>
                                <button type="button" className="btn btn-primary" onClick={handleConfirmSubmit}>{t('siEnviar', 'Sí, enviar definitivamente')}</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </React.Fragment>
    );
}

const container = document.getElementById('react-app');
const root = ReactDOM.createRoot(container);
root.render(<React.StrictMode><ActividadApp /></React.StrictMode>);
