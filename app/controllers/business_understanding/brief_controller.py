"""
Brief Controller
Handles business brief logic and report generation
"""
import json
import logging
from typing import Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BriefController:
    """Controller for business brief operations"""
    
    @staticmethod
    def generate_markdown_report(answers: Dict[str, Dict[str, str]]) -> str:
        """
        Generate a markdown report from brief answers
        
        Args:
            answers: Dictionary containing answers organized by phases
            
        Returns:
            str: Markdown formatted report
        """
        try:
            report_lines = [
                "# Reporte de Brief de Negocio",
                "",
                f"**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "---",
                ""
            ]
            
            # Iterate through each phase
            for phase, phase_answers in answers.items():
                report_lines.append(f"## {phase}")
                report_lines.append("")
                
                # Add each question and answer
                for question, answer in phase_answers.items():
                    report_lines.append(f"**{question}**")
                    report_lines.append("")
                    report_lines.append(answer)
                    report_lines.append("")
                    report_lines.append("---")
                    report_lines.append("")
            
            # Add summary section
            report_lines.extend([
                "## Resumen Ejecutivo",
                "",
                "Este brief contiene la información fundamental sobre:",
                "- La definición y propósito del negocio",
                "- Las oportunidades de comunicación identificadas", 
                "- La estrategia de comunicación propuesta",
                "",
                "Utiliza esta información como base para desarrollar tu estrategia de marketing y comunicación.",
                ""
            ])
            
            return "\n".join(report_lines)
            
        except Exception as e:
            logger.error(f"Error generating markdown report: {str(e)}")
            return f"Error al generar el reporte: {str(e)}"
    
    @staticmethod
    def save_brief_to_minio(business_id: str, answers: Dict[str, Dict[str, str]], minio_client) -> str:
        """
        Save brief answers to MinIO storage
        
        Args:
            business_id: ID of the business
            answers: Dictionary containing answers organized by phases
            minio_client: MinIO service client
            
        Returns:
            str: Path where the brief was saved
        """
        try:
            # Create the brief data structure
            brief_data = {
                "business_id": business_id,
                "created_at": datetime.now().isoformat(),
                "phases": answers,
                "metadata": {
                    "total_phases": len(answers),
                    "total_questions": sum(len(phase_answers) for phase_answers in answers.values()),
                    "generation_timestamp": datetime.now().isoformat()
                }
            }
            
            # Define the path in MinIO
            file_path = f"{business_id}/business-understanding/brief.json"
            
            # Upload to MinIO
            minio_client.upload_json(file_path, brief_data)
            
            logger.info(f"Brief saved successfully to MinIO: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving brief to MinIO: {str(e)}")
            raise
    
    @staticmethod
    def map_brief_answers_to_business_model(answers: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        """
        Map brief answers from ETAPA 1 to business model fields
        
        Args:
            answers: Dictionary containing answers organized by phases
            
        Returns:
            Dict: Mapped business model fields
        """
        try:
            business_model_data = {}
            
            # Get ETAPA 1 answers
            etapa1_answers = answers.get("ETAPA 1: ENTENDIMIENTO DEL NEGOCIO", {})
            
            # Mapping logic
            field_mappings = {
                "¿Qué hace la empresa? ¿Cuál es su propósito?": "problem_definition",
                "¿Cuál es su propuesta de valor?": "value_proposition", 
                "¿Qué productos/servicios ofrece y a quiénes?": "products_services",
                "¿Cuál es el cliente ideal?": "customer_persona",
                "¿Qué problema resuelve?": "problem_definition",  # May combine with first question
                "¿Qué los hace diferentes frente a la competencia?": "competitive_advantage",
                "¿Qué desafíos u oportunidades clave enfrentan hoy?": "challenges_opportunities",
                "¿En qué industria se encuentra?": "industry"
            }
            
            # Map answers to business model fields
            for question, answer in etapa1_answers.items():
                field_name = field_mappings.get(question)
                if field_name:
                    # If field already exists, combine the answers
                    if field_name in business_model_data:
                        business_model_data[field_name] += f"\n\n{answer}"
                    else:
                        business_model_data[field_name] = answer
            
            logger.info(f"Mapped {len(business_model_data)} fields to business model")
            return business_model_data
            
        except Exception as e:
            logger.error(f"Error mapping brief answers to business model: {str(e)}")
            return {}
    
    @staticmethod
    def validate_brief_completion(answers: Dict[str, Dict[str, str]], total_questions: int) -> bool:
        """
        Validate if the brief is complete
        
        Args:
            answers: Dictionary containing answers organized by phases
            total_questions: Total number of questions expected
            
        Returns:
            bool: True if brief is complete, False otherwise
        """
        try:
            total_answered = sum(len(phase_answers) for phase_answers in answers.values())
            is_complete = total_answered >= total_questions
            
            logger.info(f"Brief completion validation: {total_answered}/{total_questions} questions answered")
            return is_complete
            
        except Exception as e:
            logger.error(f"Error validating brief completion: {str(e)}")
            return False 