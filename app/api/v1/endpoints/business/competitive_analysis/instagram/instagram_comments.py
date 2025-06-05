from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db
from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.instagram import (
    InstagramUserInfo, 
    InstagramPostInfo,
    InstagramComment,
    InstagramCommentCategory,
    InstagramLDATopic
)
from app.services.business.competitive_analysis.instagram.instagram_scraper import InstagramScraper
from app.services.business.competitive_analysis.instagram.comments.instagram_comment_categorizer import InstagramCommentCategorizer
from app.services.business.competitive_analysis.instagram.comments.instagram_sentiment_emotion_analyzer import InstagramSentimentEmotionAnalyzer
from app.services.business.competitive_analysis.instagram.comments.instagram_topic_modeling import InstagramTopicModeling
from app.services.storage.minio_service import MinioService

# Import TaskIQ task
from app.tasks.instagram_analysis_tasks import complete_instagram_comments_analysis_task
# Import task progress service
from app.services.cache.task_progress_service import get_task_progress_service

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Models for request and response schemas
class ScrapeCommentsRequest(BaseModel):
    post_urls: List[str]
    max_comments: int = 50

class ScrapeCommentsResponse(BaseModel):
    status: str
    message: str
    post_count: int
    comments_count: int
    results: Optional[List[Dict[str, Any]]] = None

class CommentCategorizationRequest(BaseModel):
    username: str
    provider: str = "openai"
    model: str = "openai:gpt-4o-mini"

class CommentCategorizationResponse(BaseModel):
    status: str
    username: str
    total_categories: int
    category_counts: Optional[Dict[str, int]] = None

class SentimentAnalysisRequest(BaseModel):
    username: str

class SentimentAnalysisResponse(BaseModel):
    status: str
    username: str
    total_comments_analyzed: int
    sentiment_file_path: str
    emotion_file_path: str

class TopicModelingRequest(BaseModel):
    username: str
    num_topics: int = 5
    lang: str = "en"

class TopicModelingResponse(BaseModel):
    status: str
    username: str
    total_topics: int
    lda_topics_file_path: str
    wordcloud_file_path: Optional[str] = None

class CompleteCommentsAnalysisRequest(BaseModel):
    username: str
    num_topics: int = 5
    max_comments: int = 50
    provider: str = "openai"
    model: str = "openai:gpt-4o-mini"
    lang: str = "en"
    run_in_background: bool = True

# Import settings
from app.core.config import settings

# Endpoints
@router.post("/{business_id}/scrape-comments", response_model=ScrapeCommentsResponse)
async def scrape_instagram_comments(
    business_id: UUID,
    request: ScrapeCommentsRequest,
    db: Session = Depends(get_db)
):
    """
    Scrape comments from specific Instagram posts.
    
    Args:
        business_id: UUID of the business idea
        request: ScrapeCommentsRequest with post_urls and max_comments parameters
        db: Database session
        
    Returns:
        ScrapeCommentsResponse: Scraped comments information
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Initialize the Instagram scraper
        output_folder = f"{business_id}/competitor-analysis/instagram"
        instagram_scraper = InstagramScraper(
            output_folder=output_folder
        )
        
        # Clean the post URLs to ensure proper format
        clean_urls = []
        for url in request.post_urls:
            # Basic cleaning - remove trailing slashes
            clean_url = url.rstrip('/')
            
            # Ensure URL has proper protocol
            if not (clean_url.startswith('http://') or clean_url.startswith('https://')):
                clean_url = f'https://{clean_url}'
                
            clean_urls.append(clean_url)
        
        # Call the scrape_instagram_comments method
        results = await instagram_scraper.scrape_instagram_comments(
            post_urls=clean_urls,
            max_comments=request.max_comments
        )
        
        # Count total comments retrieved
        total_comments = 0
        if results:
            for result in results:
                total_comments += len(result.get("comments", []))
        
        return ScrapeCommentsResponse(
            status="success",
            message=f"Successfully scraped comments from {len(results)} posts",
            post_count=len(results),
            comments_count=total_comments,
            results=results
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{business_id}/categorize-comments", response_model=CommentCategorizationResponse)
async def categorize_instagram_comments(
    business_id: UUID,
    request: CommentCategorizationRequest,
    db: Session = Depends(get_db)
):
    """
    Categorize Instagram comments for a specific username using an LLM.
    
    Args:
        business_id: UUID of the business idea
        request: CommentCategorizationRequest with username, provider, and model
        db: Database session
        
    Returns:
        CommentCategorizationResponse: Categories generated and counts
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=request.username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {request.username} not found. You may need to scrape this profile first.")
        
        # Initialize the comment categorizer
        output_folder = f"{business_id}/competitor-analysis/instagram"
        comment_categorizer = InstagramCommentCategorizer(
            username=request.username,
            output_folder=output_folder,
            provider=request.provider.split(':')[0] if ':' in request.provider else request.provider,
            model=request.model
        )
        
        # Run the analysis
        total_categories = await comment_categorizer.run_analysis()
        
        # Get category counts from MinIO or database
        category_counts = {}
        categories = db.query(InstagramCommentCategory).filter_by(user_id=instagram_user.id).all()
        if categories:
            for category in categories:
                category_counts[category.category_type] = category.category_count
        
        return CommentCategorizationResponse(
            status="success",
            username=request.username,
            total_categories=total_categories if total_categories else 0,
            category_counts=category_counts
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{business_id}/analyze-sentiment", response_model=SentimentAnalysisResponse)
async def analyze_sentiment_emotions(
    business_id: UUID,
    request: SentimentAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze sentiment and emotions in Instagram comments for a specific username.
    
    Args:
        business_id: UUID of the business idea
        request: SentimentAnalysisRequest with username
        db: Database session
        
    Returns:
        SentimentAnalysisResponse: Analysis results with file paths
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=request.username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {request.username} not found. You may need to scrape this profile first.")
        
        # Initialize the sentiment and emotion analyzer
        output_folder = f"{business_id}/competitor-analysis/instagram"
        sentiment_analyzer = InstagramSentimentEmotionAnalyzer(
            username=request.username,
            output_folder=output_folder
        )
        
        # Run the analysis
        await sentiment_analyzer.analyze_sentiment_and_emotions()
        
        # Get the total number of comments analyzed
        # This could come from a metadata file or the database
        total_comments = db.query(InstagramComment).filter_by(user_id=instagram_user.id).count()
        
        return SentimentAnalysisResponse(
            status="success",
            username=request.username,
            total_comments_analyzed=total_comments,
            sentiment_file_path=f"{output_folder}/sentiment_analysis.json",
            emotion_file_path=f"{output_folder}/emotion_analysis.json"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{business_id}/model-topics", response_model=TopicModelingResponse)
async def model_comment_topics(
    business_id: UUID,
    request: TopicModelingRequest,
    db: Session = Depends(get_db)
):
    """
    Perform topic modeling on Instagram comments for a specific username.
    
    Args:
        business_id: UUID of the business idea
        request: TopicModelingRequest with username, num_topics, and language
        db: Database session
        
    Returns:
        TopicModelingResponse: Topic modeling results with file paths
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=request.username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {request.username} not found. You may need to scrape this profile first.")
        
        # Initialize the topic modeling analyzer
        output_folder = f"{business_id}/competitor-analysis/instagram"
        topic_modeling = InstagramTopicModeling(
            username=request.username,
            output_folder=output_folder,
            num_topics=request.num_topics,
            lang=request.lang
        )
        
        # Run the analysis
        await topic_modeling.run_lda_analysis()
        
        # Get the total number of topics from the database
        topics_count = db.query(InstagramLDATopic).filter_by(user_id=instagram_user.id).count()
        
        return TopicModelingResponse(
            status="success",
            username=request.username,
            total_topics=topics_count if topics_count else request.num_topics,
            lda_topics_file_path=f"{output_folder}/lda_topics.json",
            wordcloud_file_path=f"{output_folder}/wordcloud.png"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{business_id}/complete-comments-analysis")
async def complete_comments_analysis(
    business_id: UUID,
    request: CompleteCommentsAnalysisRequest,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Run a complete analysis on Instagram comments for a specific username using TaskIQ,
    including categorization, sentiment analysis, and topic modeling.
    
    Args:
        business_id: UUID of the business idea
        request: CompleteCommentsAnalysisRequest with all parameters
        background_tasks: Background tasks runner (deprecated, using TaskIQ)
        db: Database session
        
    Returns:
        dict: Analysis initiation status with task_id for progress tracking
    """
    try:
        # Extract parameters from request
        username = request.username
        num_topics = request.num_topics
        max_comments = request.max_comments
        provider = request.provider
        model = request.model
        lang = request.lang
        run_in_background = request.run_in_background
        
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found. You may need to scrape this profile first.")
        
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Get progress service
        progress_service = get_task_progress_service()
        
        # Initialize progress in Redis
        progress_service.set_task_progress(
            task_id=task_id,
            progress=0,
            status="queued"
        )

        # Check if we should run in background (TaskIQ) or synchronously
        if run_in_background:
            # Send task to TaskIQ queue
            try:
                taskiq_task = await complete_instagram_comments_analysis_task.kiq(
                    business_id=str(business_id),
                    username=username,
                    task_id=task_id,
                    num_topics=num_topics,
                    max_comments=max_comments,
                    provider=provider,
                    model=model,
                    lang=lang
                )
                
                logger.info(f"📤 TaskIQ comments analysis task queued with ID: {taskiq_task.task_id} for user {username}")
                
                # Update progress to indicate task was queued and store TaskIQ task ID
                progress_service.update_task_progress(task_id, {
                    "status": "queued",
                    "taskiq_task_id": taskiq_task.task_id
                })
                
                return {
                    "status": "queued",
                    "message": f"Complete comments analysis for {username} queued successfully",
                    "username": username,
                    "business_id": str(business_id),
                    "task_id": task_id
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to queue TaskIQ comments analysis task: {str(e)}")
                progress_service.set_task_failed(task_id, f"Failed to queue task: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to queue comments analysis task: {str(e)}")
        else:
            # Run task synchronously through TaskIQ (wait for result)
            try:
                taskiq_task = await complete_instagram_comments_analysis_task.kiq(
                    business_id=str(business_id),
                    username=username,
                    task_id=task_id,
                    num_topics=num_topics,
                    max_comments=max_comments,
                    provider=provider,
                    model=model,
                    lang=lang
                )
                
                # Wait for result (with timeout)
                result = await taskiq_task.wait_result(timeout=300)  # 5 minutes timeout
                
                if result.is_err:
                    raise HTTPException(status_code=500, detail=f"Comments analysis failed: {result.error}")
                
                return {
                    "status": "completed",
                    "message": f"Complete comments analysis for {username} completed successfully",
                    "username": username,
                    "business_id": str(business_id),
                    "task_id": task_id,
                    "results": result.return_value.get("results", {})
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to execute TaskIQ comments analysis task: {str(e)}")
                progress_service.set_task_failed(task_id, str(e))
                raise HTTPException(status_code=500, detail=f"Comments analysis failed: {str(e)}")

    except Exception as e:
        # If there was a task_id created, update its status
        if 'task_id' in locals():
            progress_service = get_task_progress_service()
            progress_service.set_task_failed(task_id, str(e))
        
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/complete-comments-analysis/task/{task_id}")
async def get_comments_analysis_progress(
    business_id: UUID,
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the progress of complete Instagram comments analysis for a specific task.
    
    Args:
        business_id: UUID of the business idea
        task_id: Task identifier
        db: Database session
        
    Returns:
        dict: Task progress information
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Get progress service
        progress_service = get_task_progress_service()
        
        # Get progress data from Redis
        progress_data = progress_service.get_task_progress(task_id)
        
        if progress_data is None:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "task_id": task_id,
            "progress": progress_data["progress"],
            "status": progress_data["status"],
            "results": progress_data.get("results"),
            "error": progress_data.get("error"),
            "business_id": str(business_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Optional: Endpoint to cancel an ongoing comments analysis
@router.delete("/complete-comments-analysis/task/{task_id}")
async def cancel_comments_analysis(task_id: str, db: Session = Depends(get_db)):
    """
    Cancel an ongoing Instagram comments analysis.
    
    Args:
        task_id: Task identifier
        db: Database session
        
    Returns:
        dict: Cancellation confirmation message
    """
    try:
        # Get progress service
        progress_service = get_task_progress_service()
        
        # Check if task exists
        progress_data = progress_service.get_task_progress(task_id)
        if progress_data is None:
            raise HTTPException(status_code=404, detail="Task not found")

        # Update task status to cancelled
        progress_service.update_task_progress(task_id, {
            "status": "cancelled"
        })
        
        return {"message": "Instagram comments analysis cancelled successfully", "task_id": task_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints para obtener los resultados del análisis
@router.get("/{business_id}/comment-categories/{username}")
async def get_comment_categories(
    business_id: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene las categorías de comentarios generadas para un usuario de Instagram específico.
    
    Args:
        business_id: UUID del business idea
        username: Nombre de usuario de Instagram analizado
        db: Sesión de base de datos
        
    Returns:
        dict: Categorías de comentarios con estadísticas
    """
    try:
        # Verificar si business_id existe
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Verificar si el usuario existe
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found")
        
        # Inicializar servicio MinIO
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        
        # Ruta del archivo
        file_path = f"{business_id}/competitor-analysis/instagram/{username}/dynamic_categorized_comments.json"
        
        # Obtener datos del archivo
        file_data = minio_service.get_object_data(file_path)
        if not file_data:
            raise HTTPException(status_code=404, detail="Comment categories data not found")
        
        # Devolver contenido del archivo
        return Response(
            content=file_data,
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/sentiment-analysis/{username}")
async def get_sentiment_analysis(
    business_id: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene el análisis de sentimiento para un usuario de Instagram específico.
    
    Args:
        business_id: UUID del business idea
        username: Nombre de usuario de Instagram analizado
        db: Sesión de base de datos
        
    Returns:
        dict: Análisis de sentimiento de los comentarios
    """
    try:
        # Verificar si business_id existe
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Verificar si el usuario existe
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found")
        
        # Inicializar servicio MinIO
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        
        # Ruta del archivo
        file_path = f"{business_id}/competitor-analysis/instagram/{username}/sentiment_analysis.json"
        
        # Obtener datos del archivo
        file_data = minio_service.get_object_data(file_path)
        if not file_data:
            raise HTTPException(status_code=404, detail="Sentiment analysis data not found")
        
        # Devolver contenido del archivo
        return Response(
            content=file_data,
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/emotion-analysis/{username}")
async def get_emotion_analysis(
    business_id: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene el análisis de emociones para un usuario de Instagram específico.
    
    Args:
        business_id: UUID del business idea
        username: Nombre de usuario de Instagram analizado
        db: Sesión de base de datos
        
    Returns:
        dict: Análisis de emociones de los comentarios
    """
    try:
        # Verificar si business_id existe
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Verificar si el usuario existe
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found")
        
        # Inicializar servicio MinIO
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        
        # Ruta del archivo
        file_path = f"{business_id}/competitor-analysis/instagram/{username}/emotion_analysis.json"
        
        # Obtener datos del archivo
        file_data = minio_service.get_object_data(file_path)
        if not file_data:
            raise HTTPException(status_code=404, detail="Emotion analysis data not found")
        
        # Devolver contenido del archivo
        return Response(
            content=file_data,
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/topic-analysis/{username}")
async def get_topic_analysis(
    business_id: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene el análisis de temas (LDA) para un usuario de Instagram específico.
    
    Args:
        business_id: UUID del business idea
        username: Nombre de usuario de Instagram analizado
        db: Sesión de base de datos
        
    Returns:
        dict: Temas identificados en los comentarios
    """
    try:
        # Verificar si business_id existe
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Verificar si el usuario existe
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found")
        
        # Inicializar servicio MinIO
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        
        # Ruta del archivo
        file_path = f"{business_id}/competitor-analysis/instagram/{username}/lda_topics.json"
        
        # Obtener datos del archivo
        file_data = minio_service.get_object_data(file_path)
        if not file_data:
            raise HTTPException(status_code=404, detail="Topic analysis data not found")
        
        # Devolver contenido del archivo
        return Response(
            content=file_data,
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/combined-analysis/{username}")
async def get_combined_analysis(
    business_id: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene el análisis combinado de categorías y temas para un usuario de Instagram específico.
    
    Args:
        business_id: UUID del business idea
        username: Nombre de usuario de Instagram analizado
        db: Sesión de base de datos
        
    Returns:
        dict: Análisis combinado con insights
    """
    try:
        # Verificar si business_id existe
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Verificar si el usuario existe
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found")
        
        # Inicializar servicio MinIO
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        
        # Ruta del archivo
        file_path = f"{business_id}/competitor-analysis/instagram/{username}/combined_analysis_report.json"
        
        # Obtener datos del archivo
        file_data = minio_service.get_object_data(file_path)
        if not file_data:
            raise HTTPException(status_code=404, detail="Combined analysis data not found")
        
        # Devolver contenido del archivo
        return Response(
            content=file_data,
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/wordcloud/{username}")
async def get_wordcloud(
    business_id: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene la imagen de nube de palabras (wordcloud) para un usuario de Instagram específico.
    
    Args:
        business_id: UUID del business idea
        username: Nombre de usuario de Instagram analizado
        db: Sesión de base de datos
        
    Returns:
        bytes: Imagen PNG de la nube de palabras
    """
    try:
        # Verificar si business_id existe
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Verificar si el usuario existe
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found")
        
        # Inicializar servicio MinIO
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        
        # Ruta del archivo
        file_path = f"{business_id}/competitor-analysis/instagram/{username}/wordcloud.png"
        
        # Obtener datos del archivo
        file_data = minio_service.get_object_data(file_path)
        if not file_data:
            raise HTTPException(status_code=404, detail="Wordcloud image not found")
        
        # Devolver la imagen
        return Response(
            content=file_data,
            media_type="image/png"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 