from typing import Any, Dict, List
import logging
from requests import Session
from app.models.business.business_understanding.state_of_art import ResearchTask
from app.services.storage.minio_service import MinioService

from app.services.business.business_understanding.state_of_art import MarketStateOfArtService
from app.models.business.business_understanding.state_of_art import ResearchTask, StatusEnum, ResearchTypeEnum, MarketStateOfArt

#import aisuite
import aisuite as ai

from datetime import datetime
import json

logger = logging.getLogger(__name__)

class StateOfArtController:

    def __init__(self):
        self.llm = ai.Client()

    async def process_state_of_art_research(
        self,
        task: ResearchTask,
        body_json: Dict[str, Any],
        db: Session,
        minio_client: MinioService
    ) -> Dict[str, Any]:
        """
        Process state of art research
        
        Args:
            task: The ResearchTask object
            body_json: JSON data from the webhook request
            db: Database session
            minio_client: MinIO client
            
        Returns:
            Dict with processing result information
        """
        logger.info(f"Processing business understanding research for task: {task.id}")
        
        # Extract data from the task
        business_id = task.business_idea_id
        research_type = task.research_type
        logger.info(f"Business ID: {business_id}, Research Type: {research_type}")
        
        # Get the business understanding record
        business_understanding = db.query(MarketStateOfArt).filter(
            MarketStateOfArt.id == task.business_understanding_id
        ).first()
        
        if not business_understanding:
            logger.error(f"MarketStateOfArt with ID {task.business_understanding_id} not found")
            return {
                "status": "error",
                "message": f"MarketStateOfArt with ID {task.business_understanding_id} not found"
                }
        
        # Extract the research text and citations
        research_text = body_json.get("text", "")
        citations = body_json.get("citations", [])

        try:
            # Get questions from MinIO
            questions_json = minio_client.get_object_data(f"{business_id}/business-understanding/state_of_art_questions.json")
            questions = json.loads(questions_json.decode('utf-8')) if questions_json else {}
            
            # If we have task-specific questions, load those
            task_questions = task.get_questions() if task.questions else []
            
            # Call LLM to format the answer data
            # Format depends on whether we're processing state_of_art or market_research
            formatted_response = await self._format_research_answers(
                research_type=research_type,
                questions=questions,
                task_questions=task_questions,
                research_text=research_text
            )
            
            # Format the complete answer data with both original text and formatted answers
            answer_data = {
                "text": research_text,
                "citations": citations,
                "request_id": body_json.get("request_id", task.request_id),
                "business_id": business_id,
                "research_type": str(research_type),
                "search_prompt": body_json.get("search_prompt", ""),
                "timestamp": datetime.now().isoformat(),
                "formatted_answers": formatted_response
            }
            
            # Update task with answer data
            task.add_answer(answer_data)
            task.status = StatusEnum.COMPLETED
            task.completed_at = datetime.now()
            db.commit()
            logger.info(f"Updated task {task.id} with answer data")
            
            # Guardar la tarea individual en MinIO
            task_object_name = f"{business_id}/business-understanding/tasks/{research_type}_{task.id}.json"
            await minio_client.upload_content(
                object_name=task_object_name,
                data=json.dumps(answer_data, indent=2),
                content_type="application/json",
                metadata={
                    "business_id": business_id,
                    "task_id": task.id,
                    "research_type": str(research_type),
                    "depth": task.depth,
                    "chunk_index": task.chunk_index
                }
            )
            logger.info(f"Saved individual task answer to MinIO: {task_object_name}")
            
            # Get all tasks for this business understanding and research type
            all_tasks = db.query(ResearchTask).filter(
                ResearchTask.business_understanding_id == business_understanding.id,
                ResearchTask.research_type == task.research_type
            ).all()
            
            # Check if all tasks are completed
            all_completed = all(t.status == StatusEnum.COMPLETED for t in all_tasks)
            
            if all_completed:
                logger.info(f"All {task.research_type} tasks completed, compiling results")
                
                # Determine the path based on the research type and depth
                object_name = f"{business_id}/business-understanding/"
                if research_type == ResearchTypeEnum.MARKET_RESEARCH:
                    object_name += f"market_research_{task.depth}.json"
                else:
                    object_name += f"state_of_art_{task.depth}.json"
                
                # Collect all answers
                all_answers = {}
                for t in all_tasks:
                    if t.status == StatusEnum.COMPLETED:
                        t_answer = t.get_answer()
                        if t_answer:
                            # Use the task ID as the key
                            all_answers[t.id] = t_answer
                
                # Store the combined answers in MinIO
                await minio_client.upload_content(
                    object_name=object_name,
                    data=json.dumps(all_answers, indent=2),
                    content_type="application/json",
                    metadata={
                        "business_id": business_id,
                        "research_type": str(task.research_type),
                        "depth": task.depth
                    }
                )
                logger.info(f"Saved combined research results to MinIO: {object_name}")
                
                # Update business understanding record
                if research_type == ResearchTypeEnum.MARKET_RESEARCH:
                    business_understanding.market_research_path = object_name
                    business_understanding.market_research_status = StatusEnum.COMPLETED
                else:
                    business_understanding.state_of_art_path = object_name
                    business_understanding.state_of_art_status = StatusEnum.COMPLETED
                
                db.commit()
                logger.info(f"Updated business understanding record with {task.research_type} results")
            
            return {
                "status": "success",
                "message": f"Processed {research_type} research for task {task.id}",
                "business_id": business_id,
                "all_completed": all_completed
            }
            
        except Exception as e:
            logger.error(f"Error processing {research_type} research: {str(e)}", exc_info=True)
            task.status = StatusEnum.FAILED
            task.error_message = str(e)
            db.commit()
            
            return {
                "status": "error",
                "message": f"Error processing {research_type} research: {str(e)}"
            }
    
    async def _format_research_answers(
        self, 
        research_type: ResearchTypeEnum,
        questions: Dict,
        task_questions: List,
        research_text: str
    ) -> Dict:
        """
        Format research answers using LLM based on research type and question structure
        
        Args:
            research_type: Type of research (market research or state of art)
            questions: The complete question structure from MinIO
            task_questions: The specific questions for this task
            research_text: The research answer text
            
        Returns:
            Formatted answers in the structure matching the questions
        """
        try:
            # Determine prompt based on research type
            if research_type == ResearchTypeEnum.STATE_OF_ART:
                system_prompt = """
                You are a research expert responsible for formatting research answers.
                You need to match research content to specific questions and organize them in the same structure as the original questions.
                
                For State of Art research, the questions are organized in categories like:
                - LiteraturaAcademicaYFundamentosTeóricos
                - EstudiosEmpíricosYBenchmarks
                - PerspectivasDeConsumoYTendencias
                - etc.
                
                Each category has preguntasPrincipales (main questions) and fuentesSugeridas (suggested sources).
                
                Extract answers from the research text for each question in preguntasPrincipales.
                If a question doesn't have a clear answer in the text, indicate "No hay información suficiente".
                Preserve the exact structure of the questions object, but add an "answer" field to each question.
                """
            else:  # MARKET_RESEARCH
                system_prompt = """
                You are a research expert responsible for formatting research answers.
                You need to match research content to specific questions and organize them in the same structure as the original questions.
                
                For Market Research, the questions are organized in categories like:
                - Macroentorno (with subcategories like Factores Políticos, Factores Económicos, etc.)
                - Microentorno (with subcategories like Competidores, etc.)
                - etc.
                
                Each category has subitems, and each subitem has a titulo (title) and preguntas (questions).
                
                Extract answers from the research text for each question in preguntas.
                If a question doesn't have a clear answer in the text, indicate "No hay información suficiente".
                Preserve the exact structure of the questions object, but add an "answer" field to each question.
                """
            
            # Format specific task questions if available
            task_questions_text = json.dumps(task_questions) if task_questions else "No specific task questions provided"
            
            # Call LLM to match research text with questions
            response = self.llm.chat.completions.create(
                model="openai:gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
                    Questions structure: {json.dumps(questions, ensure_ascii=False)}
                    
                    Task specific questions: {task_questions_text}
                    
                    Research text: 
                    {research_text}
                    
                    Format the research answers according to the question structure, maintaining the exact same structure
                    but adding answers to each question. Return a valid JSON object.
                    """}
                ],
                response_format={"type": "json_object"}
            )
            
            # Parse the response if it's a string
            if isinstance(response, str):
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    logger.error("Error parsing LLM response as JSON")
                    return {"error": "Failed to parse LLM response", "raw_response": response}
            
            # Extract the content from the response object
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Error formatting research answers: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def process_market_research(
        self,
        task: ResearchTask,
        body_json: Dict[str, Any],
        db: Session,
        minio_client: MinioService
    ) -> Dict[str, Any]:
        """
        Process market research
        
        Args:
            task: The ResearchTask object
            body_json: JSON data from the webhook request
            db: Database session
            minio_client: MinIO client
            
        Returns:
            Dict with processing result information
        """
        logger.info(f"Processing market research for task: {task.id}")
        
        # Extract data from the task
        business_id = task.business_idea_id
        research_type = task.research_type
        logger.info(f"Business ID: {business_id}, Research Type: {research_type}")
        
        # Get the business understanding record
        business_understanding = db.query(MarketStateOfArt).filter(
            MarketStateOfArt.id == task.business_understanding_id
        ).first()
        
        if not business_understanding:
            logger.error(f"MarketStateOfArt with ID {task.business_understanding_id} not found")
            return {
                "status": "error",
                "message": f"MarketStateOfArt with ID {task.business_understanding_id} not found"
                }
        
        # Extract the research text and citations
        research_text = body_json.get("text", "")
        citations = body_json.get("citations", [])

        try:
            # Get questions from MinIO
            questions_json = minio_client.get_object_data(f"{business_id}/business-understanding/market_research_questions.json")
            questions = json.loads(questions_json.decode('utf-8')) if questions_json else {}
            
            # If we have task-specific questions, load those
            task_questions = task.get_questions() if task.questions else []
            
            # Call LLM to format the answer data
            # Format depends on whether we're processing state_of_art or market_research
            formatted_response = await self._format_research_answers(
                research_type=research_type,
                questions=questions,
                task_questions=task_questions,
                research_text=research_text
            )
            
            # Format the complete answer data with both original text and formatted answers
            answer_data = {
                "text": research_text,
                "citations": citations,
                "request_id": body_json.get("request_id", task.request_id),
                "business_id": business_id,
                "research_type": str(research_type),
                "search_prompt": body_json.get("search_prompt", ""),
                "timestamp": datetime.now().isoformat(),
                "formatted_answers": formatted_response
            }
            
            # Update task with answer data
            task.add_answer(answer_data)
            task.status = StatusEnum.COMPLETED
            task.completed_at = datetime.now()
            db.commit()
            logger.info(f"Updated task {task.id} with answer data")
            
            # Guardar la tarea individual en MinIO
            task_object_name = f"{business_id}/business-understanding/tasks/{research_type}_{task.id}.json"
            await minio_client.upload_content(
                object_name=task_object_name,
                data=json.dumps(answer_data, indent=2),
                content_type="application/json",
                metadata={
                    "business_id": business_id,
                    "task_id": task.id,
                    "research_type": str(research_type),
                    "depth": task.depth,
                    "chunk_index": task.chunk_index
                }
            )
            logger.info(f"Saved individual task answer to MinIO: {task_object_name}")
            
            # Get all tasks for this business understanding and research type
            all_tasks = db.query(ResearchTask).filter(
                ResearchTask.business_understanding_id == business_understanding.id,
                ResearchTask.research_type == task.research_type
            ).all()
            
            # Check if all tasks are completed
            all_completed = all(t.status == StatusEnum.COMPLETED for t in all_tasks)
            
            if all_completed:
                logger.info(f"All {task.research_type} tasks completed, compiling results")
                
                # Determine the path based on the research type and depth
                object_name = f"{business_id}/business-understanding/"
                if research_type == ResearchTypeEnum.MARKET_RESEARCH:
                    object_name += f"market_research_{task.depth}.json"
                else:
                    object_name += f"state_of_art_{task.depth}.json"
                
                # Collect all answers
                all_answers = {}
                for t in all_tasks:
                    if t.status == StatusEnum.COMPLETED:
                        t_answer = t.get_answer()
                        if t_answer:
                            # Use the task ID as the key
                            all_answers[t.id] = t_answer
                
                # Store the combined answers in MinIO
                await minio_client.upload_content(
                    object_name=object_name,
                    data=json.dumps(all_answers, indent=2),
                    content_type="application/json",
                    metadata={
                        "business_id": business_id,
                        "research_type": str(task.research_type),
                        "depth": task.depth
                    }
                )
                logger.info(f"Saved combined research results to MinIO: {object_name}")
                
                # Update business understanding record
                if research_type == ResearchTypeEnum.MARKET_RESEARCH:
                    business_understanding.market_research_path = object_name
                    business_understanding.market_research_status = StatusEnum.COMPLETED
                else:
                    business_understanding.state_of_art_path = object_name
                    business_understanding.state_of_art_status = StatusEnum.COMPLETED
                
                db.commit()
                logger.info(f"Updated business understanding record with {task.research_type} results")
            
            return {
                "status": "success",
                "message": f"Processed {research_type} research for task {task.id}",
                "business_id": business_id,
                "all_completed": all_completed
            }
            
        except Exception as e:
            logger.error(f"Error processing {research_type} research: {str(e)}", exc_info=True)
            task.status = StatusEnum.FAILED
            task.error_message = str(e)
            db.commit()
            
            return {
                "status": "error",
                "message": f"Error processing {research_type} research: {str(e)}"
            }