from abc import ABC, abstractmethod
import json
from typing import Dict, Any
from openai import OpenAI
from dataclasses import dataclass
from app.services.search.dynamic_research_ai import ResearchModule, ResearchConfig
import os
import aisuite as ai

@dataclass
class BaseValidatorConfig:
    """Base configuration class for validation modules"""
    def __init__(self,
                 business_idea: str,  # Nuevo parámetro
                 validator_api_keys: Dict[str, str],
                 validator_provider: str = "deepseek",
                 validator_model: str = "deepseek-reasoner",
                 language: str = "en"):
        
        self.business_idea = business_idea  
        self.validator_api_keys = validator_api_keys
        self.validator_provider = validator_provider
        self.validator_model = validator_model
        self.language = language
        self._init_clients()
            
    def _init_clients(self):
        """Initialize LLM clients"""
        if self.validator_provider in ["openai", "claude"]:
            self.validator_client = ai.Client()
        elif self.validator_provider == "deepseek":
            self.validator_client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
        else:
            raise ValueError("Invalid validator model specified")

class BaseBusinessModule(ABC):
    """Base class for all business analysis modules"""
    
    def __init__(self, config, TRANSLATIONS):
        self.config = config
        self.results = {"en": {}, "es": {}}
        self.doc_sections = {"en": [], "es": []}
        self.TRANSLATIONS = TRANSLATIONS

    def get_translation(self, key: str) -> str:
        """Get translated text based on current language"""
        return self.TRANSLATIONS.get(key, {}).get(self.config.language, key)

    def get_default_prompt(self, question: str) -> str:
        """Default prompt template if none provided"""
        return {
            "en": f"""Analyze this business idea: {self.config.business_idea}
            
            For the question: {question}
            
            Return JSON with:
            1. "features": 3 key aspects to consider
            2. "suggestion": a model answer based on the business idea
            
            Format: {{"features": [str], "suggestion": str}}""",
            
            "es": f"""Analiza esta idea de negocio: {self.config.business_idea}
            
            Para la pregunta: {question}
            
            Devuelve JSON con:
            1. "features": 3 aspectos clave a considerar
            2. "suggestion": una respuesta modelo basada en la idea
            
            Formato: {{"features": [str], "suggestion": str}}"""
        }[self.config.language]
        
    async def ask_question(self, question_key: str, prompt_template: str = None) -> str:
        """Enhanced question handling with specialized prompts"""
        question = self.get_translation(question_key)
        
        suggestion_data = self.generate_suggestion(
            question, 
            prompt_template or self.get_default_prompt(question)
        )
        
        print(f"\n[QUESTION] {question}")
        
        if suggestion_data.get("features"):
            print("\n[KEY ASPECTS]")
            for i, aspect in enumerate(suggestion_data["features"], 1):
                print(f"{i}. {aspect}")
                
        if suggestion_data.get("suggestion"):
            print(f"\n[SUGGESTION] {suggestion_data['suggestion']}")
        
        prompt = self.get_translation("accept_prompt")
        user_input = input(prompt).strip()
        
        if await self.validate_response(user_input, suggestion_data.get("suggestion", "")):
            return suggestion_data["suggestion"]
        
        return user_input if user_input else suggestion_data["suggestion"]
    
    def generate_suggestion(self, question: str, system_prompt: str) -> dict:
        """Generate structured suggestions with JSON output"""
        try:
            response = self.config.validator_client.chat.completions.create(
                model=self.config.validator_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error generating suggestion: {e}")
            return {"features": [], "suggestion": ""}

    async def validate_response(self, user_input: str, original_suggestion: str) -> bool:
        """Use LLM to validate if user accepted the suggestion"""
        validation_prompt = {
            "en": f"""Determine if this response indicates agreement with the suggestion:
            Suggestion: {original_suggestion}
            Response: {user_input}
            
            Return JSON format: {{"agreement": boolean}}""",
            
            "es": f"""Determina si esta respuesta indica acuerdo con la sugerencia:
            Sugerencia: {original_suggestion}
            Respuesta: {user_input}
            
            Devuelve formato JSON: {{"agreement": boolean}}"""
        }[self.config.language]
        
        try:
            response = self.config.validator_client.chat.completions.create(
                model=self.config.validator_model,
                messages=[{"role": "user", "content": validation_prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            validation = json.loads(response.choices[0].message.content)
            return validation.get("agreement", False)
        except:
            return user_input.strip().lower() in ["", "y", "yes", "sí", "si"]

    @abstractmethod
    async def run(self):
        """Must be implemented by child classes"""
        pass