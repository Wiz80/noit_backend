import os
import json
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from dotenv import load_dotenv
import aisuite as ai
from openai import OpenAI
from src.core.research_dynamic_ai import ResearchConfig, ResearchModule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

@dataclass
class CompetitorInfo:
    """Data class to store competitor information"""
    name: str
    website: Optional[str]
    instagram: Optional[str]
    similarity_score: float

@dataclass
class BusinessModel:
    """Structured business model components"""
    ideal_customer: Dict[str, str]
    business_idea: Dict[str, str]
    industry: Dict[str, str]
    value_proposition: Dict[str, List[str]]
    key_metrics: Dict[str, float]
    competitive_advantage: List[str]

class EnhancedBusinessAnalyzer:
    """
    Enhanced business analysis system with integrated research capabilities
    
    Attributes:
        business_model: Parsed business model structure
        research_module: AI-powered research module
        lang: Analysis language (en/es)
    """
    
    def __init__(self, business_model_path: str, lang: str = 'es', validator_provider: str = 'deepseek', validator_model: str = "deepseek-reasoner"):
        self.lang = lang
        self.validator_provider = validator_provider
        self.validator_model = validator_model

        if validator_provider == "openai" or validator_provider == "claude":
            self.llm = ai.Client()
        elif validator_provider == "deepseek":
            self.llm = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"),
                                           base_url="https://api.deepseek.com")
            
        self.business_model = self._parse_business_model(business_model_path)
            
        self.research_module = self._init_research_module()
        
    def _init_research_module(self) -> ResearchModule:
        """Initialize the AI research module with proper configuration"""
        config = ResearchConfig(
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
            validator_api_keys={
                "deepseek": os.getenv("DEEPSEEK_API_KEY"),
                "openai": os.getenv("OPENAI_API_KEY"),
                "claude": os.getenv("CLAUDE_API_KEY")
            },
            validator_model=self.validator_model,
            language=self.lang,
            max_iterations=1,
            temperature=0.7
        )
        return ResearchModule(config, model_validator=self.validator_provider)

    def _parse_business_model(self, file_path: str) -> BusinessModel:
        """Parse structured business model from markdown file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract sections using LLM
        parsing_prompt = self._create_parsing_prompt(content)
        parsed_data = self._call_llm_parser(parsing_prompt)
        return BusinessModel(**json.loads(parsed_data))

    def _create_parsing_prompt(self, content: str) -> str:
        """Create prompt for business model extraction"""
        if self.lang == 'es':
            return f"""
            Extrae la información estructurada del modelo de negocio del siguiente texto en formato JSON.
            Campos requeridos:
            - ideal_customer (demografía, psicografía, comportamientos)
            - business_idea (descripción, propuesta_valor)
            - industry (sector, tendencias)
            - value_proposition (elementos_clave)
            - key_metrics (costos_iniciales, proyección_ventas)
            - competitive_advantage (ventajas)
            
            Texto: {content}
            """
        else:
            return f"""
            Extract structured business model information from the following text as JSON.
            Required fields:
            - ideal_customer (demographics, psychographics, behaviors)
            - business_idea (description, value_proposition)
            - industry (sector, trends)
            - value_proposition (key_elements)
            - key_metrics (initial_costs, sales_projection)
            - competitive_advantage (advantages)
            
            Text: {content}
            """

    def _call_llm_parser(self, prompt: str) -> str:
        """Execute LLM call for business model parsing"""
        try:
            response = self.llm.chat.completions.create(
                model=self.validator_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error(f"LLM parsing error: {str(e)}")
            raise

    def generate_competitor_questions(self) -> List[str]:
        """Generate competitor analysis questions based on business model"""
        analysis_prompt = self._create_analysis_prompt()
        raw_questions = self._generate_raw_questions(analysis_prompt)
        return self._clean_questions(raw_questions)

    def _create_analysis_prompt(self) -> str:
        """Create prompt for competitor question generation"""
        if self.lang == 'es':
            return f"""
            Eres un investigador doctoral (PhD) especializado en Marketing y Administración de Empresas.
            La tarea consiste en generar un conjunto de preguntas e indicaciones que guíen la
            elaboración de un “análisis de competencia”.

            Las preguntas las vas a hacer con el objetivo de evaluar a un competidor directo de la empresa

            Genera 15-20 preguntas de análisis competitivo basadas en el siguiente modelo de negocio.
            Requisitos:
            - Las preguntas deben poder responderse con información pública (sitios web, redes sociales)
            - Enfocarse en: posicionamiento de marca, estrategia de marketing, oferta de productos
            - Evitar preguntas que requieran datos financieros internos
            
            Modelo de negocio: {json.dumps(vars(self.business_model))}
            """
        else:
            return f"""
            Generate 15-20 competitive analysis questions based on this business model.
            Requirements:
            - Questions must be answerable through public information (websites, social media)
            - Focus on: brand positioning, marketing strategy, product offering
            - Avoid questions requiring internal financial data
            
            Business Model: {json.dumps(vars(self.business_model))}
            """

    def _generate_raw_questions(self, prompt: str) -> List[str]:
        """Generate initial questions using multiple LLMs"""
        models = ["openai:gpt-4o", "anthropic:claude-3-5-sonnet-20240620"]
        questions = []
        
        for model in models:
            try:
                response = ai.Client().chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5
                )
                questions.extend(response.choices[0].message.content.split('\n'))
            except Exception as e:
                logger.warning(f"Question generation failed with {model}: {str(e)}")
        
        return [q.strip() for q in questions if '?' in q]

    def _clean_questions(self, raw_questions: List[str]) -> List[str]:
        """Clean and deduplicate generated questions"""
        cleaning_prompt = self._create_cleaning_prompt(raw_questions)
        
        try:
            response = self.llm.chat.completions.create(
                model=self.validator_model,
                messages=[{"role": "user", "content": cleaning_prompt}],
                temperature=0.2
            )
            return [q.strip() for q in response.choices[0].message.content.split('\n') if q.strip()]
        except Exception as e:
            logger.error(f"Question cleaning failed: {str(e)}")
            return raw_questions[:15]

    def _create_cleaning_prompt(self, questions: List[str]) -> str:
        """Create prompt for question cleaning"""
        if self.lang == 'es':
            return f"""
            Limpia y organiza estas preguntas de análisis competitivo:
            1. Eliminar duplicados
            2. Asegurar que sean accionables con datos públicos
            3. Ordenar por importancia estratégica
            4. Limitar a máximo 15 preguntas
            
            Preguntas: {json.dumps(questions)}
            """
        else:
            return f"""
            Clean and organize these competitive analysis questions:
            1. Remove duplicates
            2. Ensure they're actionable with public data
            3. Sort by strategic importance
            4. Limit to 15 questions max
            
            Questions: {json.dumps(questions)}
            """

    async def research_competitors(self, prompt_search: str) -> List[CompetitorInfo]:
        """Execute competitor research with JSON formatting"""
        research_query = self._create_research_query(prompt_search)
        
        try:
            # Obtener respuesta cruda del módulo de investigación
            raw_response = await self.research_module.research(research_query)
            
            # Parsear con LLM a JSON estructurado
            return await self._parse_response_with_llm(raw_response)
            
        except Exception as e:
            logger.error(f"Competitor research failed: {str(e)}")
            return []
    
    def _create_research_query(self, prompt_search: str) -> str:
        """Crea el prompt de investigación manteniendo keys en inglés"""
        if self.lang == 'es':
            base_query = f"""
            {prompt_search}
            \n
            Detalles del negocio:
            - Objetivo: {json.dumps(self.business_model.ideal_customer, indent=2)}
            - Propuesta de valor: {json.dumps(self.business_model.value_proposition, indent=2)}
            - Ventajas competitivas: {json.dumps(self.business_model.competitive_advantage, indent=2)}
            """

            query = base_query + """
            \n
            Requisitos:
            1. Listar máximo 20 competidores
            2. Usar SIEMPRE keys en inglés
            3. Valores pueden ser en español
            4. Formato JSON:
            """
        else:
            base_query = f"""
            {prompt_search}
            \n
            Business Details:
            - Target: {json.dumps(self.business_model.ideal_customer, indent=2)}
            - Value Proposition: {json.dumps(self.business_model.value_proposition, indent=2)}
            - Competitive Advantages: {json.dumps(self.business_model.competitive_advantage, indent=2)}
            """

            query = base_query + """
            \n
            Requirements:
            1. List top 20 competitors
            2. Use English keys
            3. JSON Format:
            """
        
        return query + """
        \n
        {
            "competitors": [
                {
                "full_name": "string",
                "key_feature": "string",
                "website": "url",
                "instagram": "handle",
                "similarity_score": 1-100
                }
            ]
        }
        """
    
    def _create_parsing_prompt_competitors(self, raw_response: str) -> str:
        """Crea prompt para el parsing según idioma"""
        if self.lang == 'es':
            return f"""
            Convierte esta respuesta en un JSON válido:
            
            Requisitos:
            - Usar keys del español
            - Validar URLs
            - Asegurar scores entre 1-100
            
            Respuesta original:
            {raw_response}
            
            Formato requerido:
            {{
              "competitors": [
                {{
                  "full_name": "string",
                  "key_feature": "string",
                  "website": "url",
                  "instagram": "handle",
                  "similarity_score": number
                }}
              ]
            }}

            IMPORTANTE:
            - Devuelve ÚNICAMENTE el JSON sin comentarios
            - Asegura que similarity_score sea número
            - Valida que las URLs sean correctas
            - Asegurate que los keys del json estén en inglés
            
            """
        else:
            return f"""
            Convert this response into valid JSON:
            
            Requirements:
            - Use English keys
            - Validate URLs
            - Ensure scores 1-100
            
            Original response:
            {raw_response}
            
            Required format:
            {{
              "competitors": [
                {{
                  "full_name": "string",
                  "key_feature": "string",
                  "website": "url",
                  "instagram": "handle",
                  "similarity_score": number
                }}
              ]
            }}

            IMPORTANT:
            - Return ONLY the JSON without comments
            - Ensure that similarity_score is a number
            - Validate that the URLs are correct
            """
        
    async def _parse_response_with_llm(self, raw_response: str) -> List[CompetitorInfo]:
        """Usa LLM para convertir respuesta en JSON estructurado"""
        parsing_prompt = self._create_parsing_prompt_competitors(raw_response)
        
        try:
            response = self.llm.chat.completions.create(
                model=self.validator_model,
                messages=[{"role": "user", "content": parsing_prompt}],
                temperature=0.3
            )

            json_str = self._extract_json(response.choices[0].message.content)
        
            # return self._validate_competitors(json.loads(json_str))
            return json.loads(json_str)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {str(e)}")
            return []
    
    def _extract_json(self, raw_string: str) -> str:
        """Intenta extraer un JSON válido de la respuesta cruda"""
        try:
            # Buscar el primer { y último } válidos
            start = raw_string.index('{')
            end = raw_string.rindex('}') + 1
            return raw_string[start:end]
        except ValueError:
            logger.warning("JSON structure not found in response")
            return raw_string

    def _validate_competitors(self, json_data: dict) -> List[CompetitorInfo]:
        competitors = []
        
        # Validar estructura base
        if not isinstance(json_data.get('competitors', []), list):
            logger.error("Formato JSON inválido: falta lista 'competitors'")
            return []
        
        for entry in json_data['competitors']:
            try:
                # Validación completa de campos
                if not all(key in entry for key in ['full_name', 'key_feature', 'website', 'similarity_score']):
                    logger.warning(f"Entrada incompleta: {entry}")
                    continue

                score = min(100, max(0, float(entry['similarity_score']))) / 100
                
                competitors.append(CompetitorInfo(
                    name=str(entry['full_name']),
                    website=str(entry['website']),
                    instagram=str(entry.get('instagram', '')).strip('@'),
                    similarity_score=score,
                    key_feature=str(entry['key_feature'])
                ))
                
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Error validando entrada: {str(e)} - Data: {entry}")
                continue
                
        return competitors

def save_to_json(data: dict, filename: str):
    """Save analysis results to JSON file"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    return filename

async def main():
    """Example execution flow"""
    dir_ = os.getcwd()
    business_model_path = dir_ + "/src/services/business_understanding/business_model.md"
    analyzer = EnhancedBusinessAnalyzer(business_model_path, lang='es', validator_provider='claude', validator_model="anthropic:claude-3-5-sonnet-20240620")
    
    try:
        # Generate analysis questions
        logger.info("Generating competitor analysis questions...")
        questions = analyzer.generate_competitor_questions()
        save_to_json({"questions": questions}, "competitor_questions")
        
        #Research competitors

        prompt_search = """
        Identifica los principales competidores para un e-commerce de skincare masculino en Colombia que:
        - Se especializa en productos para tipos de piel específicos
        - Ofrece rutinas personalizadas
        - Tiene enfoque en educación sobre cuidado masculino
        """

        logger.info("Researching competitors...")
        competitors = await analyzer.research_competitors(prompt_search=prompt_search)
        save_to_json(competitors, "competitors")
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())