import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import json

from .broker import broker
from app.controllers.competitive_analysis.instagram_competitor_controller import InstagramCompetitorController
from app.db.session import SessionLocal
from app.services.cache.task_progress_service import get_task_progress_service
from app.models.business.competitive_analysis.competitors import Competitor
from app.models.business.competitive_analysis.instagram import InstagramUserInfo, InstagramPostInfo
from app.models.business.business_idea import BusinessIdea
from app.services.business.competitive_analysis.instagram.comments.instagram_comment_categorizer import InstagramCommentCategorizer
from app.services.business.competitive_analysis.instagram.comments.instagram_sentiment_emotion_analyzer import InstagramSentimentEmotionAnalyzer
from app.services.business.competitive_analysis.instagram.comments.instagram_topic_modeling import InstagramTopicModeling
from app.services.business.competitive_analysis.instagram.instagram_image_analyzer import InstagramImageAnalyzer
from app.services.storage.minio_service import MinioService
from app.core.config import settings
from app.services.business.competitive_analysis.instagram.instagram_statistics import InstagramStatistics

# Configure logging
logger = logging.getLogger(__name__)

@broker.task
async def run_instagram_full_analysis_task(
    business_id: str,
    task_id: str,
    competitor_ids: Optional[List[str]] = None,
    results_limit: int = 10,
    max_comments: int = 5
) -> Dict[str, Any]:
    """
    TaskIQ task for executing full Instagram analysis in the background.
    
    Args:
        business_id: Business idea ID
        task_id: Task identifier for progress tracking
        competitor_ids: Optional list of competitor IDs to analyze
        results_limit: Maximum number of posts to extract per Instagram account
        max_comments: Maximum number of comments to extract per post
        
    Returns:
        Dict with task result information
    """
    logger.info(f"🔍 Starting Instagram analysis task for business {business_id}, task {task_id}")
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    # Mark task as processing
    progress_service.set_task_progress(
        task_id=task_id,
        progress=5,
        status="processing"
    )
    
    db = None
    try:
        # Create database session
        db = SessionLocal()
        
        # Get competitors for this business idea
        competitors_query = db.query(Competitor).filter(
            Competitor.business_idea_id == business_id
        )
        
        # Filter by competitor_ids if provided
        if competitor_ids:
            competitors_query = competitors_query.filter(
                Competitor.id.in_(competitor_ids)
            )
            
        competitors = competitors_query.all()
        
        # Filter out competitors without Instagram URLs
        competitors = [c for c in competitors if c.instagram_url]
        
        if not competitors:
            logger.warning(f"No competitors with Instagram URLs found for business {business_id}")
            progress_service.set_task_completed(
                task_id=task_id,
                results={"message": "No competitors with Instagram URLs found"}
            )
            return {
                "status": "completed",
                "results": {"message": "No competitors with Instagram URLs found"},
                "business_id": business_id,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat(),
                "task_type": "instagram_analysis"
            }

        total_competitors = len(competitors)
        completed = 0
        results = {}
        
        # Initialize the controller
        controller = InstagramCompetitorController(business_id=business_id)
        
        logger.info(f"Processing {total_competitors} competitors with Instagram URLs")
        
        for competitor in competitors:
            try:
                instagram_url = competitor.instagram_url
                username = controller.extract_instagram_username(instagram_url)
                
                if username:
                    logger.info(f"Processing Instagram analysis for {username} (competitor: {competitor.competitor_name})")
                    
                    # Use the controller to analyze this competitor
                    result = await controller.analyze_instagram_competitor(
                        username=username,
                        competitor_id=competitor.id,
                        results_limit=results_limit,
                        max_comments=max_comments
                    )
                    
                    results[competitor.competitor_name] = {
                        "instagram_username": username,
                        "competitor_id": competitor.id,
                        "status": result.get("status", "completed"),
                        "message": result.get("message", "")
                    }
                    completed += 1
                else:
                    logger.warning(f"Invalid Instagram URL for competitor: {competitor.competitor_name}")
                    results[competitor.competitor_name] = {
                        "instagram_username": None,
                        "competitor_id": competitor.id,
                        "status": "skipped",
                        "reason": "Invalid Instagram URL"
                    }
                    completed += 1
            
            except Exception as e:
                logger.error(f"Error processing competitor {competitor.competitor_name}: {str(e)}")
                results[competitor.competitor_name] = {
                    "instagram_username": username if 'username' in locals() else None,
                    "competitor_id": competitor.id,
                    "status": "failed",
                    "error": str(e)
                }
                completed += 1
            
            # Update progress
            progress = int(5 + (completed / total_competitors) * 90)  # 5-95% range
            progress_service.set_task_progress(
                task_id=task_id,
                progress=progress,
                status="processing",
                results=results
            )
            
            logger.info(f"Progress: {completed}/{total_competitors} competitors processed ({progress}%)")

        # Check if all competitors are completed or in research_in_progress state
        all_completed = all(
            result.get("status") != "research_in_progress" 
            for result in results.values()
        )
        
        # Determine final status
        if all_completed:
            progress_service.set_task_completed(
                task_id=task_id,
                results=results
            )
            final_status = "completed"
        else:
            # Some competitors are still in research_in_progress
            progress_service.set_task_progress(
                task_id=task_id,
                progress=95,
                status="waiting_for_research",
                results=results
            )
            final_status = "waiting_for_research"
        
        logger.info(f"✅ Instagram analysis task completed for business {business_id}, task {task_id} with status: {final_status}")
        
        return {
            "status": final_status,
            "results": results,
            "business_id": business_id,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "instagram_analysis"
        }
        
    except Exception as e:
        logger.error(f"❌ Instagram analysis task failed for business {business_id}, task {task_id}: {str(e)}")
        
        # Mark task as failed
        progress_service.set_task_failed(
            task_id=task_id,
            error=str(e)
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "business_id": business_id,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "instagram_analysis"
        }
    finally:
        if db:
            db.close()

@broker.task
async def complete_instagram_comments_analysis_task(
    business_id: str,
    username: str,
    task_id: str,
    num_topics: int = 5,
    max_comments: int = 100,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    lang: str = "es"
) -> Dict[str, Any]:
    """
    TaskIQ task for running complete Instagram comments analysis.
    
    Args:
        business_id: Business idea ID
        username: Instagram username to analyze
        task_id: Task identifier for progress tracking
        num_topics: Number of topics for LDA analysis
        max_comments: Maximum number of comments to analyze
        provider: LLM provider for categorization
        model: LLM model for categorization
        lang: Language for analysis
        
    Returns:
        Dict with task result information
    """
    logger.info(f"🔍 Starting complete comments analysis task for username {username}, business {business_id}, task {task_id}")
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    # Mark task as processing
    progress_service.set_task_progress(
        task_id=task_id,
        progress=10,
        status="processing"
    )
    
    db = None
    try:
        # Create database session
        db = SessionLocal()
        
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            error_msg = "Business idea not found"
            logger.error(f"❌ {error_msg} for business {business_id}")
            progress_service.set_task_failed(task_id, error_msg)
            return {
                "status": "failed",
                "error": error_msg,
                "business_id": business_id,
                "username": username,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat(),
                "task_type": "instagram_comments_analysis"
            }
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            error_msg = f"Instagram user {username} not found. You may need to scrape this profile first."
            logger.error(f"❌ {error_msg}")
            progress_service.set_task_failed(task_id, error_msg)
            return {
                "status": "failed",
                "error": error_msg,
                "business_id": business_id,
                "username": username,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat(),
                "task_type": "instagram_comments_analysis"
            }
        
        output_folder = f"{business_id}/competitor-analysis/instagram"
        analysis_results = {}
        
        # 1. Run comment categorization (33% progress)
        logger.info(f"📊 Running comment categorization for {username}")
        progress_service.set_task_progress(
            task_id=task_id,
            progress=15,
            status="processing",
            results={"current_step": "categorization", "username": username}
        )
        
        try:
            comment_categorizer = InstagramCommentCategorizer(
                username=username,
                output_folder=output_folder,
                provider=provider.split(':')[0] if ':' in provider else provider,
                model=model
            )
            categories_result = await comment_categorizer.run_analysis()
            analysis_results["categorization"] = {
                "status": "completed",
                "result": categories_result
            }
            logger.info(f"✅ Comment categorization completed for {username}")
        except Exception as e:
            logger.error(f"❌ Error in categorization for {username}: {str(e)}")
            analysis_results["categorization"] = {
                "status": "failed",
                "error": str(e)
            }
        
        progress_service.set_task_progress(
            task_id=task_id,
            progress=40,
            status="processing",
            results={"current_step": "sentiment_analysis", "username": username, "categorization": analysis_results["categorization"]}
        )
        
        # 2. Run sentiment and emotion analysis (66% progress)
        logger.info(f"🎭 Running sentiment and emotion analysis for {username}")
        try:
            sentiment_analyzer = InstagramSentimentEmotionAnalyzer(
                username=username,
                output_folder=output_folder
            )
            await sentiment_analyzer.analyze_sentiment_and_emotions()
            analysis_results["sentiment_emotion"] = {
                "status": "completed",
                "sentiment_path": f"{output_folder}/sentiment_analysis.json",
                "emotion_path": f"{output_folder}/emotion_analysis.json"
            }
            logger.info(f"✅ Sentiment and emotion analysis completed for {username}")
        except Exception as e:
            logger.error(f"❌ Error in sentiment analysis for {username}: {str(e)}")
            analysis_results["sentiment_emotion"] = {
                "status": "failed",
                "error": str(e)
            }
        
        progress_service.set_task_progress(
            task_id=task_id,
            progress=70,
            status="processing",
            results={"current_step": "topic_modeling", "username": username, **analysis_results}
        )
        
        # 3. Run topic modeling (100% progress)
        logger.info(f"🧭 Running topic modeling for {username}")
        try:
            topic_modeling = InstagramTopicModeling(
                username=username,
                output_folder=output_folder,
                num_topics=num_topics,
                lang=lang
            )
            await topic_modeling.run_lda_analysis()
            analysis_results["topic_modeling"] = {
                "status": "completed",
                "topics_count": num_topics,
                "wordcloud_path": f"{output_folder}/wordcloud.png",
                "topics_json_path": f"{output_folder}/lda_topics.json"
            }
            logger.info(f"✅ Topic modeling completed for {username}")
        except Exception as e:
            logger.error(f"❌ Error in topic modeling for {username}: {str(e)}")
            analysis_results["topic_modeling"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Mark task as completed
        progress_service.set_task_completed(
            task_id=task_id,
            results={
                "username": username,
                "analysis_results": analysis_results,
                "output_folder": output_folder
            }
        )
        
        logger.info(f"✅ Complete comments analysis task completed for username {username}, business {business_id}, task {task_id}")
        
        return {
            "status": "completed",
            "results": {
                "username": username,
                "analysis_results": analysis_results,
                "output_folder": output_folder
            },
            "business_id": business_id,
            "username": username,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "instagram_comments_analysis"
        }
        
    except Exception as e:
        logger.error(f"❌ Complete comments analysis task failed for username {username}, business {business_id}, task {task_id}: {str(e)}")
        
        # Mark task as failed
        progress_service.set_task_failed(
            task_id=task_id,
            error=str(e)
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "business_id": business_id,
            "username": username,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "instagram_comments_analysis"
        }
    finally:
        if db:
            db.close()

@broker.task
async def complete_instagram_image_analysis_task(
    business_id: str,
    username: str,
    task_id: str,
    posts_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    TaskIQ task for running complete Instagram image analysis.
    
    Args:
        business_id: Business idea ID
        username: Instagram username to analyze
        task_id: Task identifier for progress tracking
        posts_limit: Optional limit on number of posts to analyze
        
    Returns:
        Dict with task result information
    """
    logger.info(f"🔍 Starting complete image analysis task for username {username}, business {business_id}, task {task_id}")
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    # Mark task as processing
    progress_service.set_task_progress(
        task_id=task_id,
        progress=10,
        status="processing"
    )
    
    db = None
    try:
        # Create database session
        db = SessionLocal()
        
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            error_msg = "Business idea not found"
            logger.error(f"❌ {error_msg} for business {business_id}")
            progress_service.set_task_failed(task_id, error_msg)
            return {
                "status": "failed",
                "error": error_msg,
                "business_id": business_id,
                "username": username,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat(),
                "task_type": "instagram_image_analysis"
            }
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            error_msg = f"Instagram user {username} not found. You may need to scrape this profile first."
            logger.error(f"❌ {error_msg}")
            progress_service.set_task_failed(task_id, error_msg)
            return {
                "status": "failed",
                "error": error_msg,
                "business_id": business_id,
                "username": username,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat(),
                "task_type": "instagram_image_analysis"
            }
        
        output_folder = f"{business_id}/competitor-analysis/instagram"
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not openai_api_key:
            error_msg = "OpenAI API key not found in environment variables"
            logger.error(f"❌ {error_msg}")
            progress_service.set_task_failed(task_id, error_msg)
            return {
                "status": "failed",
                "error": error_msg,
                "business_id": business_id,
                "username": username,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat(),
                "task_type": "instagram_image_analysis"
            }
        
        # Initialize Instagram Image Analyzer
        analyzer = InstagramImageAnalyzer(
            output_folder=output_folder, 
            api_key=openai_api_key
        )
        
        # Update progress - starting analysis
        progress_service.set_task_progress(
            task_id=task_id,
            progress=20,
            status="processing",
            results={"current_step": "fetching_posts", "username": username}
        )
        
        # Get posts data from MinIO
        logger.info(f"📂 Fetching posts data for {username}")
        try:
            minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
            posts_object_name = f"{output_folder}/{username}/instagram_posts.json"
            
            # Get JSON data from MinIO
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                error_msg = f"Could not retrieve posts data from {posts_object_name}"
                logger.error(f"❌ {error_msg}")
                progress_service.set_task_failed(task_id, error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "business_id": business_id,
                    "username": username,
                    "task_id": task_id,
                    "completed_at": datetime.now().isoformat(),
                    "task_type": "instagram_image_analysis"
                }
                
            # Parse JSON data
            posts = json.loads(posts_data.decode('utf-8'))
            if not posts or not isinstance(posts, list):
                error_msg = f"Invalid posts data format. Expected a list, got {type(posts)}"
                logger.error(f"❌ {error_msg}")
                progress_service.set_task_failed(task_id, error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "business_id": business_id,
                    "username": username,
                    "task_id": task_id,
                    "completed_at": datetime.now().isoformat(),
                    "task_type": "instagram_image_analysis"
                }
            
            # Limit posts if requested
            if posts_limit and posts_limit > 0:
                posts = posts[:posts_limit]
                
            logger.info(f"📊 Processing {len(posts)} posts for image analysis")
            
        except Exception as e:
            error_msg = f"Error fetching posts data: {str(e)}"
            logger.error(f"❌ {error_msg}")
            progress_service.set_task_failed(task_id, error_msg)
            return {
                "status": "failed",
                "error": error_msg,
                "business_id": business_id,
                "username": username,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat(),
                "task_type": "instagram_image_analysis"
            }
        
        analysis_results = {}
        
        # Step 1: Process posts images (30-70% progress)
        logger.info(f"🖼️  Processing posts images for {username}")
        progress_service.set_task_progress(
            task_id=task_id,
            progress=30,
            status="processing",
            results={"current_step": "processing_posts_images", "username": username, "posts_count": len(posts)}
        )
        
        try:
            posts_results = await analyzer.process_posts_images(username, posts)
            analysis_results["posts_images"] = {
                "status": "completed",
                "posts_processed": len(posts),
                "results": posts_results
            }
            logger.info(f"✅ Posts images processing completed for {username}")
        except Exception as e:
            logger.error(f"❌ Error processing posts images for {username}: {str(e)}")
            analysis_results["posts_images"] = {
                "status": "failed",
                "error": str(e)
            }
        
        progress_service.set_task_progress(
            task_id=task_id,
            progress=70,
            status="processing",
            results={"current_step": "saving_to_database", "username": username, "posts_images": analysis_results["posts_images"]}
        )
        
        # Step 2: Save analysis to database
        logger.info(f"💾 Saving analysis results to database for {username}")
        try:
            if analysis_results["posts_images"]["status"] == "completed":
                await analyzer.save_analysis_to_database(
                    db=db,
                    business_id=str(business_id),
                    instagram_username=username,
                    analysis_data=analysis_results["posts_images"]["results"]
                )
                analysis_results["database_save"] = {
                    "status": "completed"
                }
                logger.info(f"✅ Database save completed for {username}")
            else:
                analysis_results["database_save"] = {
                    "status": "skipped",
                    "reason": "Posts images processing failed"
                }
        except Exception as e:
            logger.error(f"❌ Error saving to database for {username}: {str(e)}")
            analysis_results["database_save"] = {
                "status": "failed",
                "error": str(e)
            }
        
        progress_service.set_task_progress(
            task_id=task_id,
            progress=85,
            status="processing",
            results={"current_step": "analyzing_feed", "username": username, **analysis_results}
        )
        
        # Step 3: Analyze Instagram feed (85-100% progress)
        logger.info(f"📈 Analyzing Instagram feed for {username}")
        try:
            feed_results = await analyzer.analyze_instagram_feed(username, posts)
            analysis_results["feed_analysis"] = {
                "status": "completed",
                "results": feed_results
            }
            logger.info(f"✅ Feed analysis completed for {username}")
        except Exception as e:
            logger.error(f"❌ Error analyzing feed for {username}: {str(e)}")
            analysis_results["feed_analysis"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Mark task as completed
        progress_service.set_task_completed(
            task_id=task_id,
            results={
                "username": username,
                "analysis_results": analysis_results,
                "posts_processed": len(posts),
                "output_folder": output_folder
            }
        )
        
        logger.info(f"✅ Complete image analysis task completed for username {username}, business {business_id}, task {task_id}")
        
        return {
            "status": "completed",
            "results": {
                "username": username,
                "analysis_results": analysis_results,
                "posts_processed": len(posts),
                "output_folder": output_folder
            },
            "business_id": business_id,
            "username": username,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "instagram_image_analysis"
        }
        
    except Exception as e:
        logger.error(f"❌ Complete image analysis task failed for username {username}, business {business_id}, task {task_id}: {str(e)}")
        
        # Mark task as failed
        progress_service.set_task_failed(
            task_id=task_id,
            error=str(e)
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "business_id": business_id,
            "username": username,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "instagram_image_analysis"
        }
    finally:
        if db:
            db.close()

@broker.task
async def complete_instagram_statistics_analysis_task(
    business_id: str,
    username: str,
    task_id: str,
    post_limit: int = 50,
    image_limit: int = 10
) -> Dict[str, Any]:
    """
    TaskIQ task for running complete Instagram statistics analysis.
    
    Args:
        business_id: Business idea ID
        username: Instagram username to analyze
        task_id: Task identifier for progress tracking
        post_limit: Maximum number of posts to analyze
        image_limit: Maximum number of images to analyze per post
        
    Returns:
        Dict with task result information
    """
    logger.info(f"🔍 Starting complete statistics analysis task for username {username}, business {business_id}, task {task_id}")
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    # Mark task as processing
    progress_service.set_task_progress(
        task_id=task_id,
        progress=10,
        status="processing"
    )
    
    db = None
    try:
        # Create database session
        db = SessionLocal()
        
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            error_msg = "Business idea not found"
            logger.error(f"❌ {error_msg} for business {business_id}")
            progress_service.set_task_failed(task_id, error_msg)
            return {
                "status": "failed",
                "error": error_msg,
                "business_id": business_id,
                "username": username,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat(),
                "task_type": "instagram_statistics_analysis"
            }
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            error_msg = f"Instagram user {username} not found. You may need to scrape this profile first."
            logger.error(f"❌ {error_msg}")
            progress_service.set_task_failed(task_id, error_msg)
            return {
                "status": "failed",
                "error": error_msg,
                "business_id": business_id,
                "username": username,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat(),
                "task_type": "instagram_statistics_analysis"
            }
        
        base_folder = f"{business_id}/competitor-analysis/instagram"
        output_folder = f"{base_folder}/{username}"
        analysis_results = {}
        
        # Update progress - starting data preparation
        progress_service.set_task_progress(
            task_id=task_id,
            progress=20,
            status="processing",
            results={"current_step": "preparing_data", "username": username}
        )
        
        # Step 1: Prepare posts data (20-40% progress)
        logger.info(f"📂 Preparing posts data for {username}")
        try:
            minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
            posts_object_name = f"{base_folder}/{username}/instagram_posts.json"
            
            # Get JSON data from MinIO
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                error_msg = f"Could not retrieve posts data from {posts_object_name}"
                logger.error(f"❌ {error_msg}")
                progress_service.set_task_failed(task_id, error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "business_id": business_id,
                    "username": username,
                    "task_id": task_id,
                    "completed_at": datetime.now().isoformat(),
                    "task_type": "instagram_statistics_analysis"
                }
            
            # Copy the data to the expected location for the statistics generator
            await minio_service.upload_content(
                object_name=f"{output_folder}/img_posts.json",
                data=posts_data,
                content_type="application/json"
            )
            
            # Parse JSON data for further processing
            posts = json.loads(posts_data.decode('utf-8'))
            if not posts or not isinstance(posts, list):
                error_msg = f"Invalid posts data format. Expected a list, got {type(posts)}"
                logger.error(f"❌ {error_msg}")
                progress_service.set_task_failed(task_id, error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "business_id": business_id,
                    "username": username,
                    "task_id": task_id,
                    "completed_at": datetime.now().isoformat(),
                    "task_type": "instagram_statistics_analysis"
                }
            
            analysis_results["data_preparation"] = {
                "status": "completed",
                "posts_count": len(posts)
            }
            logger.info(f"✅ Data preparation completed for {username}")
            
        except Exception as e:
            logger.error(f"❌ Error preparing data for {username}: {str(e)}")
            analysis_results["data_preparation"] = {
                "status": "failed",
                "error": str(e)
            }
        
        progress_service.set_task_progress(
            task_id=task_id,
            progress=40,
            status="processing",
            results={"current_step": "loading_database", "username": username, "data_preparation": analysis_results["data_preparation"]}
        )
        
        # Step 2: Ensure posts exist in database (40-60% progress)
        logger.info(f"💾 Loading posts into database for {username}")
        try:
            post_count = db.query(InstagramPostInfo).filter_by(instagram_user_id=instagram_user.id).count()
            
            if post_count == 0:
                # Load posts into the database from the JSON data
                for post in posts:
                    # Check if we already have this post
                    existing_post = db.query(InstagramPostInfo).filter_by(
                        id_post=post.get("id"),
                        instagram_user_id=instagram_user.id
                    ).first()
                    
                    if not existing_post:
                        # Create new post record
                        new_post = InstagramPostInfo(
                            instagram_user_id=instagram_user.id,
                            id_post=post.get("id"),
                            type_post=post.get("type"),
                            caption=post.get("caption", ""),
                            likes_count=post.get("likesCount", 0),
                            comments_count=post.get("commentsCount", 0),
                            post_timestamp=post.get("timestamp"),
                            url_post=post.get("url", "")
                        )
                        db.add(new_post)
                
                db.commit()
                analysis_results["database_loading"] = {
                    "status": "completed",
                    "posts_loaded": len(posts)
                }
            else:
                analysis_results["database_loading"] = {
                    "status": "skipped",
                    "reason": "Posts already exist in database",
                    "existing_posts": post_count
                }
            
            logger.info(f"✅ Database loading completed for {username}")
            
        except Exception as e:
            logger.error(f"❌ Error loading posts to database for {username}: {str(e)}")
            analysis_results["database_loading"] = {
                "status": "failed",
                "error": str(e)
            }
        
        progress_service.set_task_progress(
            task_id=task_id,
            progress=60,
            status="processing",
            results={"current_step": "generating_statistics", "username": username, **analysis_results}
        )
        
        # Step 3: Generate statistics (60-100% progress)
        logger.info(f"📊 Generating statistics for {username}")
        try:
            # Initialize the Instagram statistics analyzer
            statistics = InstagramStatistics(
                username=username,
                post_limit=post_limit,
                image_limit=image_limit,
                output_folder=output_folder
            )
            
            # Generate statistics
            stats_file_path = await statistics.generate_statistics()
            
            if stats_file_path:
                # Read the generated statistics to include in results
                statistics_data = minio_service.get_object_data(f"{output_folder}/statistics.json")
                stats = {}
                
                if statistics_data:
                    stats = json.loads(statistics_data.decode('utf-8'))
                
                analysis_results["statistics_generation"] = {
                    "status": "completed",
                    "stats_file_path": stats_file_path,
                    "statistics_summary": {
                        "total_posts": stats.get('total_posts', 0),
                        "total_followers": stats.get('total_followers', 0),
                        "avg_likes_per_post": stats.get('avg_likes_per_post', 0.0),
                        "avg_comments_per_post": stats.get('avg_comments_per_post', 0.0),
                        "avg_engagement_rate": stats.get('avg_engagement_rate', 0.0)
                    }
                }
                logger.info(f"✅ Statistics generation completed for {username}")
            else:
                analysis_results["statistics_generation"] = {
                    "status": "failed",
                    "error": "Failed to generate statistics file"
                }
                
        except Exception as e:
            logger.error(f"❌ Error generating statistics for {username}: {str(e)}")
            analysis_results["statistics_generation"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Mark task as completed
        progress_service.set_task_completed(
            task_id=task_id,
            results={
                "username": username,
                "analysis_results": analysis_results,
                "post_limit": post_limit,
                "image_limit": image_limit,
                "output_folder": output_folder
            }
        )
        
        logger.info(f"✅ Complete statistics analysis task completed for username {username}, business {business_id}, task {task_id}")
        
        return {
            "status": "completed",
            "results": {
                "username": username,
                "analysis_results": analysis_results,
                "post_limit": post_limit,
                "image_limit": image_limit,
                "output_folder": output_folder
            },
            "business_id": business_id,
            "username": username,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "instagram_statistics_analysis"
        }
        
    except Exception as e:
        logger.error(f"❌ Complete statistics analysis task failed for username {username}, business {business_id}, task {task_id}: {str(e)}")
        
        # Mark task as failed
        progress_service.set_task_failed(
            task_id=task_id,
            error=str(e)
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "business_id": business_id,
            "username": username,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "instagram_statistics_analysis"
        }
    finally:
        if db:
            db.close() 