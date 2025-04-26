"""
Core business validation logic with multilingual support
"""
from typing import Dict, Any, Optional, List
import json
from abc import ABC, abstractmethod
from openai import OpenAI
import aisuite as ai
from app.services.search.dynamic_research_ai import ResearchModule
import os
from dotenv import load_dotenv

load_dotenv()

TRANSLATIONS = {
    "market_research": {
        "en": "Market Research and Validation",
        "es": "Investigación y Validación de Mercado"
    },
    "problem_question": {
        "en": "What specific customer problem does your business solve?",
        "es": "¿Qué problema específico del cliente resuelve tu negocio?"
    },
    "industry_analysis": {
        "en": "What industry does your business operate in? (Use official classification)",
        "es": "¿En qué industria opera tu negocio? (Usa clasificación oficial)"
    },
    "customer_persona": {
        "en": "Describe your ideal customer (demographics, behaviors, needs):",
        "es": "Describe tu cliente ideal (demografía, comportamientos, necesidades):"
    },
    "value_proposition": {
        "en": "What is your unique value proposition? (Why should customers choose you?)",
        "es": "¿Cuál es tu propuesta de valor única? (¿Por qué deberían elegirte los clientes?)"
    },
    "competitive_advantage": {
        "en": "What sets your business apart from competitors?",
        "es": "¿Qué te diferencia de los competidores?"
    },
    "key_resources": {
        "en": "What are the key resources required to deliver your value proposition?",
        "es": "¿Cuáles son los recursos clave necesarios para entregar tu propuesta de valor?"
    },
     "accept_prompt": {
        "en": "\nYour answer (Enter/Y/Yes to accept suggestion): ",
        "es": "\nTu respuesta (Enter/S/Sí para aceptar sugerencia): "
    },
    "validation_error": {
        "en": "Using suggested answer based on your input",
        "es": "Usando respuesta sugerida según tu entrada"
    },
}

class BaseModule(ABC):
    """Base module with bilingual support"""
    
    def __init__(self, config: 'ValidatorConfig'):
        self.config = config
        self.results = {"en": {}, "es": {}}
        self.doc_sections = {"en": [], "es": []}
        
    def get_translation(self, key: str) -> str:
        """Get translated text based on current language"""
        return TRANSLATIONS.get(key, {}).get(self.config.language, key)
    
    async def ask_question(self, question_key: str, needs_research: bool = False) -> str:
        """Improved question handling with JSON structure"""
        question = self.get_translation(question_key)
        
        # Generate structured suggestion
        suggestion_data = self.generate_suggestion(question)
        
        print(f"\n[QUESTION] {question}")
        
        if suggestion_data.get("features"):
            print("\n[KEY ASPECTS]")
            for i, aspect in enumerate(suggestion_data["features"], 1):
                print(f"{i}. {aspect}")
                
        if suggestion_data.get("suggestion"):
            print(f"\n[SUGGESTION] {suggestion_data['suggestion']}")
        
        # Get user input
        prompt = self.get_translation("accept_prompt")
        user_input = input(prompt).strip()
        
        # Validate response
        if await self.validate_response(user_input, suggestion_data.get("suggestion", "")):
            return suggestion_data["suggestion"]
        
        return user_input if user_input else suggestion_data["suggestion"]
    
    def generate_suggestion(self, question: str) -> dict:
        """Generate structured suggestions with JSON output"""
        system_prompt = {
            "en": f"""You're a business validation expert. Analyze this business idea: {self.config.business_idea}
            
            For the question: {question}
            
            Return JSON with:
            1. "features": 3 key aspects the user should consider (questions to guide their thinking)
            2. "suggestion": a model answer based on their business idea
            
            Format: {{"features": [str], "suggestion": str}}""",
            
            "es": f"""Eres un experto en validación de negocios. Analiza esta idea: {self.config.business_idea}
            
            Para la pregunta: {question}
            
            Devuelve JSON con:
            1. "features": 3 aspectos clave a considerar (preguntas guía)
            2. "suggestion": respuesta modelo basada en su idea
            
            Formato: {{"features": [str], "suggestion": str}}"""
        }[self.config.language]
        
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

class ValidatorConfig:
    """Configuration class with language support"""
    
    def __init__(self,
                 business_idea: str,  # Nuevo parámetro
                 perplexity_api_key: str,
                 validator_api_keys: Dict[str, str],
                 validator_provider: str = "deepseek",
                 validator_model: str = "deepseek-reasoner",
                 language: str = "en"):
        
        self.business_idea = business_idea
        self.perplexity_api_key = perplexity_api_key
        self.validator_api_keys = validator_api_keys
        self.validator_model = validator_model
        self.validator_provider = validator_provider
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

class MarketResearchModule(BaseModule):
    """Bilingual Market Research Module"""
    
    async def run(self):
        await self._add_section_header()
        await self._handle_customer_persona()
        await self._handle_problem_definition()
        await self._handle_industry_analysis()
        await self._handle_value_proposition()
        await self._handle_competitive_advantage()
        await self._handle_key_resources()
        return self.results
    
    async def _add_section_header(self):
        """Add translated section header"""
        en_header = "# Market Research and Validation\n"
        es_header = "# Investigación y Validación de Mercado\n"
        self.doc_sections["en"].append(en_header)
        self.doc_sections["es"].append(es_header)
    
    async def _handle_problem_definition(self):
        question_key = "problem_question"
        response = await self.ask_question(question_key, needs_research=False)
        await self._add_result("problem_definition", response)
    
    async def _handle_industry_analysis(self):
        question_key = "industry_analysis"
        response = await self.ask_question(question_key, needs_research=False)
        await self._add_result("industry", response)
    
    async def _handle_value_proposition(self):
        question_key = "value_proposition"
        response = await self.ask_question(question_key, needs_research=True)
        await self._add_result("value_proposition", response)
    
    async def _handle_customer_persona(self):
        question_key = "customer_persona"
        response = await self.ask_question(question_key=question_key, needs_research=False)
        await self._add_result("customer_persona", response)

    async def _handle_competitive_advantage(self):
        question_key = "competitive_advantage"
        response = await self.ask_question(question_key, needs_research=False)
        await self._add_result("competitive_advantage", response)

    async def _handle_key_resources(self):
        question_key = "key_resources"
        response = await self.ask_question(question_key, needs_research=False)
        await self._add_result("key_resources", response)
    
    async def _add_result(self, key: str, value: Any):
        """Store results in both languages"""
        self.results["en"][key] = value
        self.results["es"][key] = value
        
        # Add to documentation
        en_section = f"## {key.replace('_', ' ').title()}\n{value}\n"
        es_section = f"## {await self._translate_key(key)}\n{value}\n"
        self.doc_sections["en"].append(en_section)
        self.doc_sections["es"].append(es_section)
    
    async def _translate_key(self, key: str) -> str:
        """Simple key translation for section headers"""
        translations = {
            "problem_definition": "Definición del Problema",
            "industry": "Industria",
            "competitors": "Competidores",
            "customer_persona": "Persona del Cliente",
            "value_proposition": "Propuesta de Valor",
            "competitive_advantage": "Ventaja Competitiva",
            "key_metrics": "Métricas Clave",
            "key_resources": "Recursos Clave",
        }
        return translations.get(key, key)

class ValidationResults:
    def __init__(self, full_doc: Dict[str, list], json_output: Dict[str, Dict]):
        self.full_doc = {
            lang: "\n".join(docs) for lang, docs in full_doc.items()
        }
        self.json_output = json_output

class BusinessValidator:
    """Main validation pipeline with bilingual support"""
    
    def __init__(self, config: ValidatorConfig):
        self.config = config
        self.modules = [MarketResearchModule(config)]
        self.full_doc = {"en": [], "es": []}
        self.json_output = {"en": {}, "es": {}}
        
    async def run(self) -> ValidationResults:
        print("=== Business Idea Validation System ===")
        print(f"=== Language: {self.config.language.upper()} ===\n")
        
        for module in self.modules:
            module_name = module.__class__.__name__
            print(f"\n=== Running {module_name} ===")
            
            module_results = await module.run()
            await self._aggregate_results(module)
        
        return ValidationResults(
            full_doc=self.full_doc,
            json_output=self.json_output
        )
    
    async def _aggregate_results(self, module: BaseModule):
        """Aggregate results from modules"""
        for lang in ["en", "es"]:
            self.full_doc[lang].extend(module.doc_sections[lang])
            self.json_output[lang][module.__class__.__name__] = module.results[lang]
    
    async def _save_outputs(self):
        """Save bilingual outputs"""
        for lang in ["en", "es"]:
            # Save Markdown
            with open(f"output/business_validation_{lang}.md", "w") as f:
                f.write("\n".join(self.full_doc[lang]))
            
            # Save JSON
            with open(f"output/structured_data_{lang}.json", "w") as f:
                json.dump(self.json_output[lang], f, indent=2, ensure_ascii=False)