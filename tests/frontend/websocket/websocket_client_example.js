// Ejemplo de cliente WebSocket para el sistema de Brief
class BriefWebSocketClient {
    constructor(businessId, token, options = {}) {
        this.businessId = businessId;
        this.token = token;
        this.options = {
            llm_model: options.llm_model || 'gpt-4o-mini',
            llm_temperature: options.llm_temperature || 0.7,
            llm_max_tokens: options.llm_max_tokens || 4000,
            ...options
        };
        
        this.websocket = null;
        this.sessionId = null;
        this.isConnected = false;
        
        // Callbacks que puedes personalizar
        this.onConnectionEstablished = null;
        this.onProgressUpdate = null;
        this.onTypingIndicator = null;
        this.onCompleteResponse = null;
        this.onError = null;
        this.onSessionCreated = null;
        this.onBriefCompleted = null;
    }
    
    // Conectar al WebSocket
    connect() {
        const baseUrl = window.location.origin.replace('http', 'ws');
        const params = new URLSearchParams({
            token: this.token,
            llm_model: this.options.llm_model,
            llm_temperature: this.options.llm_temperature,
            llm_max_tokens: this.options.llm_max_tokens
        });
        
        const wsUrl = `${baseUrl}/api/v1/business/${this.businessId}/brief/chat?${params}`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('🔌 WebSocket conectado');
            this.isConnected = true;
        };
        
        this.websocket.onmessage = (event) => {
            this.handleMessage(JSON.parse(event.data));
        };
        
        this.websocket.onclose = (event) => {
            console.log('🔌 WebSocket desconectado:', event.code, event.reason);
            this.isConnected = false;
        };
        
        this.websocket.onerror = (error) => {
            console.error('❌ Error en WebSocket:', error);
        };
    }
    
    // Manejar mensajes del servidor
    handleMessage(message) {
        console.log('📨 Mensaje recibido:', message);
        
        switch (message.type) {
            case 'connection_established':
                console.log(`✅ Conexión establecida. Total preguntas: ${message.total_questions}`);
                if (this.onConnectionEstablished) {
                    this.onConnectionEstablished(message);
                }
                break;
                
            case 'session_created':
                this.sessionId = message.session_id;
                console.log(`🆕 Sesión creada: ${this.sessionId}`);
                if (this.onSessionCreated) {
                    this.onSessionCreated(message);
                }
                break;
                
            case 'progress_update':
                console.log(`⏳ Progreso: ${message.progress}% - ${message.status}`);
                if (this.onProgressUpdate) {
                    this.onProgressUpdate(message.progress, message.status);
                }
                break;
                
            case 'typing_indicator':
                console.log(`✍️ ${message.is_typing ? 'Escribiendo...' : 'Terminó de escribir'}`);
                if (this.onTypingIndicator) {
                    this.onTypingIndicator(message.is_typing);
                }
                break;
                
            case 'complete_response':
                console.log('✅ Respuesta completa recibida');
                if (this.onCompleteResponse) {
                    this.onCompleteResponse(message.data);
                }
                break;
                
            case 'brief_completed':
                console.log('🎉 Brief completado!');
                if (this.onBriefCompleted) {
                    this.onBriefCompleted(message);
                }
                break;
                
            case 'error':
                console.error(`❌ Error: ${message.error_code} - ${message.message}`);
                if (this.onError) {
                    this.onError(message.error_code, message.message);
                }
                break;
                
            case 'pong':
                console.log('🏓 Pong recibido');
                break;
                
            default:
                console.warn('⚠️ Tipo de mensaje desconocido:', message.type);
        }
    }
    
    // Enviar mensaje de chat
    sendMessage(message) {
        if (!this.isConnected) {
            console.error('❌ WebSocket no está conectado');
            return false;
        }
        
        const payload = {
            type: 'chat_message',
            message: message,
            session_id: this.sessionId
        };
        
        console.log('📤 Enviando mensaje:', payload);
        this.websocket.send(JSON.stringify(payload));
        return true;
    }
    
    // Enviar ping para mantener la conexión viva
    ping() {
        if (!this.isConnected) return false;
        
        this.websocket.send(JSON.stringify({ type: 'ping' }));
        return true;
    }
    
    // Desconectar
    disconnect() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
            this.isConnected = false;
        }
    }
}

// Ejemplo de uso completo con UI
class BriefChatUI {
    constructor(businessId, token) {
        this.client = new BriefWebSocketClient(businessId, token);
        this.setupEventHandlers();
        this.setupUI();
    }
    
    setupEventHandlers() {
        // Configurar todos los callbacks
        this.client.onConnectionEstablished = (data) => {
            this.updateStatus(`Conectado. ${data.total_questions} preguntas en total.`);
            this.showChatInterface();
        };
        
        this.client.onProgressUpdate = (progress, status) => {
            this.updateProgressBar(progress);
            this.updateStatus(status);
        };
        
        this.client.onTypingIndicator = (isTyping) => {
            this.showTypingIndicator(isTyping);
        };
        
        this.client.onCompleteResponse = (data) => {
            this.displayBotMessage(data.reply);
            this.hideProgressBar();
            
            // Mostrar sugerencias si las hay
            if (data.suggestion_answer) {
                this.showSuggestion(data.suggestion_answer, data.suggestion_response);
            }
            
            // Mostrar progreso de preguntas
            this.updateQuestionProgress(data.current_question_index, data.total_questions);
        };
        
        this.client.onError = (errorCode, message) => {
            this.displayError(`Error ${errorCode}: ${message}`);
        };
        
        this.client.onBriefCompleted = (data) => {
            this.displayCompletionMessage();
            this.showDownloadOptions();
        };
    }
    
    setupUI() {
        // HTML básico de la interfaz
        document.getElementById('chat-container').innerHTML = `
            <div id="status-bar">
                <div id="connection-status">Conectando...</div>
                <div id="progress-container" style="display:none;">
                    <div id="progress-bar"></div>
                    <div id="progress-text"></div>
                </div>
            </div>
            
            <div id="chat-messages"></div>
            
            <div id="typing-indicator" style="display:none;">
                <span>El asistente está escribiendo...</span>
            </div>
            
            <div id="suggestions-panel" style="display:none;">
                <h4>💡 Sugerencia:</h4>
                <p id="suggestion-text"></p>
                <button id="use-suggestion">Usar esta respuesta</button>
            </div>
            
            <div id="chat-input-container" style="display:none;">
                <input type="text" id="message-input" placeholder="Escribe tu respuesta...">
                <button id="send-button">Enviar</button>
            </div>
            
            <div id="question-progress">
                <span id="question-counter">Pregunta 0 de 0</span>
            </div>
        `;
        
        // Event listeners
        document.getElementById('send-button').onclick = () => this.sendMessage();
        document.getElementById('message-input').onkeypress = (e) => {
            if (e.key === 'Enter') this.sendMessage();
        };
        document.getElementById('use-suggestion').onclick = () => this.useSuggestion();
    }
    
    connect() {
        this.client.connect();
    }
    
    sendMessage() {
        const input = document.getElementById('message-input');
        const message = input.value.trim();
        
        if (!message) return;
        
        // Mostrar mensaje del usuario
        this.displayUserMessage(message);
        
        // Enviar al servidor
        this.client.sendMessage(message);
        
        // Limpiar input y mostrar progreso
        input.value = '';
        this.showProgressBar();
    }
    
    useSuggestion() {
        const suggestionText = document.getElementById('suggestion-text').textContent;
        document.getElementById('message-input').value = suggestionText;
        this.hideSuggestion();
    }
    
    // Métodos de UI
    updateStatus(status) {
        document.getElementById('connection-status').textContent = status;
    }
    
    showChatInterface() {
        document.getElementById('chat-input-container').style.display = 'block';
    }
    
    updateProgressBar(progress) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        
        progressBar.style.width = `${progress}%`;
        progressText.textContent = `${progress}%`;
    }
    
    showProgressBar() {
        document.getElementById('progress-container').style.display = 'block';
    }
    
    hideProgressBar() {
        document.getElementById('progress-container').style.display = 'none';
    }
    
    showTypingIndicator(show) {
        document.getElementById('typing-indicator').style.display = show ? 'block' : 'none';
    }
    
    displayUserMessage(message) {
        const messagesDiv = document.getElementById('chat-messages');
        messagesDiv.innerHTML += `
            <div class="user-message">
                <strong>Tú:</strong> ${message}
            </div>
        `;
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
    
    displayBotMessage(message) {
        const messagesDiv = document.getElementById('chat-messages');
        messagesDiv.innerHTML += `
            <div class="bot-message">
                <strong>Asistente:</strong> ${message.replace(/\n/g, '<br>')}
            </div>
        `;
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
    
    showSuggestion(suggestionAnswer, suggestionResponse) {
        const panel = document.getElementById('suggestions-panel');
        const text = document.getElementById('suggestion-text');
        
        text.textContent = suggestionResponse || suggestionAnswer;
        panel.style.display = 'block';
    }
    
    hideSuggestion() {
        document.getElementById('suggestions-panel').style.display = 'none';
    }
    
    updateQuestionProgress(current, total) {
        document.getElementById('question-counter').textContent = `Pregunta ${current + 1} de ${total}`;
    }
    
    displayError(error) {
        const messagesDiv = document.getElementById('chat-messages');
        messagesDiv.innerHTML += `
            <div class="error-message">
                ❌ ${error}
            </div>
        `;
    }
    
    displayCompletionMessage() {
        const messagesDiv = document.getElementById('chat-messages');
        messagesDiv.innerHTML += `
            <div class="completion-message">
                🎉 ¡Brief completado! Todas las preguntas han sido respondidas.
            </div>
        `;
    }
    
    showDownloadOptions() {
        // Mostrar opciones para descargar el reporte
        document.getElementById('chat-input-container').innerHTML = `
            <button onclick="downloadReport()">📄 Descargar Reporte</button>
            <button onclick="startNewBrief()">🔄 Nuevo Brief</button>
        `;
    }
}

// Inicializar la aplicación
document.addEventListener('DOMContentLoaded', () => {
    // Obtener businessId y token de la página o localStorage
    const businessId = 'your-business-id'; // Reemplazar con el ID real
    const token = localStorage.getItem('jwt_token'); // O de donde obtengas el token
    
    const briefChat = new BriefChatUI(businessId, token);
    briefChat.connect();
    
    // Mantener conexión viva con ping cada 30 segundos
    setInterval(() => {
        briefChat.client.ping();
    }, 30000);
});

// CSS básico para la interfaz
const styles = `
<style>
#chat-container {
    max-width: 800px;
    margin: 0 auto;
    font-family: Arial, sans-serif;
}

#status-bar {
    background: #f0f0f0;
    padding: 10px;
    border-radius: 5px;
    margin-bottom: 10px;
}

#progress-container {
    margin-top: 10px;
}

#progress-bar {
    height: 20px;
    background: #4CAF50;
    border-radius: 10px;
    transition: width 0.3s ease;
}

#chat-messages {
    height: 400px;
    overflow-y: auto;
    border: 1px solid #ddd;
    padding: 10px;
    margin-bottom: 10px;
    border-radius: 5px;
}

.user-message {
    text-align: right;
    margin-bottom: 10px;
    padding: 8px;
    background: #e3f2fd;
    border-radius: 5px;
}

.bot-message {
    text-align: left;
    margin-bottom: 10px;
    padding: 8px;
    background: #f5f5f5;
    border-radius: 5px;
}

.error-message {
    background: #ffebee;
    color: #c62828;
    padding: 8px;
    border-radius: 5px;
    margin-bottom: 10px;
}

.completion-message {
    background: #e8f5e8;
    color: #2e7d2e;
    padding: 15px;
    border-radius: 5px;
    margin-bottom: 10px;
    text-align: center;
    font-weight: bold;
}

#suggestions-panel {
    background: #fff3e0;
    border: 1px solid #ffcc02;
    padding: 15px;
    border-radius: 5px;
    margin-bottom: 10px;
}

#chat-input-container {
    display: flex;
    gap: 10px;
}

#message-input {
    flex: 1;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 5px;
}

button {
    padding: 10px 20px;
    background: #2196F3;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
}

button:hover {
    background: #1976D2;
}

#typing-indicator {
    font-style: italic;
    color: #666;
    padding: 5px;
}
</style>
`;

// Agregar estilos al documento
document.head.insertAdjacentHTML('beforeend', styles); 