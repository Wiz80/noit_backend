import gradio as gr
import os
import json
import logging
import random
from typing import Optional, List

# Librería para contar tokens
import tiktoken
from openai import OpenAI

# Configuración básica y de logging
logging.basicConfig(level=logging.INFO)

# -----------------------------------------------------------------------------
# Configuración del cliente y tokenización
# -----------------------------------------------------------------------------
# Intenta obtener la clave de API de las variables de entorno, si no la encuentra, usa la clave proporcionada directamente
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    # Usa la clave que vimos en el shell (solo para fines de desarrollo)
    api_key = "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"
    print(f"ADVERTENCIA: Usando clave API hardcodeada. Esto no es seguro para entornos de producción.")

client = OpenAI(api_key=api_key)
MAX_TOKENS_GPT4O = 8192  # Ajusta según el límite del modelo

def get_encoder():
    """
    Retorna un codificador apropiado para el modelo.
    Se intenta con "gpt-4" y se usa "gpt-3.5-turbo" como fallback.
    """
    try:
        return tiktoken.encoding_for_model("gpt-4")
    except KeyError:
        return tiktoken.encoding_for_model("gpt-3.5-turbo")

ENCODER = get_encoder()

def count_tokens(messages: List[dict]) -> int:
    """
    Calcula la cantidad aproximada de tokens usados por la lista de mensajes.
    Cada mensaje debe tener 'role' y 'content'.
    """
    total_tokens = 0
    for msg in messages:
        total_tokens += len(ENCODER.encode(msg.get("content", "")))
    return total_tokens

def log_token_usage(session, phase_name: str, messages: List[dict], response_msg: str):
    """
    Calcula y guarda en session.token_usage_temp el uso de tokens en request y response,
    mostrando el porcentaje respecto a MAX_TOKENS_GPT4O.
    """
    request_tokens = count_tokens(messages)
    req_percent = 100.0 * request_tokens / MAX_TOKENS_GPT4O
    req_str = f"[{phase_name}] Request tokens: {request_tokens}/{MAX_TOKENS_GPT4O} ({req_percent:.2f}%)"
    usage_lines = [req_str]

    if response_msg:
        assistant_message = [{"role": "assistant", "content": response_msg}]
        response_tokens = count_tokens(assistant_message)
        resp_percent = 100.0 * response_tokens / MAX_TOKENS_GPT4O
        resp_str = f"[{phase_name}] Response tokens: {response_tokens}/{MAX_TOKENS_GPT4O} ({resp_percent:.2f}%)"
        usage_lines.append(resp_str)

    session.token_usage_temp.extend(usage_lines)
    for line in usage_lines:
        logging.info(line)

# -----------------------------------------------------------------------------
# Definición de fases y preguntas (estructura del brief)
# -----------------------------------------------------------------------------
phases = {
    "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO": [
        "¿Qué hace la empresa? ¿Cuál es su propósito?",
        "¿Cuál es su propuesta de valor?",
        "¿Qué productos/servicios ofrece y a quiénes?",
        "¿Cuál es el cliente ideal?",
        "¿Qué problema resuelve?",
        "¿Qué los hace diferentes frente a la competencia?",
        "¿Qué desafíos u oportunidades clave enfrentan hoy?"
    ],
    "ETAPA 2: NECESIDAD / OPORTUNIDAD DE COMUNICACIÓN": [
        "¿Qué está ocurriendo alrededor del negocio o mercado que hace necesaria esta comunicación?",
        "¿Cuál es la oportunidad de negocio concreta?",
        "¿Qué objetivo tiene esta comunicación (posicionamiento, lanzamiento, awareness, conversión, etc.)?"
    ],
    "ETAPA 3: ESTRATEGIA DE COMUNICACIÓN": [
        "¿Cuál es la idea o mensaje clave a comunicar?",
        "¿A quién va dirigida esta comunicación?",
        "¿Qué valores o características tiene esta audiencia que deberíamos considerar?",
        "¿Por qué nos creerían?",
        "¿Qué hace nuestra promesa creíble?",
        "¿Cómo vamos a sonar (tono, voz, estilo)?",
        "¿Cuál es el indicador de éxito más importante?",
        "¿Qué cifras o resultados esperamos?",
        "¿Qué queremos que la audiencia piense, sienta o haga después de recibir esta comunicación?",
        "¿Hay limitaciones legales, presupuestarias o de formatos?",
        "¿Canales obligatorios o a evitar?",
        "¿Fechas clave?"
    ]
}

# -----------------------------------------------------------------------------
# Ejemplos canónicos para cada pregunta
# -----------------------------------------------------------------------------
QUESTION_EXAMPLES = {
    "¿Qué hace la empresa? ¿Cuál es su propósito?": [
        "Somos una startup de software que desarrolla soluciones de automatización para pymes. Nuestro propósito es simplificar procesos y permitir que las empresas se enfoquen en lo que mejor hacen.",
        "Somos una empresa de moda sostenible comprometida con la creación de prendas ecológicas y éticas, generando un impacto positivo en el medio ambiente."
    ],
    "¿Cuál es su propuesta de valor?": [
        "Ofrecemos asesoría integral y soporte 24/7 para garantizar soluciones a la medida, con atención personalizada.",
        "Proporcionamos productos de alta calidad a un precio competitivo, con innovación y excelente experiencia de cliente."
    ],
    # Agrega más ejemplos si es necesario
}

def generate_markdown(answers: dict) -> str:
    """Genera un reporte en Markdown a partir de las respuestas del brief, agrupando la información por fase."""
    md = ""
    for phase in phases.keys():
        md += f"## {phase}\n"
        phase_answers = answers.get(phase, {})
        for question in phases[phase]:
            answer = phase_answers.get(question, "Sin respuesta")
            md += f"- *{question}*: {answer}\n"
        md += "\n"
    return md

# -----------------------------------------------------------------------------
# Clase para manejar la sesión del brief (FSM) y el historial
# -----------------------------------------------------------------------------
class BriefSession:
    def __init__(self):
        self.phases = phases
        self.flat_questions = []
        self.build_flat_questions()
        self.current_index = 0
        self.answers = {}
        self.mode = "normal"  # "normal" o "correction"
        self.pending_correction: Optional[tuple] = None
        self.question_mapping = {i + 1: self.flat_questions[i] for i in range(len(self.flat_questions))}
        self.llm_history: List[dict] = []
        self.token_usage_temp: List[str] = []  # Para almacenar información de token usage

    def build_flat_questions(self):
        for phase, questions in self.phases.items():
            for q in questions:
                self.flat_questions.append((phase, q))

    def get_current_question(self) -> Optional[str]:
        if self.current_index < len(self.flat_questions):
            phase, question = self.flat_questions[self.current_index]
            return f"[{self.current_index + 1}] {phase} - {question}"
        else:
            return None

    def store_answer(self, answer: str):
        phase, question = self.flat_questions[self.current_index]
        if phase not in self.answers:
            self.answers[phase] = {}
        self.answers[phase][question] = answer

    def update_answer(self, phase: str, question: str, answer: str):
        if phase not in self.answers:
            self.answers[phase] = {}
        self.answers[phase][question] = answer

    def advance_question(self):
        self.current_index += 1

    def is_finished(self) -> bool:
        return self.current_index >= len(self.flat_questions)

# -----------------------------------------------------------------------------
# Funciones LLM (con logs de tokens) y mejores prompts
# -----------------------------------------------------------------------------
def get_local_example(question: str) -> str:
    examples_list = QUESTION_EXAMPLES.get(question, [])
    if not examples_list:
        return ""
    return random.choice(examples_list)

def generate_llm_explanation(question: str, local_example: str, history: List[dict], session: BriefSession) -> str:
    """
    Proporciona una aclaración profesional para la pregunta integrando el ejemplo local.
    Responde en un único párrafo, de forma natural y amigable.
    """
    if not local_example.strip():
        local_example = "No se dispone de un ejemplo local. Por favor, genera uno basado en buenas prácticas."

    system_msg = {
        "role": "system",
        "content": (
            "Eres un consultor senior en marketing y comunicación. Tu tarea es explicar de forma clara y profesional "
            "la siguiente pregunta, integrando el ejemplo local. Utiliza un tono natural y cercano, y sé conciso."
        )
    }
    user_msg = {
        "role": "user",
        "content": f"Pregunta: '{question}'\nEjemplo local: '{local_example}'"
    }
    messages = history + [system_msg, user_msg]
    log_token_usage(session, "generate_llm_explanation - BEFORE", messages, "")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,
            max_tokens=200
        )
        explanation = response.choices[0].message.content.strip()
        log_token_usage(session, "generate_llm_explanation - AFTER", messages, explanation)
        history.append({"role": "assistant", "content": f"[Aclaración interna]: {explanation}"})
        return explanation
    except Exception as e:
        logging.error(f"Error al generar explicación: {e}")
        return "No se pudo generar la aclaración en este momento."

def rewrite_text(text: str, history: List[dict], session: BriefSession) -> str:
    """
    Corrige y mejora la redacción del texto de forma natural y profesional.
    """
    system_msg = {
        "role": "system",
        "content": "Corrige y mejora la redacción del siguiente texto, manteniendo su significado original. Sé natural y profesional."
    }
    user_msg = {"role": "user", "content": f"Texto original: '{text}'"}
    messages = history + [system_msg, user_msg]
    log_token_usage(session, "rewrite_text - BEFORE", messages, "")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.3,
            max_tokens=150
        )
        rewritten = response.choices[0].message.content.strip()
        log_token_usage(session, "rewrite_text - AFTER", messages, rewritten)
        history.append({"role": "assistant", "content": f"[Reescritura interna]: {rewritten}"})
        return rewritten
    except Exception as e:
        logging.error(f"Error en reescritura: {e}")
        return text

def generate_llm_suggestion(history: List[dict], user_text: str, session: BriefSession) -> str:
    """
    Ofrece una recomendación o intuición breve en caso de respuesta incompleta.
    Utiliza un tono natural y amigable, y orienta al usuario basándose en el contexto previo.
    """
    system_msg = {
        "role": "system",
        "content": (
            "Eres un asesor creativo y empático. El usuario indica que aún no tiene claro su respuesta. "
            "Ofrece una recomendación o analogía breve que lo oriente, utilizando un tono natural y cercano."
        )
    }
    user_msg = {
        "role": "user",
        "content": f"El usuario dice: '{user_text}'. Por favor, ofrécele una recomendación breve y profesional que lo oriente."
    }
    messages = history + [system_msg, user_msg]
    log_token_usage(session, "generate_llm_suggestion - BEFORE", messages, "")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=200
        )
        suggestion = response.choices[0].message.content.strip()
        log_token_usage(session, "generate_llm_suggestion - AFTER", messages, suggestion)
        history.append({"role": "assistant", "content": f"[Sugerencia interna]: {suggestion}"})
        return suggestion
    except Exception as e:
        logging.error(f"Error al generar la sugerencia: {e}")
        return "No se pudo generar una sugerencia en este momento."

def classify_intent(message: str, history: List[dict], session: BriefSession) -> str:
    """
    Clasifica la intención del mensaje en una de estas etiquetas EXACTAS:
      - respuesta_valida
      - nonsense
      - pedir_aclaracion
      - corregir_respuesta
      - omitir
      - respuesta_incompleta
    Usa 'respuesta_incompleta' si el usuario indica no tener claro su respuesta.
    """
    system_msg = {
        "role": "system",
        "content": (
            "Eres un experto clasificador de intenciones para un agente de brief. Analiza cuidadosamente el mensaje actual en el contexto completo y responde SOLO con una de estas etiquetas EXACTAS (en minúsculas):\n"
            "- respuesta_valida\n- nonsense\n- pedir_aclaracion\n- corregir_respuesta\n- omitir\n- respuesta_incompleta\n\n"
            "Utiliza 'respuesta_incompleta' si el usuario expresa que no tiene claro su respuesta sin pedir que se omita o aclare."
        )
    }
    user_msg = {"role": "user", "content": f"Mensaje actual: '{message}'"}
    messages = history + [system_msg, user_msg]
    log_token_usage(session, "classify_intent - BEFORE", messages, "")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.0,
            max_tokens=10
        )
        intent = response.choices[0].message.content.strip().lower()
        log_token_usage(session, "classify_intent - AFTER", messages, intent)
        history.append({"role": "assistant", "content": f"[Clasificación interna]: {intent}"})
        logging.info(f"Intención clasificada: {intent}")
        return intent
    except Exception as e:
        logging.error(f"Error en clasificación de intención: {e}")
        lower_msg = message.lower()
        if any(x in lower_msg for x in ["no estoy seguro", "no lo sé", "no lo tengo claro", "no tengo idea", "aún no sé", "aun no sé"]):
            return "respuesta_incompleta"
        elif "aclara" in lower_msg or "ejemplo" in lower_msg:
            return "pedir_aclaracion"
        elif "correg" in lower_msg:
            return "corregir_respuesta"
        elif "omitir" in lower_msg:
            return "omitir"
        elif len(message.strip()) < 3:
            return "nonsense"
        else:
            return "respuesta_valida"

# -----------------------------------------------------------------------------
# Lógica principal del flujo en process_message
# -----------------------------------------------------------------------------
def process_message(session: BriefSession, message: str) -> str:
    if len(message.strip()) < 3:
        return "Tu mensaje es muy corto. Por favor, proporciona más detalles."

    # Modo corrección
    if session.mode == "correction":
        if session.pending_correction is None:
            try:
                q_num = int(message.strip())
                if q_num in session.question_mapping:
                    phase, question = session.question_mapping[q_num]
                    session.pending_correction = (phase, question)
                    return f"Modo corrección activado para la pregunta [{q_num}]: {phase} - {question}. Ingresa la nueva respuesta."
                else:
                    return "Número de pregunta inválido. Inténtalo de nuevo."
            except ValueError:
                return "Debes ingresar un número válido para identificar la pregunta a corregir."
        else:
            phase, question = session.pending_correction
            new_answer = rewrite_text(message, session.llm_history, session)
            session.update_answer(phase, question, new_answer)
            session.mode = "normal"
            session.pending_correction = None
            assistant_reply = f"Respuesta corregida para la pregunta: {question}\n\nContinuemos. {session.get_current_question() or ''}"
            session.llm_history.append({"role": "assistant", "content": assistant_reply})
            return assistant_reply

    # Modo normal: clasificar intención
    intent = classify_intent(message, session.llm_history, session)

    if intent == "respuesta_valida":
        corrected_answer = rewrite_text(message, session.llm_history, session)
        session.store_answer(corrected_answer)
        assistant_reply = f"Respuesta registrada (reescrita): \"{corrected_answer}\"."
        session.advance_question()
        if session.is_finished():
            md = generate_markdown(session.answers)
            assistant_reply += "\n\nBrief completado. Resumen final:\n" + md
        else:
            assistant_reply += "\n\nSiguiente pregunta: " + session.get_current_question()
        session.llm_history.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply

    elif intent == "nonsense":
        return "Tu respuesta no tiene sentido. Por favor, reescríbela de forma más clara o escribe 'omitir'."

    elif intent == "pedir_aclaracion":
        current_question_info = session.flat_questions[session.current_index]
        question_text = current_question_info[1]
        local_example = get_local_example(question_text)
        explanation = generate_llm_explanation(question_text, local_example, session.llm_history, session)
        return (
            f"Aquí tienes una aclaración/ejemplo para la pregunta:\n{session.get_current_question()}\n\n"
            f"{explanation}\n\nPor favor, ingresa tu respuesta cuando estés listo."
        )

    elif intent == "corregir_respuesta":
        session.mode = "correction"
        session.pending_correction = None
        return ("Modo corrección activado. Por favor, ingresa el número de la pregunta que deseas corregir, "
                "y luego la nueva respuesta en el siguiente mensaje.")

    elif intent == "omitir":
        session.store_answer("Omitida")
        assistant_reply = "Pregunta omitida."
        session.advance_question()
        if session.is_finished():
            md = generate_markdown(session.answers)
            assistant_reply += "\n\nBrief completado. Resumen final:\n" + md
        else:
            assistant_reply += "\n\nSiguiente pregunta: " + session.get_current_question()
        session.llm_history.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply

    elif intent == "respuesta_incompleta":
        corrected_user_text = rewrite_text(message, session.llm_history, session)
        suggestion = generate_llm_suggestion(session.llm_history, corrected_user_text, session)
        final_answer = (
            f"No tiene claro su respuesta, pero no omite.\n"
            f"*Respuesta del usuario*: \"{corrected_user_text}\"\n"
            f"*Sugerencia/Intuición*: {suggestion}"
        )
        session.store_answer(final_answer)
        session.advance_question()
        assistant_reply = "He registrado tu respuesta como 'incompleta' junto con una sugerencia.\n"
        if session.is_finished():
            md = generate_markdown(session.answers)
            assistant_reply += "\nBrief completado. Resumen final:\n" + md
        else:
            assistant_reply += "\nSiguiente pregunta: " + session.get_current_question()
        session.llm_history.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply

    else:
        return "No se pudo determinar la intención. Por favor, reescríbelo de forma clara."

# -----------------------------------------------------------------------------
# Función principal que integra el flujo completo de la conversación
# -----------------------------------------------------------------------------
def agent_reply(user_input: str, session: Optional[BriefSession]) -> (str, BriefSession):
    """
    Función principal invocada en cada interacción.
    Si no existe sesión, se crea una nueva.
    Se añade el historial para mantener el contexto y se informa al usuario del posible tiempo de respuesta.
    """
    if session is None:
        session = BriefSession()
        session.token_usage_temp = []
        session.llm_history.append({"role": "system", "content": "Inicio de la sesión de brief."})
        # Mensaje de bienvenida mejorado y natural, con indicación del tiempo (por ejemplo, 10-20 segundos por mensaje)
        welcome = (
            "¡Hola! Bienvenido al proceso de brief. Ten en cuenta que cada interacción puede tardar entre 10 y 20 segundos "
            "debido a las consultas al modelo GPT-4o. Por favor, sé paciente y disfruta del proceso.\n\n"
            "Iniciaremos con la siguiente pregunta:\n" + session.get_current_question()
        )
        session.llm_history.append({"role": "assistant", "content": welcome})
        reply = welcome
    else:
        session.token_usage_temp = []
        session.llm_history.append({"role": "user", "content": user_input})
        reply = process_message(session, user_input)
    return reply, session

# -----------------------------------------------------------------------------
# Interfaz con Gradio
# -----------------------------------------------------------------------------
with gr.Blocks() as demo:
    gr.Markdown("## Agente Conversacional para Brief (Contexto Completo + Uso de Tokens) - Modelo gpt-4o")
    chatbot = gr.Chatbot(label="Conversación", type="messages")
    state = gr.State(None)
    usage_info = gr.Markdown(label="Uso de Tokens (Request/Response)")

    with gr.Row():
        txt = gr.Textbox(
            show_label=False,
            placeholder="Escribe tu respuesta aquí y presiona Enter..."
        )
    
    def user_step(user_message, chat_history, session_state):
        reply, session_state = agent_reply(user_message, session_state)
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": reply})
        usage_text = "\n".join(session_state.token_usage_temp)
        if not usage_text:
            usage_text = "No se registró uso de tokens en esta interacción."
        return chat_history, session_state, usage_text

    txt.submit(
        fn=user_step,
        inputs=[txt, chatbot, state],
        outputs=[chatbot, state, usage_info]
    )

if __name__ == "__main__":
    try:
        demo.launch(server_name="127.0.0.1", server_port=7860, share=False, debug=True)
        print("La interfaz Gradio se ha lanzado en http://127.0.0.1:7860")
    except Exception as e:
        print(f"Error al lanzar Gradio: {e}")