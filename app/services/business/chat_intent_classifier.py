import os
import logging
import json
from typing import Dict, List, Optional, Any
from openai import OpenAI
import tiktoken

logger = logging.getLogger(__name__)

class ChatIntentClassifier:
    """
    Servicio para clasificar la intención del usuario en los mensajes de chat
    y determinar hacia qué flujo de conversación dirigir la interacción.
    """
    
    INTENT_TYPES = {
        "brief": "El usuario quiere hablar sobre el brief, crearlo o modificarlo",
        "business_canvas": "El usuario quiere hablar sobre el modelo de negocio, canvas o propuesta de valor",
        "competitive_analysis": "El usuario quiere realizar o consultar análisis de competidores",
        "general_question": "El usuario tiene una pregunta general sobre su negocio",
        "next_steps": "El usuario quiere saber qué pasos seguir o qué hacer a continuación",
        "feedback": "El usuario quiere feedback o insights sobre su progreso",
        "none": "No se puede determinar una intención clara"
    }
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Inicializa el clasificador de intenciones.
        
        Args:
            api_key: API key para OpenAI
            model: Modelo a utilizar para la clasificación
        """
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
    
    async def classify_intent(
        self, 
        message: str, 
        conversation_history: Optional[List[Dict[str, str]]] = None,
        completed_steps: Optional[List[str]] = None,
        next_step: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Clasifica la intención del mensaje del usuario.
        
        Args:
            message: Mensaje del usuario a clasificar
            conversation_history: Historial de la conversación (opcional)
            completed_steps: Pasos ya completados por el negocio (opcional)
            next_step: Siguiente paso recomendado según el progreso (opcional)
            
        Returns:
            Dict con la intención clasificada y información adicional
        """
        try:
            # Construir el prompt para el clasificador
            system_message = self._build_system_prompt(completed_steps, next_step)
            
            # Preparar historial de conversación
            messages = [{"role": "system", "content": system_message}]
            
            # Añadir historial si existe
            if conversation_history:
                # Limitar a las últimas 5 interacciones para mantener el contexto relevante
                # pero sin exceder límites de tokens
                for msg in conversation_history[-10:]:
                    messages.append(msg)
            
            # Añadir el mensaje actual del usuario
            messages.append({"role": "user", "content": message})
            
            # Enviar al modelo para clasificación
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # Baja temperatura para respuestas consistentes
                response_format={"type": "json_object"},
                max_tokens=250
            )
            
            # Extraer y validar la respuesta
            result = json.loads(response.choices[0].message.content)
            
            # Asegurar que la respuesta tenga la estructura esperada
            if "intent" not in result:
                result["intent"] = "none"
                result["confidence"] = 0.0
                result["explanation"] = "No se pudo determinar la intención"
            
            return result
            
        except Exception as e:
            logger.error(f"Error en la clasificación de intención: {str(e)}")
            return {
                "intent": "none",
                "confidence": 0.0,
                "explanation": f"Error en la clasificación: {str(e)}",
                "error": True
            }
    
    def _build_system_prompt(self, completed_steps: Optional[List[str]], next_step: Optional[str]) -> str:
        """Construye el prompt para el sistema de clasificación de intenciones"""
        
        intent_descriptions = "\n".join([f"- {intent}: {desc}" for intent, desc in self.INTENT_TYPES.items()])
        
        progress_context = ""
        if completed_steps is not None or next_step is not None:
            progress_context = "\n\nInformación de contexto del progreso del usuario:"
            
            if completed_steps is not None:
                if completed_steps:
                    progress_context += f"\n- Pasos completados: {', '.join(completed_steps)}"
                else:
                    progress_context += "\n- Pasos completados: Ninguno"
            
            if next_step is not None:
                progress_context += f"\n- Siguiente paso recomendado: {next_step}"
        
        return f"""Eres un asistente especializado en clasificar la intención de mensajes en un sistema de asistencia empresarial.
Tu trabajo es analizar el mensaje del usuario y determinar qué tipo de asistencia está buscando.

Los tipos de intenciones que debes clasificar son:
{intent_descriptions}
{progress_context}

Responde con un JSON que contenga los siguientes campos:
- intent: El tipo de intención identificada (usar exactamente uno de los valores listados arriba)
- confidence: Número entre 0 y 1 que indica la confianza en la clasificación
- explanation: Breve explicación de por qué se clasificó así
- recommended_action: Acción sugerida para manejar esta intención

Analiza cuidadosamente el contexto completo y la pregunta del usuario antes de responder.
""" 