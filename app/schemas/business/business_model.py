from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

class BusinessModelMessageRequest(BaseModel):
    """
    Request model for sending a message in a business model chat session
    """
    message: str = Field(..., description="Message sent by the user")
    session_id: Optional[str] = Field(None, description="Session ID for an existing chat session")

class BusinessModelMessageResponse(BaseModel):
    """
    Response model for a message in a business model chat session
    """
    session_id: str = Field(..., description="Session ID for the chat session")
    reply: str = Field(..., description="Reply from the system")
    current_question_index: int = Field(..., description="Current question index")
    total_questions: int = Field(..., description="Total number of questions")
    session_finished: bool = Field(..., description="Whether the session is finished")

class BusinessModelSessionInfo(BaseModel):
    """
    Information about a business model chat session
    """
    session_id: str = Field(..., description="Session ID")
    business_id: str = Field(..., description="Business ID")
    user_id: str = Field(..., description="User ID")
    current_question_index: int = Field(..., description="Current question index")
    total_questions: int = Field(..., description="Total number of questions")
    session_finished: bool = Field(..., description="Whether the session is finished")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

class BusinessModelSessionListResponse(BaseModel):
    """
    List of business model chat sessions
    """
    sessions: List[BusinessModelSessionInfo] = Field(..., description="List of sessions")

class BusinessModelReportResponse(BaseModel):
    """
    Business model report
    """
    session_id: str = Field(..., description="Session ID")
    business_id: str = Field(..., description="Business ID")
    report_markdown: str = Field(..., description="Report in markdown format")
    answers: Dict[str, Dict[str, str]] = Field(..., description="Answers organized by phase and question")
    
class BusinessModelResponse(BaseModel):
    """
    Response with business model data
    """
    id: str = Field(..., description="Model ID")
    business_id: str = Field(..., description="Business ID")
    problem_definition: Optional[str] = Field(None, description="Problem definition")
    industry: Optional[str] = Field(None, description="Industry")
    competitors: Optional[str] = Field(None, description="Competitors")
    customer_persona: Optional[str] = Field(None, description="Customer persona")
    value_proposition: Optional[str] = Field(None, description="Value proposition")
    competitive_advantage: Optional[str] = Field(None, description="Competitive advantage")
    key_metrics: Optional[str] = Field(None, description="Key metrics")
    key_resources: Optional[str] = Field(None, description="Key resources")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp") 