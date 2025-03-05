from pydantic import BaseModel
from typing import Dict, Any, Optional

class BusinessValidationResponse(BaseModel):
    success: bool
    business_id: str
    data_url: str 
    results: Dict[str, Any] 