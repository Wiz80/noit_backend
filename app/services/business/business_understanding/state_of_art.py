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
from app.models.business.business_understanding.state_of_art import MarketStateOfArt, StatusEnum, ResearchTask, ResearchTypeEnum
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
        depth: str = "normal"
    ):
        self.db = db_session
        self.minio = minio_client
        self.language = language
        self.depth = depth
        
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
    
    async def create_research_tasks(
        self, 
        questions_dict: Dict[str, Any],
        business_understanding_id: str,
        business_idea_id: str,
        is_market_research: bool = True
    ) -> List[ResearchTask]:
        """Creates research tasks for the questions and sends them to the research module"""
        research_type = "market_research" if is_market_research else "state_of_art"
        logger.info(f"Creating research tasks for {research_type}")
        
        # Define how many request chunks we'll make based on depth
        depth_chunks = {
            "very simple": 1,  # All questions in one request
            "simple": 2,       # Split into 2 requests
            "normal": 3,       # Split into 3 requests
            "pro": 4,          # Split into 4 requests
            "deep": 6          # Split into 6 requests (or one per category)
        }
        
        # Get the number of chunks based on depth
        num_chunks = depth_chunks.get(self.depth, 3)  # Default to 'normal' if invalid depth
        logger.info(f"Using depth '{self.depth}' - will process all questions in {num_chunks} large request(s)")
        
        # Extract all questions into a flat structure for processing
        all_questions = []
        question_mapping = {}  # Maps question to its original location
        
        if is_market_research:
            # For market research
            for main_category in questions_dict.keys():
                category_data = questions_dict[main_category]
                
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
                            continue
                else:
                    subitems = category_data["subitems"]
                
                # Create subitems in result structure
                for idx, subitem in enumerate(subitems):
                    # Handle different key formats (English/Spanish)
                    title = subitem.get("titulo", subitem.get("title", "Unknown"))
                    questions = subitem.get("preguntas", subitem.get("questions", []))
                    
                    logger.info(f"Collecting questions from {main_category} - {title}: {len(questions)} questions")
                    
                    # Add questions to the flat list and keep track of their location
                    for question in questions:
                        all_questions.append(question)
                        question_mapping[question] = (main_category, idx)
        else:
            # For state of art
            for category in questions_dict.keys():
                category_data = questions_dict.get(category, {})
                
                # Check if the category is present
                if not category_data:
                    continue
                
                # Handle different key formats (English/Spanish)
                main_questions = category_data.get("preguntasPrincipales", 
                                                category_data.get("mainQuestions", 
                                                                category_data.get("questions", [])))
                
                # If still no questions found, try to extract them from other keys
                if not main_questions and isinstance(category_data, dict):
                    for key, value in category_data.items():
                        if isinstance(value, list) and all(isinstance(item, str) for item in value):
                            main_questions = value
                            break
                
                logger.info(f"Collecting questions from {category}: {len(main_questions)} questions")
                
                # Add questions to the flat list and keep track of their location
                for question in main_questions:
                    all_questions.append(question)
                    question_mapping[question] = category
        
        # Log total question count
        logger.info(f"Total questions collected: {len(all_questions)}")
        
        # Split questions into chunks based on depth
        if num_chunks > len(all_questions):
            num_chunks = len(all_questions)
            logger.info(f"Reducing number of chunks to {num_chunks} as there are only {len(all_questions)} questions")
            
        chunk_size = len(all_questions) // num_chunks
        remainder = len(all_questions) % num_chunks
        
        question_chunks = []
        start = 0
        for i in range(num_chunks):
            # Add an extra item to the first 'remainder' chunks
            end = start + chunk_size + (1 if i < remainder else 0)
            question_chunks.append(all_questions[start:end])
            start = end
        
        # Log chunk distribution
        for i, chunk in enumerate(question_chunks):
            logger.info(f"Chunk {i+1} has {len(chunk)} questions")
        
        # Create and send research tasks
        research_tasks = []
        for i, chunk in enumerate(question_chunks):
            logger.info(f"Processing chunk {i+1}/{len(question_chunks)} with {len(chunk)} questions")
            
            # Create research task record
            task = ResearchTask(
                business_understanding_id=business_understanding_id,
                business_idea_id=business_idea_id,
                request_id="pending",  # Will be updated after sending to research module
                research_type=ResearchTypeEnum.MARKET_RESEARCH if is_market_research else ResearchTypeEnum.STATE_OF_ART,
                depth=self.depth,
                chunk_index=f"{i+1}/{num_chunks}",
                status=StatusEnum.PENDING
            )
            
            # Store questions in task
            task.add_questions(chunk)
            
            # Save task to database
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            
            # Create and send research request
            try:
                # Create the callback URL with the task ID
                callback_url = f"/api/v1/business/{business_idea_id}/research-callback/{task.id}"
                
                # Send research request
                request_dict = {
                    "search_query": "\n".join(chunk),
                    "task_id": task.id,
                    "business_id": business_idea_id,
                    "research_type": research_type,
                    "callback_url": callback_url
                }
                
                # Send to research module
                response = await self.research_module.research(
                    query=request_dict,
                    business_id=business_idea_id,
                    task_id=task.id
                )
                
                # Extract request ID from response
                request_id = None
                if isinstance(response, str) and "ID:" in response:
                    # Try to extract request ID from response text
                    try:
                        request_id = response.split("ID:")[1].split(".")[0].strip()
                    except:
                        request_id = "unknown"
                
                # Update task with request ID
                task.request_id = request_id
                task.status = StatusEnum.IN_PROGRESS
                self.db.commit()
                
                logger.info(f"Research task created and sent: ID={task.id}, RequestID={request_id}")
                research_tasks.append(task)
                
            except Exception as e:
                logger.error(f"Error sending research task: {str(e)}", exc_info=True)
                task.status = StatusEnum.FAILED
                task.error_message = str(e)
                self.db.commit()
        
        return research_tasks

    async def process_callback_data(
        self,
        task_id: str,
        research_data: Dict[str, Any]
    ) -> bool:
        """Process callback data from research module and update the task"""
        logger.info(f"Processing callback data for task: {task_id}")
        
        # Find the task
        task = self.db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
        if not task:
            logger.error(f"Task with ID {task_id} not found")
            return False
        
        try:
            # Update task with answer data
            task.add_answer(research_data)
            task.status = StatusEnum.COMPLETED
            self.db.commit()
            
            # Get all tasks for this business understanding
            business_understanding = task.business_understanding
            all_tasks = self.db.query(ResearchTask).filter(
                ResearchTask.business_understanding_id == business_understanding.id,
                ResearchTask.research_type == task.research_type
            ).all()
            
            # Check if all tasks are completed
            all_completed = all(t.status == StatusEnum.COMPLETED for t in all_tasks)
            
            if all_completed:
                logger.info(f"All {task.research_type} tasks completed, compiling results")
                
                # Compile results based on the type
                compiled_results = self.compile_research_results(
                    business_understanding,
                    all_tasks,
                    is_market_research=(task.research_type == ResearchTypeEnum.MARKET_RESEARCH)
                )
                
                # Store results in MinIO
                object_name = f"{task.business_idea_id}/business-understanding/{task.research_type}_{self.depth}.json"
                
                await self.minio.upload_content(
                    object_name=object_name,
                    data=json.dumps(compiled_results, indent=2),
                    content_type="application/json",
                    metadata={
                        "business_id": task.business_idea_id,
                        "type": task.research_type
                    }
                )
                
                # Update business understanding record
                if task.research_type == ResearchTypeEnum.MARKET_RESEARCH:
                    business_understanding.market_research_path = object_name
                    business_understanding.market_research_status = StatusEnum.COMPLETED
                else:
                    business_understanding.state_of_art_path = object_name
                    business_understanding.state_of_art_status = StatusEnum.COMPLETED
                
                self.db.commit()
                logger.info(f"Business understanding record updated with {task.research_type} results")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing callback data: {str(e)}", exc_info=True)
            task.status = StatusEnum.FAILED
            task.error_message = str(e)
            self.db.commit()
            return False
    
    def compile_research_results(
        self,
        business_understanding: MarketStateOfArt,
        tasks: List[ResearchTask],
        is_market_research: bool = True
    ) -> Dict[str, Any]:
        """Compile research results from tasks into the original structure"""
        logger.info(f"Compiling {'market research' if is_market_research else 'state of art'} results")
        
        # Get questions_dict from the first task
        # This is just to get the original structure
        result = {}
        
        # Get all questions and answers
        answers = {}
        question_mapping = {}
        
        # Extract all answers and mappings from completed tasks
        for task in tasks:
            if task.status != StatusEnum.COMPLETED:
                continue
                
            task_questions = task.get_questions()
            task_answer = task.get_answer()
            
            if not task_answer:
                continue
                
            # Map answers to questions
            for question in task_questions:
                if question not in question_mapping:
                    if is_market_research:
                        # Find the question in the original structure
                        # This is a placeholder - we'll need to get this from somewhere
                        question_mapping[question] = ("Unknown", 0)
                    else:
                        question_mapping[question] = "Unknown"
                    
                    # Store the answer
                    answers[question] = task_answer
        
        # Now construct the result structure
        if is_market_research:
            # Here we'd need the original questions structure
            # This is a placeholder implementation
            pass
        else:
            # Here we'd need the original questions structure
            # This is a placeholder implementation
            pass
            
        return result
    
    async def process_business_understanding(
        self, 
        business_idea_id: str,
        force_update: bool = False,
        depth: str = "normal"
    ) -> Dict[str, Any]:
        """Procesa toda la lógica de business understanding para una idea de negocio"""
        logger.info(f"Starting business understanding process for business idea: {business_idea_id}")
        
        # Update the depth parameter
        self.depth = depth
        logger.info(f"Using depth parameter: {self.depth}")
        
        # Obtener o crear registros
        logger.info("Getting business idea from database")
        business_idea = await self._get_business_idea(business_idea_id)
        logger.info(f"Retrieved business idea: {business_idea.title}")
        
        logger.info("Getting or creating business understanding record")
        business_understanding = await self._get_or_create_business_understanding(business_idea_id)
        logger.info(f"Business understanding record ID: {business_understanding.id}")
        
        # Define paths for MinIO objects
        market_research_path = f"{business_idea_id}/business-understanding/market_research_{self.depth}.json"
        state_of_art_path = f"{business_idea_id}/business-understanding/state_of_art_{self.depth}.json"
        
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
                
                # Delete any existing research tasks
                if force_update:
                    logger.info("Deleting existing market research tasks")
                    self.db.query(ResearchTask).filter(
                        ResearchTask.business_understanding_id == business_understanding.id,
                        ResearchTask.research_type == ResearchTypeEnum.MARKET_RESEARCH
                    ).delete()
                    self.db.commit()
                
                # Generar preguntas
                logger.info("Generating market research questions")
                market_research_questions = await self.generate_market_research_questions(business_idea)
                logger.info("Market research questions generated successfully")
                
                # Create research tasks
                logger.info("Creating market research tasks")
                market_research_tasks = await self.create_research_tasks(
                    questions_dict=market_research_questions,
                    business_understanding_id=business_understanding.id,
                    business_idea_id=business_idea_id,
                    is_market_research=True
                )
                logger.info(f"Created {len(market_research_tasks)} market research tasks")
                
                results["market_research"] = {
                    "status": "in_progress",
                    "tasks_created": len(market_research_tasks),
                    "task_ids": [task.id for task in market_research_tasks]
                }
                logger.info("Market research process initiated")
                
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
                
                # Delete any existing research tasks
                if force_update:
                    logger.info("Deleting existing state of art tasks")
                    self.db.query(ResearchTask).filter(
                        ResearchTask.business_understanding_id == business_understanding.id,
                        ResearchTask.research_type == ResearchTypeEnum.STATE_OF_ART
                    ).delete()
                    self.db.commit()
                
                # Generar preguntas
                logger.info("Generating state of art questions")
                state_of_art_questions = await self.generate_state_of_art_questions(business_idea)
                logger.info("State of art questions generated successfully")
                
                # Create research tasks
                logger.info("Creating state of art tasks")
                state_of_art_tasks = await self.create_research_tasks(
                    questions_dict=state_of_art_questions,
                    business_understanding_id=business_understanding.id,
                    business_idea_id=business_idea_id,
                    is_market_research=False
                )
                logger.info(f"Created {len(state_of_art_tasks)} state of art tasks")
                
                results["state_of_art"] = {
                    "status": "in_progress",
                    "tasks_created": len(state_of_art_tasks),
                    "task_ids": [task.id for task in state_of_art_tasks]
                }
                logger.info("State of art process initiated")
                
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
        
        logger.info("Business understanding process initiated")
        return results