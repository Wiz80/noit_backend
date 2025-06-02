from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

class BriefMessageRequest(BaseModel):
    """Request model for sending a message in a business brief chat session"""
    message: str = Field(..., description="Message sent by the user")
    session_id: Optional[str] = Field(None, description="Session ID for an existing chat session")
    business_id: str = Field(..., description="ID of the business")
    llm_model: Optional[str] = Field("claude-3-5-sonnet-20241022", description="LLM model to use for the conversation")
    llm_temperature: Optional[float] = Field(0.7, description="Temperature for LLM responses (0.0-1.0)")
    llm_max_tokens: Optional[int] = Field(4000, description="Maximum tokens for LLM responses")

class BriefMessageResponse(BaseModel):
    """Response model for a message in a business brief chat session"""
    session_id: str = Field(..., description="Session ID for the chat session")
    reply: str = Field(..., description="Reply from the system")
    suggestion_answer: Optional[str] = Field(None, description="Suggested answer for the current question")
    suggestion_response: Optional[str] = Field(None, description="Suggested response from the agent")
    current_question_index: int = Field(..., description="Current question index")
    total_questions: int = Field(..., description="Total number of questions")
    session_finished: bool = Field(..., description="Whether the session is finished")
    answer_recorded: Optional[bool] = Field(None, description="Whether the user's answer was recorded")
    previous_action_confirmation: Optional[str] = Field(None, description="Confirmation message for the previous action")
    llm_model_used: Optional[str] = Field(None, description="LLM model that was used for this response")
    response_was_refined: Optional[bool] = Field(None, description="Whether the user's response was automatically refined")
    refined_answer: Optional[str] = Field(None, description="The refined version of the user's answer if refinement was applied")
    used_suggestion_as_base: Optional[bool] = Field(None, description="Whether the suggestion was used as the base for the response")
    was_affirmative_to_suggestion: Optional[bool] = Field(None, description="Whether the user's response was affirmative to the suggestion")
    etapa1_completed: Optional[bool] = Field(None, description="Whether ETAPA 1 was just completed")
    business_model_mapping: Optional[Dict[str, str]] = Field(None, description="Business model mapping when ETAPA 1 is completed")
    mapping_success: Optional[bool] = Field(None, description="Whether the business model mapping was successful")

class BriefSessionInfo(BaseModel):
    """Information about a brief session"""
    session_id: str = Field(..., description="Session ID")
    business_id: str = Field(..., description="Business ID")
    user_id: str = Field(..., description="User ID")
    current_question_index: int = Field(..., description="Current question index")
    total_questions: int = Field(..., description="Total number of questions")
    session_finished: bool = Field(..., description="Whether the session is finished")
    created_at: str = Field(..., description="Session creation timestamp")
    updated_at: str = Field(..., description="Session last update timestamp")

class BriefSessionListResponse(BaseModel):
    """Response model for listing brief sessions"""
    sessions: List[BriefSessionInfo] = Field(..., description="List of brief sessions")

class BriefReportResponse(BaseModel):
    """Response model for brief report"""
    session_id: str = Field(..., description="Session ID")
    business_id: str = Field(..., description="Business ID")
    report_markdown: str = Field(..., description="Report in markdown format")
    answers: Dict[str, Dict[str, str]] = Field(..., description="All answers organized by phases")

class LLMConfigResponse(BaseModel):
    """Response model for LLM configuration information"""
    available_models: Dict[str, List[str]] = Field(..., description="Available models grouped by provider")
    current_default: str = Field(..., description="Current default model")
    supported_providers: List[str] = Field(..., description="List of supported providers")

class LLMChangeRequest(BaseModel):
    """Request model for changing LLM configuration"""
    llm_model: str = Field(..., description="New LLM model to use")
    temperature: Optional[float] = Field(0.7, description="Temperature for LLM responses")
    max_tokens: Optional[int] = Field(4000, description="Maximum tokens for responses") 