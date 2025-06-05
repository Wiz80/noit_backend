import json
import redis
import logging
from typing import Dict, Any, Optional
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

class TaskProgressService:
    """Service for managing task progress using Redis"""
    
    def __init__(
        self, 
        host: str = None,
        port: int = None,
        db: int = None,
        password: str = None,
        default_ttl: int = 3600  # 1 hour in seconds
    ):
        # Use settings if parameters not provided
        self.redis = redis.Redis(
            host=host or settings.REDIS_HOST,
            port=port or settings.REDIS_PORT,
            db=db or settings.REDIS_DB,
            password=password or settings.REDIS_PASSWORD,
            decode_responses=True
        )
        self.default_ttl = default_ttl
        logger.info(f"Task progress service initialized with Redis host: {host or settings.REDIS_HOST}")
    
    def _get_task_key(self, task_id: str) -> str:
        """Get Redis key for a task progress"""
        return f"task:progress:{task_id}"
    
    def set_task_progress(
        self, 
        task_id: str, 
        progress: int, 
        status: str, 
        results: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        taskiq_task_id: Optional[str] = None
    ) -> bool:
        """
        Set task progress in Redis
        
        Args:
            task_id: ID of the task
            progress: Progress percentage (0-100)
            status: Status of the task (queued, processing, completed, failed)
            results: Optional results data
            error: Optional error message
            taskiq_task_id: Optional TaskIQ task ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            task_data = {
                "progress": progress,
                "status": status,
                "results": results or {},
                "error": error,
                "taskiq_task_id": taskiq_task_id
            }
            
            task_key = self._get_task_key(task_id)
            self.redis.set(task_key, json.dumps(task_data), ex=self.default_ttl)
            
            logger.info(f"Set progress for task {task_id}: {progress}% - {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting task progress for {task_id}: {str(e)}")
            return False
    
    def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task progress from Redis
        
        Args:
            task_id: ID of the task
            
        Returns:
            Task progress data or None if not found
        """
        try:
            task_key = self._get_task_key(task_id)
            task_data = self.redis.get(task_key)
            
            if not task_data:
                logger.warning(f"Task progress {task_id} not found")
                return None
            
            # Refresh TTL
            self.redis.expire(task_key, self.default_ttl)
            
            return json.loads(task_data)
            
        except Exception as e:
            logger.error(f"Error getting task progress for {task_id}: {str(e)}")
            return None
    
    def update_task_progress(
        self, 
        task_id: str, 
        update_data: Dict[str, Any]
    ) -> bool:
        """
        Update specific fields of task progress
        
        Args:
            task_id: ID of the task
            update_data: Dictionary with fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current data
            current_data = self.get_task_progress(task_id)
            if current_data is None:
                logger.warning(f"Cannot update non-existent task progress {task_id}")
                return False
            
            # Update with new data
            current_data.update(update_data)
            
            # Save back to Redis
            task_key = self._get_task_key(task_id)
            self.redis.set(task_key, json.dumps(current_data), ex=self.default_ttl)
            
            logger.info(f"Updated task progress for {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating task progress for {task_id}: {str(e)}")
            return False
    
    def delete_task_progress(self, task_id: str) -> bool:
        """
        Delete task progress from Redis
        
        Args:
            task_id: ID of the task
            
        Returns:
            True if deleted, False if not found
        """
        try:
            task_key = self._get_task_key(task_id)
            result = self.redis.delete(task_key)
            
            if result:
                logger.info(f"Deleted task progress for {task_id}")
                return True
            else:
                logger.warning(f"Task progress {task_id} not found for deletion")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting task progress for {task_id}: {str(e)}")
            return False
    
    def set_task_failed(self, task_id: str, error: str) -> bool:
        """
        Mark a task as failed
        
        Args:
            task_id: ID of the task
            error: Error message
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_task_progress(task_id, {
            "status": "failed",
            "error": error
        })
    
    def set_task_completed(
        self, 
        task_id: str, 
        results: Dict[str, Any]
    ) -> bool:
        """
        Mark a task as completed with results
        
        Args:
            task_id: ID of the task
            results: Results of the task
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_task_progress(task_id, {
            "progress": 100,
            "status": "completed",
            "results": results,
            "error": None
        })


# Create a singleton instance
_task_progress_service_instance = None

def get_task_progress_service() -> TaskProgressService:
    """
    Get singleton instance of TaskProgressService
    
    Returns:
        TaskProgressService instance
    """
    global _task_progress_service_instance
    if _task_progress_service_instance is None:
        _task_progress_service_instance = TaskProgressService()
    return _task_progress_service_instance 