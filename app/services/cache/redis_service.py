import json
import redis
import logging
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    """Model for chat messages"""
    role: str  # 'user', 'system', or 'assistant'
    content: str
    timestamp: datetime = None
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now()
        super().__init__(**data)

class ChatSession(BaseModel):
    """Model for chat sessions"""
    id: str
    user_id: str
    business_id: str
    messages: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    created_at: datetime = None
    updated_at: datetime = None
    
    def __init__(self, **data):
        if 'id' not in data:
            data['id'] = str(uuid.uuid4())
        if 'created_at' not in data:
            data['created_at'] = datetime.now()
        if 'updated_at' not in data:
            data['updated_at'] = datetime.now()
        if 'messages' not in data:
            data['messages'] = []
        if 'metadata' not in data:
            data['metadata'] = {}
        super().__init__(**data)

class RedisChatService:
    """Service for managing chat conversations using Redis"""
    
    def __init__(
        self, 
        host: str = "localhost", 
        port: int = 6379, 
        db: int = 0, 
        password: str = None,
        default_ttl: int = 86400  # 24 hours in seconds
    ):
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )
        self.default_ttl = default_ttl
        logger.info(f"Redis chat service initialized with host: {host}, port: {port}")
    
    def _get_session_key(self, session_id: str) -> str:
        """Get Redis key for a chat session"""
        return f"chat:session:{session_id}"
    
    def _get_user_sessions_key(self, user_id: str) -> str:
        """Get Redis key for user's sessions"""
        return f"chat:user:{user_id}:sessions"
    
    def _get_business_sessions_key(self, business_id: str) -> str:
        """Get Redis key for business's sessions"""
        return f"chat:business:{business_id}:sessions"

    async def create_session(
        self, 
        user_id: str, 
        business_id: str, 
        metadata: Dict[str, Any] = None,
        initial_messages: List[Dict[str, Any]] = None
    ) -> ChatSession:
        """
        Create a new chat session
        
        Args:
            user_id: ID of the user
            business_id: ID of the business
            metadata: Additional metadata for the session
            initial_messages: Optional list of initial messages
            
        Returns:
            ChatSession object
        """
        # Create session object
        session = ChatSession(
            user_id=user_id,
            business_id=business_id,
            metadata=metadata or {},
        )
        
        # Add initial messages if provided
        if initial_messages:
            session.messages.extend(initial_messages)
        
        # Serialize and store in Redis
        session_data = session.model_dump_json()
        session_key = self._get_session_key(session.id)
        user_sessions_key = self._get_user_sessions_key(user_id)
        business_sessions_key = self._get_business_sessions_key(business_id)
        
        pipe = self.redis.pipeline()
        pipe.set(session_key, session_data, ex=self.default_ttl)
        pipe.sadd(user_sessions_key, session.id)
        pipe.sadd(business_sessions_key, session.id)
        pipe.execute()
        
        logger.info(f"Created chat session {session.id} for user {user_id}, business {business_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get a chat session by ID
        
        Args:
            session_id: ID of the session to retrieve
            
        Returns:
            ChatSession object or None if not found
        """
        session_key = self._get_session_key(session_id)
        session_data = self.redis.get(session_key)
        
        if not session_data:
            logger.warning(f"Chat session {session_id} not found")
            return None
        
        # Refresh TTL
        self.redis.expire(session_key, self.default_ttl)
        
        try:
            # Parse the JSON data and create a ChatSession object
            session_dict = json.loads(session_data)
            return ChatSession(**session_dict)
        except Exception as e:
            logger.error(f"Error parsing chat session {session_id}: {e}")
            return None
    
    async def add_message(
        self, 
        session_id: str, 
        message: Dict[str, Any]
    ) -> Optional[ChatSession]:
        """
        Add a message to a chat session
        
        Args:
            session_id: ID of the session
            message: Message dictionary with 'role' and 'content' keys
            
        Returns:
            Updated ChatSession object or None if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Cannot add message to non-existent session {session_id}")
            return None
        
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()
        
        # Add message
        session.messages.append(message)
        session.updated_at = datetime.now()
        
        # Update in Redis
        session_key = self._get_session_key(session_id)
        session_data = session.model_dump_json()
        self.redis.set(session_key, session_data, ex=self.default_ttl)
        
        logger.info(f"Added {message['role']} message to session {session_id}")
        return session
    
    async def get_user_sessions(self, user_id: str) -> List[str]:
        """
        Get all session IDs for a user
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of session IDs
        """
        user_sessions_key = self._get_user_sessions_key(user_id)
        session_ids = self.redis.smembers(user_sessions_key)
        return list(session_ids)
    
    async def get_business_sessions(self, business_id: str) -> List[str]:
        """
        Get all session IDs for a business
        
        Args:
            business_id: ID of the business
            
        Returns:
            List of session IDs
        """
        business_sessions_key = self._get_business_sessions_key(business_id)
        session_ids = self.redis.smembers(business_sessions_key)
        return list(session_ids)
    
    async def update_session_metadata(
        self, 
        session_id: str, 
        metadata: Dict[str, Any]
    ) -> Optional[ChatSession]:
        """
        Update metadata for a chat session
        
        Args:
            session_id: ID of the session
            metadata: Metadata to update
            
        Returns:
            Updated ChatSession object or None if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Cannot update metadata for non-existent session {session_id}")
            return None
        
        # Update metadata
        session.metadata.update(metadata)
        session.updated_at = datetime.now()
        
        # Update in Redis
        session_key = self._get_session_key(session_id)
        session_data = session.model_dump_json()
        self.redis.set(session_key, session_data, ex=self.default_ttl)
        
        logger.info(f"Updated metadata for session {session_id}")
        return session
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a chat session
        
        Args:
            session_id: ID of the session to delete
            
        Returns:
            True if deleted, False if not found
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Cannot delete non-existent session {session_id}")
            return False
        
        # Remove from Redis
        session_key = self._get_session_key(session_id)
        user_sessions_key = self._get_user_sessions_key(session.user_id)
        business_sessions_key = self._get_business_sessions_key(session.business_id)
        
        pipe = self.redis.pipeline()
        pipe.delete(session_key)
        pipe.srem(user_sessions_key, session_id)
        pipe.srem(business_sessions_key, session_id)
        pipe.execute()
        
        logger.info(f"Deleted chat session {session_id}")
        return True
    
    async def get_conversation_history(
        self, 
        session_id: str, 
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session
        
        Args:
            session_id: ID of the session
            limit: Optional limit on number of messages to return (most recent)
            
        Returns:
            List of messages in the conversation
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Cannot get history for non-existent session {session_id}")
            return []
        
        messages = session.messages
        if limit and len(messages) > limit:
            messages = messages[-limit:]
        
        return messages 