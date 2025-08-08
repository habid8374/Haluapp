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
            body: JSON.stringify({ pregunta: userMessageText })
        })
        .then(response => {
            if (!response.ok) throw new Error(`Error del servidor: ${response.status}`);
            return response.json();
        })
        .then(data => {
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