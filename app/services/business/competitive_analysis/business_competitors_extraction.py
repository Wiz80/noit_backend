import os
import json
import logging
import hashlib
import asyncio
import aiohttp
import uuid
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set, Tuple, Callable, Any
from dotenv import load_dotenv
from app.services.search.dynamic_research_ai import ResearchConfig, ResearchModule
from app.models.business.competitive_analysis.competitors import Competitor
import app.prompts.business.prompts_business_competitors as prompts
from app.db.session import SessionLocal
from sqlalchemy.orm import sessionmaker
import re
from functools import lru_cache
import threading

# LangChain imports
from langchain_core.messages import HumanMessage
from app.services.llm import create_llm_client, read_api_key_from_env_file

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
    """Structured business model components - matches database schema"""
    business_idea: str
    customer_persona: str
    industry: str
    problem_definition: Optional[str] = None
    value_proposition: Optional[str] = None
    competitive_advantage: Optional[str] = None
    products_services: Optional[str] = None
    challenges_opportunities: Optional[str] = None
    
    def get_comprehensive_description(self) -> str:
        """Generate a comprehensive description using all available fields"""
        sections = []
        
        if self.business_idea:
            sections.append(f"IDEA DE NEGOCIO:\n{self.business_idea}")
        
        if self.problem_definition:
            sections.append(f"PROBLEMA QUE RESUELVE:\n{self.problem_definition}")
        
        if self.customer_persona:
            sections.append(f"CLIENTE OBJETIVO:\n{self.customer_persona}")
        
        if self.value_proposition:
            sections.append(f"PROPUESTA DE VALOR:\n{self.value_proposition}")
        
        if self.products_services:
            sections.append(f"PRODUCTOS/SERVICIOS:\n{self.products_services}")
        
        if self.competitive_advantage:
            sections.append(f"VENTAJA COMPETITIVA:\n{self.competitive_advantage}")
        
        if self.challenges_opportunities:
            sections.append(f"DESAFÍOS Y OPORTUNIDADES:\n{self.challenges_opportunities}")
        
        if self.industry:
            sections.append(f"INDUSTRIA:\n{self.industry}")
        
        return "\n\n".join(sections)
    
    def get_key_elements_for_research(self) -> Dict[str, str]:
        """Extract key elements for competitor research"""
        return {
            "industry": self.industry or "",
            "problem": self.problem_definition or "",
            "value_proposition": self.value_proposition or "",
            "target_customer": self.customer_persona or "",
            "products_services": self.products_services or "",
            "competitive_advantage": self.competitive_advantage or ""
        }

@dataclass
class WebhookConfig:
    """Configuración para el webhook de callback"""
    url: str
    headers: Optional[Dict[str, str]] = None
    include_request_id: bool = True
    timeout: int = 60

@dataclass
class ResearchStatus:
    """Estado actual de la investigación"""
    request_id: str
    status: str  # "pending", "completed", "error"
    business_id: str
    results: Optional[List[Dict]] = None
    error_message: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)

class EnhancedBusinessAnalyzer:
    """
    Enhanced business analysis system with integrated research capabilities
    
    Attributes:
        business_model: Parsed business model structure
        research_module: AI-powered research module
        lang: Analysis language (en/es)
    """
    
    # Cache para almacenar preguntas por tipo de industria y idioma
    _question_cache = {}
    
    # Registro de investigaciones en curso
    _active_researches = {}
    
    def __init__(self, business_model: str, 
                       lang: str = 'es', 
                       validator_provider: str = 'anthropic', 
                       validator_model: str = "claude-3-5-sonnet-20241022",
                       max_depth: int = 3,
                       research_model: str = "sonar-deep-research",
                       db: sessionmaker = SessionLocal):
        
        self.lang = lang
        self.validator_provider = validator_provider
        self.validator_model = validator_model
        self.research_model = research_model

        # Initialize LLM using LangChain
        try:
            self.llm = create_llm_client(
                provider=validator_provider,
                model=validator_model,
                temperature=0.3
            )
            logging.info(f"LLM initialized with provider: {validator_provider}, model: {validator_model}")
        except Exception as e:
            logging.error(f"Error initializing LLM: {str(e)}")
            # Fallback to default anthropic model
            try:
                self.llm = create_llm_client(
                    provider="anthropic",
                    model="claude-3-5-sonnet-20241022",
                    temperature=0.3,
                    max_tokens=20000
                )
                logging.info("Fallback to default Claude model successful")
            except Exception as fallback_error:
                logging.error(f"Fallback failed: {str(fallback_error)}")
                raise ValueError(f"Could not initialize any LLM: {fallback_error}")
            
        self.business_model = business_model
        self.max_depth = max_depth

        # Create a session from the session factory if it's a sessionmaker
        if callable(db):
            self.db_session = db()
        else:
            self.db_session = db

        if self.lang == 'es':
            self.business_details = f"""
            Detalles del negocio:
            {self.business_model.get_comprehensive_description()}
            """
        else:
            self.business_details = f"""
            Business Details:
            {self.business_model.get_comprehensive_description()}
            """
            
        self.research_module = self._init_research_module()
        
    def _init_research_module(self) -> ResearchModule:
        """Initialize the AI research module with proper configuration"""
        # Leer las API keys directamente del archivo .env
        config = ResearchConfig(
            model=self.research_model,
            language=self.lang,
            max_iterations=self.max_depth
        )
        logging.info(f"Initializing research module with max_iterations={self.max_depth}, language={self.lang}, validator={self.validator_provider}, model={self.research_model}")
        return ResearchModule(config)

    def _generate_cache_key(self) -> str:
        """Genera una clave única para cachear resultados basada en la industria y el idioma"""
        industry = str(self.business_model.industry).lower()
        return f"{self.lang}_{hashlib.md5(industry.encode()).hexdigest()}"
        
    def generate_competitor_questions(self) -> List[str]:
        """
        Generate competitor analysis questions based on business model
        Optimizado para utilizar caché y reducir llamadas a la API
        Usa siempre Deepseek con modelo deepseek-reasoner para generar preguntas
        """
        # Crear clave de caché basada en industria e idioma
        cache_key = self._generate_cache_key()
        
        # Verificar si ya tenemos preguntas en caché para esta industria/idioma
        if cache_key in self._question_cache:
            logger.info(f"Using cached questions for industry: {self.business_model.industry}")
            cached_questions = self._question_cache[cache_key]
            
            # Personalizar algunas preguntas con el modelo de negocio específico
            personalized_questions = self._personalize_cached_questions(cached_questions)
            return personalized_questions
        
        # Si no hay caché, generar preguntas con una sola llamada a la API
        analysis_prompt = prompts.create_analysis_prompt(lang=self.lang, business_model=self.business_model)
        
        # Modificar el prompt para recibir preguntas estructuradas y sin duplicados en una sola llamada
        structured_prompt = f"""
        {analysis_prompt}
        
        INSTRUCCIONES IMPORTANTES:
        1. Genera al menos 10 preguntas específicas y relevantes para realizar un análisis competitivo.
        2. Las preguntas deben estar numeradas con formato "1. Pregunta...?"
        3. Evita cualquier duplicación o redundancia.
        4. Las preguntas deben ser directas y específicas.
        5. Asegúrate que cada pregunta termine con signo de interrogación.
        
        Por favor, proporciona ÚNICAMENTE la lista numerada de preguntas, sin texto adicional.
        """
        
        try:
            # Usar el LLM configurado (por defecto Claude)
            logger.info(f"Generando preguntas con {self.validator_provider} usando modelo {self.validator_model}")
            
            # Crear mensaje usando LangChain
            message = HumanMessage(content=structured_prompt)
            response = self.llm.invoke([message])
            content = response.content
                
            # Procesar las preguntas sin llamadas adicionales a la API
            questions = self._process_questions_locally(content)
            
            # Guardar en caché para futuras consultas
            if questions:
                self._question_cache[cache_key] = questions
                logger.info(f"Cached {len(questions)} questions for industry: {self.business_model.industry}")
            
            return questions
            
        except Exception as e:
            logger.error(f"Error generating competitor questions with {self.validator_provider}: {str(e)}")
            # Intentar con fallback usando el LLM configurado
            try:
                if hasattr(self, 'llm') and self.llm:
                    logger.info("Intentando generar preguntas con fallback")
                    message = HumanMessage(content=structured_prompt)
                    response = self.llm.invoke([message])
                    content = response.content
                    questions = self._process_questions_locally(content)
                    
                    if questions:
                        self._question_cache[cache_key] = questions
                        return questions
            except Exception as fallback_error:
                logger.error(f"Error en fallback para generar preguntas: {str(fallback_error)}")
            
            # Si todo falla, retornar preguntas predeterminadas
            return self._get_default_questions()
    
    def _process_questions_locally(self, raw_content: str) -> List[str]:
        """Procesa y limpia las preguntas sin llamadas adicionales a la API"""
        # Extraer preguntas usando expresiones regulares
        # Busca líneas que comiencen con números o - y terminen con ?
        pattern = r'(?:\d+\.|-)\s*([^.?]*\?)'
        matches = re.findall(pattern, raw_content)
        
        # Limpiar y filtrar resultados
        questions = []
        seen = set()  # Para eliminar duplicados
        
        for q in matches:
            clean_q = q.strip()
            # Normalizar para comparación (minúsculas, sin puntuación excesiva)
            norm_q = re.sub(r'\s+', ' ', clean_q.lower())
            
            # Verificar si la pregunta tiene sentido y no es duplicada
            if (clean_q and 
                '?' in clean_q and 
                len(clean_q) > 15 and 
                norm_q not in seen):
                questions.append(clean_q)
                seen.add(norm_q)
        
        # Si no se encontraron suficientes preguntas, intentar con un patrón más general
        if len(questions) < 5:
            general_pattern = r'([^.?]*\?)'
            general_matches = re.findall(general_pattern, raw_content)
            
            for q in general_matches:
                clean_q = q.strip()
                norm_q = re.sub(r'\s+', ' ', clean_q.lower())
                
                if (clean_q and 
                    len(clean_q) > 15 and 
                    norm_q not in seen):
                    questions.append(clean_q)
                    seen.add(norm_q)
        
        return questions[:15]  # Limitar a 15 preguntas máximo
        
    def _personalize_cached_questions(self, cached_questions: List[str]) -> List[str]:
        """Personaliza algunas preguntas cacheadas con el modelo de negocio específico"""
        # Extraer elementos clave del modelo de negocio
        business_name = ""
        try:
            if isinstance(self.business_model.business_idea, dict):
                business_name = self.business_model.business_idea.get('name', '')
            elif isinstance(self.business_model.business_idea, str):
                # Intentar extraer algún nombre de negocio de la descripción
                if len(self.business_model.business_idea) > 10:
                    business_name = self.business_model.business_idea.split()[0:3]
                    business_name = " ".join(business_name)
        except:
            pass
        
        # Si no hay información específica para personalizar, devolver las preguntas como están
        if not business_name:
            return cached_questions
            
        # Personalizar algunas preguntas (no todas, para mantener variedad)
        personalized = []
        for i, question in enumerate(cached_questions):
            if i % 3 == 0 and business_name:  # Personalizar cada tercera pregunta
                if self.lang == 'es':
                    question = question.replace("la empresa", f"{business_name}")
                    question = question.replace("el negocio", f"{business_name}")
                else:
                    question = question.replace("the business", f"{business_name}")
                    question = question.replace("the company", f"{business_name}")
            personalized.append(question)
            
        return personalized
        
    def _get_default_questions(self) -> List[str]:
        """Proporciona preguntas predeterminadas en caso de fallo"""
        if self.lang == 'es':
            return [
                "¿Quiénes son los principales competidores en este mercado?",
                "¿Qué características diferenciadoras tienen los competidores?",
                "¿Cuál es la estrategia de precios de la competencia?",
                "¿Qué canales de distribución utilizan los competidores?",
                "¿Cómo se posicionan los competidores en redes sociales?",
                "¿Cuáles son las fortalezas y debilidades de la competencia?",
                "¿Qué segmentos de mercado atienden los competidores?",
                "¿Qué tecnologías o innovaciones utilizan los competidores?",
                "¿Cómo es la experiencia de usuario que ofrecen los competidores?",
                "¿Cuál es la reputación y percepción de marca de los competidores?"
            ]
        else:
            return [
                "Who are the main competitors in this market?",
                "What differentiating features do competitors have?",
                "What is the pricing strategy of the competition?",
                "What distribution channels do competitors use?",
                "How do competitors position themselves on social media?",
                "What are the strengths and weaknesses of the competition?",
                "What market segments do competitors serve?",
                "What technologies or innovations do competitors use?",
                "How is the user experience offered by competitors?",
                "What is the reputation and brand perception of competitors?"
            ]

    def _generate_raw_questions(self, prompt: str) -> List[str]:
        """
        DEPRECATED: Este método ya no se utiliza, se mantiene por compatibilidad
        Se reemplaza con una implementación más eficiente en generate_competitor_questions
        """
        logger.warning("_generate_raw_questions is deprecated, using optimized implementation instead")
        return self.generate_competitor_questions()

    def _clean_questions(self, raw_questions: List[str]) -> List[str]:
        """
        DEPRECATED: Este método ya no se utiliza, se mantiene por compatibilidad
        La limpieza de preguntas ahora se realiza localmente sin llamadas a la API
        """
        logger.warning("_clean_questions is deprecated, using optimized implementation instead")
        return self._process_questions_locally("\n".join(raw_questions))

    # ==================== MÉTODOS ASINCRÓNICOS PARA INVESTIGACIÓN DE COMPETIDORES ====================
    
    def start_competitor_research(self, prompt_search: str, business_id: str, webhook_config: WebhookConfig) -> str:
        """
        Inicia la investigación de competidores de forma asincrónica y retorna inmediatamente
        
        Args:
            prompt_search: Búsqueda para la investigación
            business_id: ID del negocio
            webhook_config: Configuración del webhook para recibir la respuesta
            
        Returns:
            request_id: ID único de la solicitud para seguimiento
        """
        # Generar ID único para esta solicitud
        request_id = str(uuid.uuid4())
        
        # Registrar la investigación como en curso
        research_status = ResearchStatus(
            request_id=request_id,
            status="pending",
            business_id=business_id
        )
        
        self._active_researches[request_id] = research_status
        
        # Iniciar investigación en un hilo separado
        threading.Thread(
            target=self._run_async_research,
            args=(request_id, prompt_search, business_id, webhook_config),
            daemon=True
        ).start()
        
        logger.info(f"Investigación iniciada con ID: {request_id}")
        return request_id
    
    def _run_async_research(self, request_id: str, prompt_search: str, business_id: str, webhook_config: WebhookConfig):
        """Ejecuta la investigación en un hilo separado y envía los resultados al webhook"""
        # Crear un nuevo event loop para este hilo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Ejecutar la investigación de forma asincrónica
            results = loop.run_until_complete(
                self._execute_research(prompt_search, business_id)
            )
            
            # Actualizar el estado de la investigación
            if request_id in self._active_researches:
                self._active_researches[request_id].status = "completed"
                self._active_researches[request_id].results = results
                
                # Convertir resultados a formato para webhook
                webhook_payload = {
                    "status": "completed",
                    "business_id": business_id,
                    "competitors": results
                }
                
                if webhook_config.include_request_id:
                    webhook_payload["request_id"] = request_id
                
                # Enviar resultados al webhook
                loop.run_until_complete(
                    self._send_webhook_notification(webhook_config, webhook_payload)
                )
                
        except Exception as e:
            logger.error(f"Error en investigación asincrónica {request_id}: {str(e)}")
            
            # Actualizar estado con error
            if request_id in self._active_researches:
                self._active_researches[request_id].status = "error"
                self._active_researches[request_id].error_message = str(e)
                
                # Notificar error al webhook
                error_payload = {
                    "status": "error",
                    "business_id": business_id,
                    "error": str(e)
                }
                
                if webhook_config.include_request_id:
                    error_payload["request_id"] = request_id
                
                try:
                    loop.run_until_complete(
                        self._send_webhook_notification(webhook_config, error_payload)
                    )
                except Exception as webhook_error:
                    logger.error(f"Error enviando notificación de error al webhook: {str(webhook_error)}")
        
        finally:
            # Cerrar el loop
            loop.close()
    
    async def _send_webhook_notification(self, webhook_config: WebhookConfig, payload: Dict):
        """Envía una notificación al webhook configurado"""
        headers = webhook_config.headers or {"Content-Type": "application/json"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_config.url,
                    json=payload,
                    headers=headers,
                    timeout=webhook_config.timeout
                ) as response:
                    if response.status < 200 or response.status >= 300:
                        response_text = await response.text()
                        logger.error(f"Error en webhook ({response.status}): {response_text}")
                    else:
                        logger.info(f"Notificación de webhook enviada exitosamente: {webhook_config.url}")
        except Exception as e:
            logger.error(f"Error enviando notificación webhook: {str(e)}")
    
    def get_research_status(self, request_id: str) -> Optional[Dict]:
        """
        Obtiene el estado actual de una investigación
        
        Args:
            request_id: ID de la solicitud de investigación
            
        Returns:
            Estado actual de la investigación o None si no se encuentra
        """
        if request_id in self._active_researches:
            return self._active_researches[request_id].to_dict()
        return None
    
    async def _execute_research(self, prompt_search: str, business_id: str) -> List[Dict]:
        """Ejecuta la investigación de competidores de forma asincrónica"""
        research_query = prompts.create_research_query(
            lang=self.lang,
            business_details=self.business_details,
            prompt_search=prompt_search
        )
        
        logging.info(f"Starting competitor research with max_depth={self.max_depth}")
        logging.info(f"Research query: {research_query[:200]}...")
        
        # Realizar una única llamada al módulo de investigación para obtener todos los datos necesarios
        logging.info("Calling research module for comprehensive competitor data...")
        raw_response = await self.research_module.research(research_query)
        logging.info(f"Research module returned response of length: {len(raw_response)}")

        if not raw_response:
            logging.error("No competitors found in research")
            return []
        
        # Parse response with LLM to structured JSON
        logging.info("Parsing research response with LLM...")
        prompt_parsing = prompts.create_parsing_prompt_competitors(
            lang=self.lang,
            raw_response=raw_response
        )
        
        # Parsear con LLM a JSON estructurado final
        competitors_data = await self._parse_response_with_llm(prompt=prompt_parsing)
        logging.info(f"Parsed competitors data: {competitors_data}")
        
        # Save competitors to database
        logging.info("Saving competitors to database...")
        created_competitors = self.save_competitors(
            competitors_data=competitors_data, 
            business_idea_id=business_id
        )
        
        # Convertir objetos Competitor a diccionarios para la respuesta
        competitor_dicts = []
        for competitor in created_competitors:
            competitor_dict = {
                "id": str(competitor.id),
                "competitor_name": competitor.competitor_name,
                "key_feature": competitor.key_feature,
                "website": competitor.website,
                "instagram_url": competitor.instagram_url,
                "facebook_url": competitor.facebook_url,
                "linkedin_url": competitor.linkedin_url,
                "x_url": competitor.x_url,
                "youtube_url": competitor.youtube_url,
                "tiktok_url": competitor.tiktok_url,
                "similarity_score": float(competitor.similarity_score)
            }
            competitor_dicts.append(competitor_dict)
        
        return competitor_dicts
            
    async def research_competitors(self, prompt_search: str, business_id: str) -> List[CompetitorInfo]:
        """
        Execute competitor research with a single API call to get comprehensive data
        (Método original, mantenido para compatibilidad)
        """
        research_query = prompts.create_research_query(lang=self.lang,
                                                       business_details=self.business_details,
                                                       prompt_search=prompt_search)
        
        logging.info(f"Starting competitor research with max_depth={self.max_depth}")
        logging.info(f"Research query: {research_query[:200]}...")
        logging.info(f"Using research model: {self.research_model}")
        
        try:
            # Realizar una única llamada al módulo de investigación para obtener todos los datos necesarios
            logging.info("Calling research module for comprehensive competitor data...")
            raw_response = await self.research_module.research(research_query)
            logging.info(f"Research module returned response of length: {len(raw_response)}")

            if not raw_response:
                logging.error("No competitors found in research")
                return []
            
            # Parse response with LLM to structured JSON
            logging.info("Parsing research response with LLM...")
            prompt_parsing = prompts.create_parsing_prompt_competitors(lang=self.lang,
                                                                       raw_response=raw_response)
            
            try:
                # Parsear con LLM a JSON estructurado final
                competitors_data = await self._parse_response_with_llm(prompt=prompt_parsing)
                logging.info(f"Parsed competitors data: {competitors_data}")
                
                # Save competitors to database
                logging.info("Saving competitors to database...")
                self.save_competitors(competitors_data=competitors_data, 
                                      business_idea_id=business_id)
                
                return competitors_data.get('competitors', [])
            
            except Exception as e:
                logging.error(f"Error parsing competitors: {str(e)}")
                return []
            
        except Exception as e:
            logging.error(f"Competitor research failed: {str(e)}")
            
            # Proporcionar mensaje de error más detallado basado en el tipo de error
            if "timeout" in str(e).lower():
                logging.error("La solicitud de investigación se agotó. Intenta configurar un timeout más largo con la variable N8N_WEBHOOK_TIMEOUT")
                logging.error("Por ejemplo, añade al archivo .env: N8N_WEBHOOK_TIMEOUT=120")
            elif "connection" in str(e).lower():
                logging.error("Error de conexión al servidor n8n. Verifica que el servidor esté accesible.")
            
            # Devolver una estructura vacía en lugar de fallar completamente
            return []

    async def _parse_response_with_llm(self, prompt: str) -> Dict:
        """Usa LLM para convertir respuesta en JSON estructurado"""
        try:
            logging.info(f"Enviando solicitud a {self.validator_provider} usando modelo {self.validator_model}")
            
            # Usar LangChain para la llamada al LLM
            message = HumanMessage(content=prompt)
            response = self.llm.invoke([message])
            
            # Procesar la respuesta
            json_str = self._extract_json(response.content)
            return json.loads(json_str)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {str(e)}")
            return {"competitors": []}
        except Exception as e:
            logger.error(f"Error en _parse_response_with_llm: {str(e)}")
            return {"competitors": []}
    
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

    def save_competitors(self, competitors_data, business_idea_id):
        # List to store created competitors
        created_competitors = []
        
        for competitor_info in competitors_data['competitors']:
            try:
                # Handle different possible field names for competitor name
                competitor_name = competitor_info.get("competitor_name", "Unknown Competitor")
                
                # Create Competitor object
                competitor = Competitor(
                    business_idea_id=business_idea_id,
                    competitor_name=competitor_name,
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
                
            except Exception as e:
                logger.error(f"Error saving competitor {competitor_info}: {str(e)}")
                # Continue with the next competitor instead of failing completely
                continue
        
        # Commit to store competitors at the same time - remove await since this is a synchronous session
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error committing competitors to database: {str(e)}")
            self.db_session.rollback()
            raise
        
        return created_competitors

    async def research_competitors_async(
        self,
        prompt_search: dict,
        business_id: str,
        request_id: str
    ) -> str:
        """
        Inicia la investigación de competidores de forma asincrónica
        Esta función devuelve inmediatamente un ID de solicitud, mientras
        la investigación se procesa en n8n.
        
        Args:
            prompt_search: Prompt para la búsqueda (puede incluir URL de callback)
            business_id: ID del negocio
            request_id: ID único de la solicitud
            
        Returns:
            ID de la solicitud para seguimiento
        """
        logger.info(f"Iniciando investigación asincrónica para negocio {business_id} con ID {request_id}")
        
        try:
            # Configure the research module with the default settings
            research_config = ResearchConfig(
                model=self.research_model,
                language=self.lang,
                max_iterations=1
            )
            
            # Instantiate the research module
            research_module = ResearchModule(
                config=research_config
            )
            
            await research_module.research(prompt_search)
            
            # Log that we've started the task and will continue without waiting
            logger.info(f"Solicitud de investigación enviada, ID: {request_id}. Continuando sin esperar.")
            
            # Return the request ID immediately
            return request_id
            
        except Exception as e:
            logger.error(f"Error al iniciar investigación asíncrona: {str(e)}")
            raise