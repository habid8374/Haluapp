document.addEventListener('DOMContentLoaded', function () {
    const chatBubble = document.getElementById('halu-chat-bubble');
    // Obtenemos la URL de la API desde el propio botón del chat
    const apiUrl = chatBubble ? chatBubble.dataset.apiUrl : null;
    const csrftoken = getCookie('csrftoken');

    // Si no encontramos los elementos básicos, no hacemos nada.
    if (!chatBubble || !apiUrl) {
        console.error("HALU: No se encontró el botón del chat o la URL de la API. El asistente no se iniciará.");
        return;
    }

    const chatWindow = document.getElementById('halu-chat-window');
    const chatBody = document.getElementById('halu-chat-body');
    const inputForm = document.getElementById('halu-input-form');
    const userInput = document.getElementById('halu-user-input');
    
    // NUEVO: Memoria del chat para enviar a la IA
    let chatHistory = [];

    chatBubble.addEventListener('click', () => {
        chatWindow.style.display = chatWindow.style.display === 'flex' ? 'none' : 'flex';
        if (chatWindow.style.display === 'flex') { userInput.focus(); }
    });

    inputForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const userMessageText = userInput.value.trim();
        if (!userMessageText) return;

        addMessage(userMessageText, 'user');
        userInput.value = '';

        fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ 
                pregunta: userMessageText,
                historial: chatHistory 
            })
        })
        .then(async response => {
            const isJson = response.headers.get('content-type')?.includes('application/json');
            const data = isJson ? await response.json() : null;
            
            if (!response.ok) {
                // Si el servidor nos mandó un JSON con el error (ej: 403 permisos), lo procesamos
                if (data && (data.respuesta || data.error)) {
                    return data;
                }
                throw new Error(`Error del servidor: ${response.status}`);
            }
            return data;
        })
        .then(data => {
            if (data.historial) {
                chatHistory = data.historial; // Actualizamos la memoria
            }
            addMessage(data.respuesta || data.error || "Respuesta no válida.", 'halu');
        })
        .catch(error => {
            console.error('Error en la petición a HALU:', error);
            addMessage('Hubo un problema de conexión. Revisa la consola (F12).', 'halu');
        });
    });

    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add(sender === 'user' ? 'user-message' : 'halu-message');
        messageDiv.innerHTML = text;
        chatBody.appendChild(messageDiv);
        chatBody.scrollTop = chatBody.scrollHeight;
    }
    
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});