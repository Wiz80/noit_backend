import os
import json
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from dotenv import load_dotenv
import aisuite as ai
from openai import OpenAI
from app.services.search.dynamic_research_ai import ResearchConfig, ResearchModule
from app.models.business.competitive_analysis.competitors import Competitor
import app.prompts.business.prompts_business_competitors as prompts
from app.db.session import SessionLocal
from sqlalchemy.orm import sessionmaker

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
    business_idea: str
    customer_persona: str
    industry: str

class EnhancedBusinessAnalyzer:
    """
    Enhanced business analysis system with integrated research capabilities
    
    Attributes:
        business_model: Parsed business model structure
        research_module: AI-powered research module
        lang: Analysis language (en/es)
    """
    
    def __init__(self, business_model: str, 
                       lang: str = 'es', 
                       validator_provider: str = 'deepseek', 
                       validator_model: str = "deepseek-reasoner",
                       max_depth: int = 3,
                       db: sessionmaker = SessionLocal):
        
        self.lang = lang
        self.validator_provider = validator_provider
        self.validator_model = validator_model

        if validator_provider == "openai" or validator_provider == "claude":
            self.llm = ai.Client()
        elif validator_provider == "deepseek":
            self.llm = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"),
                                           base_url="https://api.deepseek.com")
            
        self.business_model = business_model

        self.max_depth = max_depth

        self.db_session = db

        if self.lang == 'es':
            self.business_details = f"""
            Detalles del negocio:
            - Modelo de negocio: {json.dumps(self.business_model.business_idea, indent=2)}
            - Cliente : {json.dumps(self.business_model.customer_persona, indent=2)}
            - Industria: {json.dumps(self.business_model.industry, indent=2)}
            """
        else:
            self.business_details = f"""
            Business Details:
            - Business Model: {json.dumps(self.business_model.business_idea, indent=2)}
            - Customer Persona: {json.dumps(self.business_model.customer_persona, indent=2)}
            - Industry: {json.dumps(self.business_model.industry, indent=2)}
            """
            
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
            max_iterations=self.max_depth,
            temperature=0.7
        )
        logging.info(f"Initializing research module with max_iterations={self.max_depth}, language={self.lang}, validator={self.validator_provider}, model={self.validator_model}")
        return ResearchModule(config, model_validator=self.validator_provider)

    def generate_competitor_questions(self) -> List[str]:
        """Generate competitor analysis questions based on business model"""
        analysis_prompt = prompts.create_analysis_prompt(lang=self.lang, business_model=self.business_model)
        raw_questions = self._generate_raw_questions(analysis_prompt)
        return self._clean_questions(raw_questions)

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
        cleaning_prompt = prompts.create_cleaning_prompt(lang=self.lang, questions=raw_questions)
        
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

    async def research_competitors(self, prompt_search: str, business_id: str) -> List[CompetitorInfo]:
        """Execute competitor research with JSON formatting"""
        research_query = prompts.create_research_query(lang=self.lang,
                                                       business_details=self.business_details,
                                                       prompt_search=prompt_search)
        
        logging.info(f"Starting competitor research with max_depth={self.max_depth}")
        logging.info(f"Research query: {research_query[:200]}...")
        
        try:
            # Obtener respuesta cruda del módulo de investigación
            logging.info("Calling research module...")
            basic_competitors = await self.research_module.research(research_query)
            logging.info(f"Research module returned response of length: {len(basic_competitors)}")

            if not basic_competitors:
                logging.error("No competitors found in research")
                return []
            
            # Parse response with LLM to structured JSON
            logging.info("Parsing research response with LLM...")
            prompt_parsing = prompts.parse_json_with_llm(lang=self.lang,
                                                         raw_response=basic_competitors)
            
            try:
                basic_competitors = await self._parse_response_with_llm(prompt=prompt_parsing)
                logging.info(f"Parsed basic competitors: {basic_competitors}")
                
                # Enrich competitors with additional details
                logging.info("Enriching competitors with additional details...")
                enriched_competitors = await self._enrich_competitors(basic_competitors)
                
                # Final parsing to ensure proper structure
                logging.info("Final parsing of enriched competitors...")
                prompt_parsing = prompts.create_parsing_prompt_competitors(lang=self.lang,
                                                                           raw_response=enriched_competitors)
                
                # Parsear con LLM a JSON estructurado
                competitors = await self._parse_response_with_llm(prompt=prompt_parsing)
                
                # Save competitors to database
                logging.info("Saving competitors to database...")
                await self.save_competitors(competitors_data=competitors, 
                                            business_idea_id=business_id)
                
                return competitors.get('competitors', [])
            
            except Exception as e:
                logging.error(f"Error parsing or enriching competitors: {str(e)}")
                # Try to save basic competitors if available
                if isinstance(basic_competitors, dict) and 'competitors' in basic_competitors:
                    logging.info("Saving basic competitors to database...")
                    await self.save_competitors(competitors_data=basic_competitors, 
                                                business_idea_id=business_id)
                    return basic_competitors.get('competitors', [])
                return []
            
        except Exception as e:
            logging.error(f"Competitor research failed: {str(e)}")
            return []
        
        
    async def _parse_response_with_llm(self, prompt: str) -> List[CompetitorInfo]:
        """Usa LLM para convertir respuesta en JSON estructurado"""
    
        try:
            response = self.llm.chat.completions.create(
                model=self.validator_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            json_str = self._extract_json(response.choices[0].message.content)
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

    async def _enrich_competitors(self, basic_competitors: List[Dict]) -> List[Dict]:
        """Enrich basic competitor data with detailed information"""
        enriched_competitors = []
        
        for competitor in basic_competitors['competitors']:
            try:
                # Verify we have a full name to research
                if not competitor.get('full_name'):
                    logger.warning(f"Competidor sin nombre, omitiendo: {competitor}")
                    continue
                    
                # Investigar detalles del competidor
                detailed_info = await self._research_competitor_details(competitor)
                
                # Combinar información básica con detalles
                enriched_competitor = {
                    'full_name': competitor['full_name'],
                    'key_feature': competitor.get('key_feature', ''),
                    'similarity_score': competitor.get('similarity_score', 0.0),
                    **detailed_info}
                enriched_competitors.append(enriched_competitor)
                
                # Pequeña pausa para evitar limitaciones de API
                import asyncio
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error al enriquecer competidor {competitor.get('full_name')}: {str(e)}")
                # Agregar versión básica si falla el enriquecimiento
                enriched_competitors.append(competitor)
        
        return enriched_competitors

    async def _research_competitor_details(self, competitor: Dict) -> Dict:
        """Research detailed information about a competitor"""
        research_query = prompts.create_competitor_details_query(lang=self.lang,
                                                                 business_details=self.business_details,
                                                                 competitor=competitor)
        
        try:
            # Obtain raw response from research module
            raw_response = await self.research_module.research(research_query)
            
            prompt = prompts.parse_json_with_llm(lang=self.lang,
                                                 raw_response=raw_response)
            # Parsear con LLM a JSON estructurado
            return await self._parse_response_with_llm(prompt=prompt)
            
        except Exception as e:
            logger.error(f"Competitor details research failed for {competitor.get('full_name')}: {str(e)}")
            return {}

    async def save_competitors(self, competitors_data, business_idea_id):
        # List to store created competitors
        created_competitors = []
        
        for competitor_info in competitors_data['competitors']:
            # Create Competitor object
            competitor = Competitor(
                business_idea_id=business_idea_id,
                competitor_name=competitor_info["full_name"],
                key_feature=competitor_info.get("key_feature", ""),
                website=competitor_info.get("website", ""),
                instagram_url=competitor_info.get("instagram_url", ""),
                facebook_url=competitor_info.get("facebook_url", ""),
                linkedin_url=competitor_info.get("linkedin_url", ""),
                x_url=competitor_info.get("x_url", ""),
                youtube_url=competitor_info.get("youtube_url", ""),
                tiktok_url=competitor_info.get("tiktok_url", ""),
                similarity_score=competitor_info.get("similarity_score", 0.0)
            )
            
            # Add to session
            self.db_session.add(competitor)
            created_competitors.append(competitor)
        
        # Commit to store competitors at the same time
        await self.db_session.commit()
        
        return created_competitors