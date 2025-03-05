import json
import logging
import asyncio
import os
from typing import Dict, List, Any, Optional
import aisuite as ai
from openai import OpenAI
from app.services.storage.minio_service import MinioService
import app.prompts.business.prompts_state_of_art as prompts
from app.services.search.dynamic_research_ai import ResearchModule, ResearchConfig
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.state_of_art import MarketStateOfArt, StatusEnum
from sqlalchemy.orm import Session

from dotenv import load_dotenv
load_dotenv()


logger = logging.getLogger(__name__)

class MarketStateOfArtService:
    def __init__(
        self, 
        db_session: Session, 
        minio_client: MinioService,
        llm_provider: str = "openai",
        llm_model: str = "openai:gpt-4o",
        language: str = "en",
        max_iterations: int = 1,
        temperature: float = 0.7,
        test_mode: bool = False,
        test_questions_limit: int = 4
    ):
        self.db = db_session
        self.minio = minio_client
        self.language = language
        self.test_mode = test_mode
        self.test_questions_limit = test_questions_limit
        
        if llm_provider == "openai" or llm_provider == "claude":
            self.llm = ai.Client()
        elif llm_provider == "deepseek":
            self.llm = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"),
                              base_url="https://api.deepseek.com")
            
        self.llm_model = llm_model
        
        # Configuración para el módulo de investigación
        self.research_config = ResearchConfig(
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
            validator_api_keys={"openai": os.getenv("OPENAI_API_KEY")},
            validator_model="openai:gpt-4o-mini",
            language=language,
            max_iterations=max_iterations,
            temperature=temperature
        )
        
        self.research_module = ResearchModule(self.research_config, model_validator="openai")
    
    async def _get_business_idea(self, business_idea_id: str) -> BusinessIdea:
        """Obtiene el business idea desde la base de datos"""
        logger.info(f"Querying database for business idea with ID: {business_idea_id}")
        business_idea = self.db.query(BusinessIdea).filter(
            BusinessIdea.id == business_idea_id
        ).first()
        
        if not business_idea:
            logger.error(f"Business idea with ID {business_idea_id} not found in database")
            raise ValueError(f"Business idea with ID {business_idea_id} not found")
        
        logger.info(f"Found business idea: {business_idea.title} (ID: {business_idea.id})")
        return business_idea
    
    async def _get_or_create_business_understanding(
        self, 
        business_idea_id: str
    ) -> MarketStateOfArt:
        """Obtiene o crea un registro de BusinessUnderstanding"""
        logger.info(f"Querying database for existing MarketStateOfArt record for business idea ID: {business_idea_id}")
        business_understanding = self.db.query(MarketStateOfArt).filter(
            MarketStateOfArt.business_idea_id == business_idea_id
        ).first()
        
        if not business_understanding:
            logger.info(f"No existing MarketStateOfArt record found, creating new one for business idea ID: {business_idea_id}")
            business_understanding = MarketStateOfArt(
                business_idea_id=business_idea_id,
                language=self.language
            )
            self.db.add(business_understanding)
            self.db.commit()
            self.db.refresh(business_understanding)
            logger.info(f"Created new MarketStateOfArt record with ID: {business_understanding.id}")
        else:
            logger.info(f"Found existing MarketStateOfArt record with ID: {business_understanding.id}")
            
        return business_understanding
        
    async def generate_market_research_questions(
        self, 
        business_idea: BusinessIdea
    ) -> Dict[str, Any]:
        """Genera preguntas de investigación de mercado basadas en la idea de negocio"""
        logger.info(f"Generating market research questions for business idea: {business_idea.id} - {business_idea.title}")
        content = f"""
        Title: {business_idea.title}
        Description: {business_idea.description}
        Mission: {business_idea.mission or ''}
        Vision: {business_idea.vision or ''}
        """
        
        system_prompt = prompts.get_market_research_prompt(language=self.language)
        logger.info(f"Using language: {self.language} for market research prompt")
        
        try:
            logger.info(f"Calling LLM with model: {self.llm_model} to generate market research questions")
            response = self.llm.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                temperature=0.3
            )
            
            logger.info("LLM response received for market research questions")
            # Intentamos parsear el JSON de la respuesta
            response_text = response.choices[0].message.content.strip()
            
            # Limpiar posibles marcadores de código
            if response_text.startswith("```json"):
                logger.info("Cleaning JSON code markers from response")
                response_text = response_text.split("```json", 1)[1]
            if response_text.endswith("```"):
                response_text = response_text.rsplit("```", 1)[0]
            
            response_text = response_text.strip()
            
            logger.info("Parsing JSON response for market research questions")
            result = json.loads(response_text)
            logger.info(f"Successfully generated market research questions with {len(result)} main categories")
            return result
            
        except Exception as e:
            logger.error(f"Error generating market research questions: {str(e)}", exc_info=True)
            raise

    async def generate_state_of_art_questions(
        self, 
        business_idea: BusinessIdea
    ) -> Dict[str, Any]:
        """Genera preguntas de estado del arte basadas en la idea de negocio"""
        logger.info(f"Generating state of art questions for business idea: {business_idea.id} - {business_idea.title}")
        content = f"""
        Title: {business_idea.title}
        Description: {business_idea.description}
        Mission: {business_idea.mission or ''}
        Vision: {business_idea.vision or ''}
        """
        
        system_prompt = prompts.get_state_of_art_prompt(language=self.language)
        logger.info(f"Using language: {self.language} for state of art prompt")
        
        try:
            logger.info(f"Calling LLM with model: {self.llm_model} to generate state of art questions")
            response = self.llm.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                temperature=0.3
            )
            
            logger.info("LLM response received for state of art questions")
            # Intentamos parsear el JSON de la respuesta
            response_text = response.choices[0].message.content.strip()
            
            # Limpiar posibles marcadores de código
            if response_text.startswith("```json"):
                logger.info("Cleaning JSON code markers from response")
                response_text = response_text.split("```json", 1)[1]
            if response_text.endswith("```"):
                response_text = response_text.rsplit("```", 1)[0]
            
            response_text = response_text.strip()
            
            logger.info("Parsing JSON response for state of art questions")
            result = json.loads(response_text)
            logger.info(f"Successfully generated state of art questions with {len(result)} categories")
            
            # Normalize keys in case they don't match expected format
            normalized_result = {}
            expected_keys = [
                "LiteraturaAcademicaYFundamentosTeóricos", "AcademicLiteratureAndTheoreticalFoundations",
                "EstudiosEmpíricosYBenchmarks", "EmpiricalStudiesAndBenchmarks",
                "PerspectivasDeConsumoYTendencias", "ConsumerPerspectivesAndTrends",
                "MetodologíasDeInvestigación", "ResearchMethodologies",
                "GapAnalysisYLíneasFuturas", "GapAnalysisAndFutureLines",
                "AplicacionesPrácticasYRecomendaciones", "PracticalApplicationsAndRecommendations"
            ]
            
            # Map Spanish keys to normalized keys
            key_mapping = {
                "LiteraturaAcademicaYFundamentosTeóricos": "AcademicLiteratureAndTheoreticalFoundations",
                "EstudiosEmpíricosYBenchmarks": "EmpiricalStudiesAndBenchmarks",
                "PerspectivasDeConsumoYTendencias": "ConsumerPerspectivesAndTrends",
                "MetodologíasDeInvestigación": "ResearchMethodologies",
                "GapAnalysisYLíneasFuturas": "GapAnalysisAndFutureLines",
                "AplicacionesPrácticasYRecomendaciones": "PracticalApplicationsAndRecommendations"
            }
            
            # Create a dictionary with normalized keys and data
            for key, value in result.items():
                normalized_key = key_mapping.get(key, key)
                normalized_result[normalized_key] = value
            
            # Ensure all expected keys are in the result
            for key in expected_keys:
                if key not in normalized_result:
                    # Check if we have a matching key in the result
                    found = False
                    for result_key in result.keys():
                        if result_key.lower().replace(" ", "") == key.lower().replace(" ", ""):
                            normalized_result[key] = result[result_key]
                            found = True
                            break
                    
                    # If still not found, create an empty structure
                    if not found and key in [
                        "AcademicLiteratureAndTheoreticalFoundations",
                        "EmpiricalStudiesAndBenchmarks",
                        "ConsumerPerspectivesAndTrends",
                        "ResearchMethodologies",
                        "GapAnalysisAndFutureLines",
                        "PracticalApplicationsAndRecommendations"
                    ]:
                        normalized_result[key] = {
                            "preguntasPrincipales": [],
                            "fuentesSugeridas": []
                        }
            
            return normalized_result
            
        except Exception as e:
            logger.error(f"Error generating state of art questions: {str(e)}", exc_info=True)
            raise
    
    async def answer_questions(
        self, 
        questions_dict: Dict[str, Any],
        is_market_research: bool = True
    ) -> Dict[str, Any]:
        """Responde a las preguntas usando el módulo de research"""
        research_type = "market research" if is_market_research else "state of art"
        logger.info(f"Starting to answer {research_type} questions")
        
        # Check if we're in test mode
        if self.test_mode:
            logger.info(f"RUNNING IN TEST MODE - Will only process up to {self.test_questions_limit} questions per category")
        
        result = {}
        
        # Log the structure of the questions_dict to help debug
        logger.info(f"Questions dictionary structure: {json.dumps(questions_dict, indent=2)[:500]}...")
        
        # Extraemos todas las preguntas según el formato
        if is_market_research:
            # Para investigación de mercado
            logger.info(f"Processing market research questions with {len(questions_dict)} main categories")
            
            # In test mode, limit the number of categories
            categories_to_process = list(questions_dict.keys())
            if self.test_mode and len(categories_to_process) > 2:
                logger.info(f"TEST MODE: Limiting to first 2 categories instead of {len(categories_to_process)}")
                categories_to_process = categories_to_process[:2]
            
            for main_category in categories_to_process:
                category_data = questions_dict[main_category]
                logger.info(f"Processing main category: {main_category}")
                logger.info(f"Category data keys: {list(category_data.keys())}")
                
                result[main_category] = {"subitems": []}
                
                # Check if the expected structure exists
                if "subitems" not in category_data:
                    logger.warning(f"No 'subitems' key found in category {main_category}. Available keys: {list(category_data.keys())}")
                    # Try alternative keys or create a default structure
                    subitems = category_data.get("subcategories", category_data.get("items", []))
                    if not subitems and isinstance(category_data, dict):
                        # If no recognized keys, try to use the category data directly
                        logger.info(f"Using category data directly for {main_category}")
                        # Create a single subitem with all questions from this category
                        questions = []
                        for key, value in category_data.items():
                            if isinstance(value, list):
                                questions.extend(value)
                            elif isinstance(value, str):
                                questions.append(value)
                        
                        if questions:
                            subitems = [{
                                "title": main_category,
                                "titulo": main_category,
                                "questions": questions,
                                "preguntas": questions
                            }]
                        else:
                            logger.warning(f"Could not extract questions from category {main_category}")
                            continue
                else:
                    subitems = category_data["subitems"]
                
                # In test mode, limit the number of subitems
                if self.test_mode and len(subitems) > 2:
                    logger.info(f"TEST MODE: Limiting to first 2 subitems instead of {len(subitems)}")
                    subitems = subitems[:2]
                
                for subitem in subitems:
                    # Handle different key formats (English/Spanish)
                    title = subitem.get("titulo", subitem.get("title", "Unknown"))
                    questions = subitem.get("preguntas", subitem.get("questions", []))
                    
                    # In test mode, limit the number of questions
                    if self.test_mode and len(questions) > self.test_questions_limit:
                        logger.info(f"TEST MODE: Limiting to first {self.test_questions_limit} questions instead of {len(questions)}")
                        questions = questions[:self.test_questions_limit]
                    
                    logger.info(f"Processing subitem: {title} with {len(questions)} questions")
                    subitem_result = {
                        "titulo": title,
                        "preguntas": questions,
                        "respuestas": []
                    }
                    
                    # Procesar las preguntas en batches para optimizar
                    batch_size = 3  # Procesar 3 preguntas a la vez
                    for i in range(0, len(questions), batch_size):
                        batch = questions[i:i+batch_size]
                        logger.info(f"Processing batch of {len(batch)} questions (from {i} to {i+len(batch)-1})")
                        
                        # Crear tareas para responder preguntas en paralelo
                        logger.info("Creating research tasks for batch")
                        tasks = [self.research_module.research(question) for question in batch]
                        logger.info("Awaiting research tasks to complete")
                        batch_answers = await asyncio.gather(*tasks)
                        logger.info(f"Received {len(batch_answers)} answers for batch")
                        
                        subitem_result["respuestas"].extend(batch_answers)
                    
                    result[main_category]["subitems"].append(subitem_result)
                    logger.info(f"Completed processing subitem: {title}")
        else:
            # Para estado del arte
            logger.info(f"Processing state of art questions with {len(questions_dict)} categories")
            
            # In test mode, limit the number of categories
            categories_to_process = list(questions_dict.keys())
            if self.test_mode and len(categories_to_process) > 2:
                logger.info(f"TEST MODE: Limiting to first 2 categories instead of {len(categories_to_process)}")
                categories_to_process = categories_to_process[:2]
            
            for category in categories_to_process:
                logger.info(f"Processing category: {category}")
                category_data = questions_dict.get(category, {})
                
                # Check if the category is present in the questions_dict
                if not category_data:
                    logger.warning(f"No data found for category {category}")
                    # Create an empty structure for this category
                    result[category] = {
                        "preguntasPrincipales": [],
                        "fuentesSugeridas": [],
                        "respuestas": []
                    }
                    continue
                
                logger.info(f"Category data keys: {list(category_data.keys())}")
                
                # Handle different key formats (English/Spanish)
                main_questions = category_data.get("preguntasPrincipales", 
                                                 category_data.get("mainQuestions", 
                                                                 category_data.get("questions", [])))
                suggested_sources = category_data.get("fuentesSugeridas", 
                                                    category_data.get("suggestedSources", []))
                
                # If still no questions found, try to extract them from other keys
                if not main_questions and isinstance(category_data, dict):
                    logger.warning(f"No main questions found in category {category}. Trying to extract from other keys.")
                    for key, value in category_data.items():
                        if isinstance(value, list) and all(isinstance(item, str) for item in value):
                            logger.info(f"Found potential questions in key {key}")
                            main_questions = value
                            break
                
                # In test mode, limit the number of questions
                if self.test_mode and len(main_questions) > self.test_questions_limit:
                    logger.info(f"TEST MODE: Limiting to first {self.test_questions_limit} questions instead of {len(main_questions)}")
                    main_questions = main_questions[:self.test_questions_limit]
                
                result[category] = {
                    "preguntasPrincipales": main_questions,
                    "fuentesSugeridas": suggested_sources,
                    "respuestas": []
                }
                
                # Procesar las preguntas en batches
                logger.info(f"Category has {len(main_questions)} main questions")
                batch_size = 3
                for i in range(0, len(main_questions), batch_size):
                    batch = main_questions[i:i+batch_size]
                    logger.info(f"Processing batch of {len(batch)} questions (from {i} to {i+len(batch)-1})")
                    
                    # Crear tareas para responder preguntas en paralelo
                    logger.info("Creating research tasks for batch")
                    tasks = [self.research_module.research(question) for question in batch]
                    logger.info("Awaiting research tasks to complete")
                    batch_answers = await asyncio.gather(*tasks)
                    logger.info(f"Received {len(batch_answers)} answers for batch")
                    
                    result[category]["respuestas"].extend(batch_answers)
                logger.info(f"Completed processing category: {category}")
        
        logger.info(f"Completed answering all {research_type} questions")
        return result
    
    async def process_business_understanding(
        self, 
        business_idea_id: str,
        force_update: bool = False
    ) -> Dict[str, Any]:
        """Procesa toda la lógica de business understanding para una idea de negocio"""
        logger.info(f"Starting business understanding process for business idea: {business_idea_id}")
        
        # Obtener o crear registros
        logger.info("Getting business idea from database")
        business_idea = await self._get_business_idea(business_idea_id)
        logger.info(f"Retrieved business idea: {business_idea.title}")
        
        logger.info("Getting or creating business understanding record")
        business_understanding = await self._get_or_create_business_understanding(business_idea_id)
        logger.info(f"Business understanding record ID: {business_understanding.id}")
        
        # Define paths for MinIO objects
        market_research_path = f"{business_idea_id}/business-understanding/market_research.json"
        state_of_art_path = f"{business_idea_id}/business-understanding/state_of_art.json"
        
        # If force_update is True, delete existing files in MinIO
        if force_update:
            logger.info("Force update requested, deleting existing files in MinIO")
            try:
                logger.info(f"Attempting to delete market research file: {market_research_path}")
                self.minio.delete_object(market_research_path)
                logger.info("Market research file deleted successfully")
            except Exception as e:
                logger.warning(f"Error deleting market research file: {str(e)}")
            
            try:
                logger.info(f"Attempting to delete state of art file: {state_of_art_path}")
                self.minio.delete_object(state_of_art_path)
                logger.info("State of art file deleted successfully")
            except Exception as e:
                logger.warning(f"Error deleting state of art file: {str(e)}")
        
        results = {}
        
        # Iniciar con investigación de mercado si no está completada o force_update es True
        if business_understanding.market_research_status != StatusEnum.COMPLETED or force_update:
            logger.info("Market research not completed or force update requested, starting process")
            try:
                # Actualizar estado
                logger.info("Updating market research status to IN_PROGRESS")
                business_understanding.market_research_status = StatusEnum.IN_PROGRESS
                self.db.commit()
                
                # Generar preguntas
                logger.info("Generating market research questions")
                market_research_questions = await self.generate_market_research_questions(business_idea)
                logger.info("Market research questions generated successfully")
                
                # Responder preguntas
                logger.info("Starting to answer market research questions")
                market_research_answers = await self.answer_questions(
                    market_research_questions, 
                    is_market_research=True
                )
                logger.info("Market research questions answered successfully")
                
                # Guardar en MinIO
                logger.info(f"Uploading market research answers to MinIO at path: {market_research_path}")
                try:
                    await self.minio.upload_content(
                        object_name=market_research_path,
                        data=json.dumps(market_research_answers, indent=2),
                        content_type="application/json",
                        metadata={
                            "business_id": business_idea_id,
                            "type": "market_research"
                        }
                    )
                    logger.info("Market research answers uploaded to MinIO successfully")
                except Exception as upload_error:
                    logger.error(f"Failed to upload market research to MinIO: {str(upload_error)}", exc_info=True)
                    raise Exception(f"Failed to upload market research to MinIO: {str(upload_error)}")
                
                # Actualizar registro
                logger.info("Updating business understanding record with market research path")
                business_understanding.market_research_path = market_research_path
                business_understanding.market_research_status = StatusEnum.COMPLETED
                self.db.commit()
                logger.info("Business understanding record updated successfully")
                
                results["market_research"] = {
                    "status": "completed",
                    "path": market_research_path
                }
                logger.info("Market research process completed successfully")
                
            except Exception as e:
                logger.error(f"Error in market research process: {str(e)}", exc_info=True)
                business_understanding.market_research_status = StatusEnum.FAILED
                business_understanding.error_message = str(e)
                self.db.commit()
                logger.info("Updated business understanding record with FAILED status")
                
                results["market_research"] = {
                    "status": "failed",
                    "error": str(e)
                }
        else:
            logger.info("Market research already completed, skipping")
            results["market_research"] = {
                "status": "already_completed",
                "path": business_understanding.market_research_path
            }
        
        # Continuar con estado del arte si no está completado o force_update es True
        if business_understanding.state_of_art_status != StatusEnum.COMPLETED or force_update:
            logger.info("State of art not completed or force update requested, starting process")
            try:
                # Actualizar estado
                logger.info("Updating state of art status to IN_PROGRESS")
                business_understanding.state_of_art_status = StatusEnum.IN_PROGRESS
                self.db.commit()
                
                # Generar preguntas
                logger.info("Generating state of art questions")
                state_of_art_questions = await self.generate_state_of_art_questions(business_idea)
                logger.info("State of art questions generated successfully")
                
                # Responder preguntas
                logger.info("Starting to answer state of art questions")
                state_of_art_answers = await self.answer_questions(
                    state_of_art_questions, 
                    is_market_research=False
                )
                logger.info("State of art questions answered successfully")
                
                # Guardar en MinIO
                logger.info(f"Uploading state of art answers to MinIO at path: {state_of_art_path}")
                try:
                    await self.minio.upload_content(
                        object_name=state_of_art_path,
                        data=json.dumps(state_of_art_answers, indent=2),
                        content_type="application/json",
                        metadata={
                            "business_id": business_idea_id,
                            "type": "state_of_art"
                        }
                    )
                    logger.info("State of art answers uploaded to MinIO successfully")
                except Exception as upload_error:
                    logger.error(f"Failed to upload state of art to MinIO: {str(upload_error)}", exc_info=True)
                    raise Exception(f"Failed to upload state of art to MinIO: {str(upload_error)}")
                
                # Actualizar registro
                logger.info("Updating business understanding record with state of art path")
                business_understanding.state_of_art_path = state_of_art_path
                business_understanding.state_of_art_status = StatusEnum.COMPLETED
                self.db.commit()
                logger.info("Business understanding record updated successfully")
                
                results["state_of_art"] = {
                    "status": "completed",
                    "path": state_of_art_path
                }
                logger.info("State of art process completed successfully")
                
            except Exception as e:
                logger.error(f"Error in state of art process: {str(e)}", exc_info=True)
                business_understanding.state_of_art_status = StatusEnum.FAILED
                business_understanding.error_message = str(e)
                self.db.commit()
                logger.info("Updated business understanding record with FAILED status")
                
                results["state_of_art"] = {
                    "status": "failed",
                    "error": str(e)
                }
        else:
            logger.info("State of art already completed, skipping")
            results["state_of_art"] = {
                "status": "already_completed",
                "path": business_understanding.state_of_art_path
            }
        
        logger.info("Business understanding process completed")
        return results