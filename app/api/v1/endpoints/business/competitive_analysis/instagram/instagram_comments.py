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
    Run a complete analysis on Instagram comments for a specific username,
    including categorization, sentiment analysis, and topic modeling.
    
    Args:
        business_id: UUID of the business idea
        request: CompleteCommentsAnalysisRequest with all parameters
        background_tasks: Background tasks runner
        db: Database session
        
    Returns:
        dict: Analysis initiation status
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
        
        # Define the analysis function to run in the background
        async def run_complete_analysis():
            output_folder = f"{business_id}/competitor-analysis/instagram"
            
            try:
                # 1. Run comment categorization
                comment_categorizer = InstagramCommentCategorizer(
                    username=username,
                    output_folder=output_folder,
                    provider=provider.split(':')[0] if ':' in provider else provider,
                    model=model
                )
                await comment_categorizer.run_analysis()
                
                # 2. Run sentiment and emotion analysis
                sentiment_analyzer = InstagramSentimentEmotionAnalyzer(
                    username=username,
                    output_folder=output_folder
                )
                await sentiment_analyzer.analyze_sentiment_and_emotions()
                
                # 3. Run topic modeling
                topic_modeling = InstagramTopicModeling(
                    username=username,
                    output_folder=output_folder,
                    num_topics=num_topics,
                    lang=lang
                )
                await topic_modeling.run_lda_analysis()
                
                # Update status in database
                # This would typically update a job status table
                
            except Exception as e:
                # Log the error and update status in database
                print(f"Error in complete analysis for {username}: {str(e)}")
        
        # Check if we should run in background or synchronously based on the parameter
        if run_in_background and background_tasks:
            background_tasks.add_task(run_complete_analysis)
            return {
                "status": "processing",
                "message": f"Complete comments analysis for {username} started in background",
                "username": username,
                "business_id": str(business_id)
            }
        else:
            # Run synchronously
            await run_complete_analysis()
            return {
                "status": "completed",
                "message": f"Complete comments analysis for {username} completed",
                "username": username,
                "business_id": str(business_id)
            }

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
        minio_service = MinioService(bucket_name="lattice-businesses")
        
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
        minio_service = MinioService(bucket_name="lattice-businesses")
        
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
        minio_service = MinioService(bucket_name="lattice-businesses")
        
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
        minio_service = MinioService(bucket_name="lattice-businesses")
        
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
        minio_service = MinioService(bucket_name="lattice-businesses")
        
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
        minio_service = MinioService(bucket_name="lattice-businesses")
        
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