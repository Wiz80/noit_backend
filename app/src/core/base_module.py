from abc import ABC, abstractmethod
import json
from typing import Dict, Any
from openai import OpenAI

class BaseBusinessModule(ABC):
    """Base class for all business analysis modules"""
    
    def __init__(self, config):
        self.config = config
        self.results = {"en": {}, "es": {}}
        self.doc_sections = {"en": [], "es": []}
        
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

    @abstractmethod
    async def run(self):
        """Must be implemented by child classes"""
        pass