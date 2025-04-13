from sqlalchemy.orm import Session
from datetime import datetime
import logging
import json
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, BusinessModel
from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus
from app.services.storage.minio_service import MinioService
from app.db.session import SessionLocal

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BusinessCompetitorController:
    """
    Controller para el análisis de competidores de negocio.
    Maneja la generación de preguntas y la investigación de competidores.
    """
    
    def __init__(self, business_id: str):
        """
        Inicializa el controlador con el ID del negocio.
        
        Args:
            business_id (str): ID del negocio
        """
        self.business_id = business_id
    
    async def run_competitor_analysis(
        self,
        minio_service,
        business_model_data: dict,
        business_model_id: str,
        request
    ) -> dict:
        """
        Ejecuta el análisis de competidores utilizando los datos del modelo de negocio
        
        Args:
            minio_service: Instancia de MinioService
            business_model_data (dict): Datos del modelo de negocio
            business_model_id (str): ID del modelo de negocio
            request: Parámetros de solicitud de análisis
            
        Returns:
            dict: Resultados del análisis con competidores y preguntas
        """
        try:
            # Crear instancia del analizador de negocios
            analyzer = EnhancedBusinessAnalyzer(
                business_model=BusinessModel(**business_model_data),
                lang=request.language,
                validator_provider=request.validator_provider,
                validator_model=request.validator_model
            )

            # Generar preguntas de análisis de competidores
            questions = analyzer.generate_competitor_questions()

            # Investigar competidores
            competitors = await analyzer.research_competitors(
                prompt_search=request.search_prompt
            )

            # Almacenar resultados en MinIO
            results = {
                "competitors": competitors,
                "analysis_questions": questions,
                "business_model_summary": business_model_data
            }

            # Guardar resultados en MinIO
            results_filename = f"analysis_results_{business_model_id}.json"
            await minio_service.upload_json(results_filename, results)

            return results

        except Exception as e:
            logger.error(f"Error en análisis de competidores: {str(e)}")
            raise Exception(f"Error ejecutando análisis de competidores: {str(e)}")

    async def generate_competitor_questions(self, business_model, lang="en"):
        """
        Genera preguntas de análisis de competidores.
        
        Args:
            business_model: Instancia de BusinessModel
            lang: Código de idioma (default: "en")
            
        Returns:
            list: Lista de preguntas de análisis
        """
        try:
            analyzer = EnhancedBusinessAnalyzer(
                business_model=business_model,
                lang=lang,
                max_depth=1
            )
            
            questions = analyzer.generate_competitor_questions()
            return questions
            
        except Exception as e:
            logger.error(f"Error generando preguntas de competidores: {str(e)}")
            raise Exception(f"Error generando preguntas de competidores: {str(e)}")
    
    async def research_competitors_async(
        self,
        prompt_search: dict,
        business_id: str,
        request_id: str,
        business_model: dict,
        lang: str = "en"
    ):
        """
        Investiga competidores de forma asíncrona.
        
        Args:
            prompt_search: Prompt de búsqueda para la investigación de competidores
            business_id: ID del negocio
            request_id: ID de la solicitud de investigación
            business_model: Modelo de negocio
            lang: Idioma (predeterminado: "en")
        """
        try:
            # Crear sesión de base de datos
            db = SessionLocal()
            
            # Crear instancia del analizador
            analyzer = EnhancedBusinessAnalyzer(
                business_model=business_model,
                lang=lang,
                max_depth=1,
                db=db
            )
            
            # Pasar la tarea al método de investigación de competidores asíncrono del analizador
            await analyzer.research_competitors_async(
                prompt_search=prompt_search,
                business_id=business_id,
                request_id=request_id
            )
            
            # Cerrar sesión de base de datos al terminar
            db.close()
            
        except Exception as e:
            logger.error(f"Error en investigación de competidores asíncrona: {str(e)}")
            # Asegurarse de cerrar la sesión de base de datos incluso en caso de error
            if 'db' in locals():
                db.close() 