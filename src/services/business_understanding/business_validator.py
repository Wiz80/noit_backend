"""
Core business validation logic with multilingual support
"""
from typing import Dict, Any, Optional, List
import json
from abc import ABC, abstractmethod
from openai import OpenAI
import aisuite as ai
from src.core.research_dynamic_ai import ResearchModule
import os
from dotenv import load_dotenv

TRANSLATIONS = {
    "market_research": {
        "en": "Market Research and Validation",
        "es": "Investigación y Validación de Mercado"
    },
    "problem_question": {
        "en": "What specific customer problem does your business solve?",
        "es": "¿Qué problema específico del cliente resuelve tu negocio?"
    },
}

class BaseModule(ABC):
    """Base module with bilingual support"""
    
    def __init__(self, config: 'ValidatorConfig'):
        self.config = config
        self.results = {"en": {}, "es": {}}
        self.doc_sections = {"en": [], "es": []}
        self.research_module = ResearchModule(config)
        
    def get_translation(self, key: str) -> str:
        """Get translated text based on current language"""
        return TRANSLATIONS.get(key, {}).get(self.config.language, key)
    
    async def ask_question(self, question_key: str, needs_research: bool = False) -> str:
        """Handle bilingual questioning"""
        base_question = TRANSLATIONS.get(question_key, {})
        question = base_question.get(self.config.language, question_key)
        
        # Generate suggestion in target language
        suggestion = self.generate_suggestion(question)
        
        # Display question and suggestion
        print(f"\n[QUESTION] {question}")
        if suggestion:
            print(f"[SUGGESTION] {suggestion}")
            
        # Add research if needed
        if needs_research:
            research = await self.research_module.research(question)
            print(f"[RESEARCH] {research[:200]}...")
            
        # Get user input
        response = input("Your answer: ").strip()
        return response or suggestion
    
    def generate_suggestion(self, question: str) -> str:
        """Generate answer suggestion using LLM in target language"""
        prompt = {
            "en": f"You're a business validation assistant. Help the user answer this question: {question}",
            "es": f"Eres un asistente de validación de negocios. Ayuda al usuario a responder: {question}"
        }[self.config.language]
        
        try:
            response = self.config.validator_client.chat.completions.create(
                model=self.config.validator_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating suggestion: {e}")
            return ""

class ValidatorConfig:
    """Configuration class with language support"""
    
    def __init__(self,
                 perplexity_api_key: str,
                 validator_api_keys: Dict[str, str],
                 validator_provider: str = "deepseek",
                 validator_model: str = "deepseek-reasoner",
                 language: str = "en"):
        
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
        await self._handle_problem_definition()
        await self._handle_industry_analysis()
        await self._handle_competitors()
        await self._handle_customer_persona()
        return self.results
    
    async def _add_section_header(self):
        """Add translated section header"""
        en_header = "# Market Research and Validation\n"
        es_header = "# Investigación y Validación de Mercado\n"
        self.doc_sections["en"].append(en_header)
        self.doc_sections["es"].append(es_header)
    
    async def _handle_problem_definition(self):
        question_key = "problem_question"
        response = await self.ask_question(question_key, needs_research=True)
        self._add_result("problem_definition", response)
    
    async def _handle_industry_analysis(self):
        question_en = "What industry does your business operate in? (Use official classification)"
        question_es = "¿En qué industria opera tu negocio? (Usa clasificación oficial)"
        response = await self.ask_question("industry_question", needs_research=True)
        self._add_result("industry", response)
    
    async def _handle_competitors(self):
        question_en = "List main competitors and their key characteristics:"
        question_es = "Lista los principales competidores y sus características clave:"
        response = await self.ask_question("competitors_question", needs_research=True)
        self._add_result("competitors", response)
    
    async def _handle_customer_persona(self):
        question_en = "Describe your ideal customer (demographics, behaviors, needs):"
        question_es = "Describe tu cliente ideal (demografía, comportamientos, necesidades):"
        response = await self.ask_question("persona_question")
        self._add_result("customer_persona", response)
    
    async def _add_result(self, key: str, value: Any):
        """Store results in both languages"""
        self.results["en"][key] = value
        self.results["es"][key] = value
        
        # Add to documentation
        en_section = f"## {key.replace('_', ' ').title()}\n{value}\n"
        es_section = f"## {self._translate_key(key)}\n{value}\n"
        self.doc_sections["en"].append(en_section)
        self.doc_sections["es"].append(es_section)
    
    async def _translate_key(self, key: str) -> str:
        """Simple key translation for section headers"""
        translations = {
            "problem_definition": "Definición del Problema",
            "industry": "Industria",
            "competitors": "Competidores",
            "customer_persona": "Persona del Cliente"
        }
        return translations.get(key, key)

class BusinessValidator:
    """Main validation pipeline with bilingual support"""
    
    def __init__(self, config: ValidatorConfig):
        self.config = config
        self.modules = [MarketResearchModule(config)]
        self.full_doc = {"en": [], "es": []}
        self.json_output = {"en": {}, "es": {}}
        
    def run(self):
        print("=== Business Idea Validation System ===")
        print(f"=== Language: {self.config.language.upper()} ===\n")
        
        for module in self.modules:
            module_name = module.__class__.__name__
            print(f"\n=== Running {module_name} ===")
            
            module_results = module.run()
            self._aggregate_results(module)
            
        self._save_outputs()
        print("\nValidation complete! Check outputs/ directory")
    
    def _aggregate_results(self, module: BaseModule):
        """Aggregate results from modules"""
        for lang in ["en", "es"]:
            self.full_doc[lang].extend(module.doc_sections[lang])
            self.json_output[lang][module.__class__.__name__] = module.results[lang]
    
    def _save_outputs(self):
        """Save bilingual outputs"""
        for lang in ["en", "es"]:
            # Save Markdown
            with open(f"outputs/business_validation_{lang}.md", "w") as f:
                f.write("\n".join(self.full_doc[lang]))
            
            # Save JSON
            with open(f"outputs/structured_data_{lang}.json", "w") as f:
                json.dump(self.json_output[lang], f, indent=2, ensure_ascii=False)