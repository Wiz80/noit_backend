from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum

class LatinAmericaCurrency(str, Enum):
    """Latin America currency enumeration"""
    # Primary Latin American currencies
    COP = "COP"  # Colombian Peso
    MXN = "MXN"  # Mexican Peso
    ARS = "ARS"  # Argentine Peso
    BRL = "BRL"  # Brazilian Real
    PEN = "PEN"  # Peruvian Sol
    CLP = "CLP"  # Chilean Peso
    VES = "VES"  # Venezuelan Bolívar
    BOB = "BOB"  # Bolivian Boliviano
    PYG = "PYG"  # Paraguayan Guaraní
    UYU = "UYU"  # Uruguayan Peso
    GTQ = "GTQ"  # Guatemalan Quetzal
    CRC = "CRC"  # Costa Rican Colón
    PAB = "PAB"  # Panamanian Balboa
    HNL = "HNL"  # Honduran Lempira
    NIO = "NIO"  # Nicaraguan Córdoba
    DOP = "DOP"  # Dominican Peso
    
    # International currencies common in the region
    USD = "USD"  # US Dollar
    EUR = "EUR"  # Euro

class ProductTypeEnum(str, Enum):
    """Product type enumeration"""
    PRODUCT = "product"
    SERVICE = "service"
    SUBSCRIPTION = "subscription"
    OTHER = "other"

class PricingStatusEnum(str, Enum):
    """Pricing extraction status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

# Request Schemas
class CompetitorPricingExtractionRequest(BaseModel):
    """Request model for competitor pricing extraction"""
    competitor_ids: Optional[List[str]] = Field(None, description="List of competitor IDs to extract pricing for. If None, extracts for all competitors.")
    update_existing: bool = Field(False, description="Whether to update existing pricing data")
    llm_provider: str = Field("openai", description="LLM provider to use for extraction")
    llm_model: str = Field("gpt-4o-mini", description="LLM model to use for extraction")
    target_country: str = Field("CO", description="Target country code for regional price parsing (CO, MX, AR, etc.)")
    language: str = Field("es", description="Language for extraction prompts (es, en)")
    default_currency: LatinAmericaCurrency = Field(LatinAmericaCurrency.COP, description="Default currency for the target market")

class SingleCompetitorPricingRequest(BaseModel):
    """Request model for single competitor pricing extraction"""
    competitor_id: str = Field(..., description="ID of the competitor to extract pricing for")
    website_url: Optional[str] = Field(None, description="Website URL to extract from (optional, will use competitor's website if not provided)")
    llm_provider: str = Field("openai", description="LLM provider to use for extraction")
    llm_model: str = Field("gpt-4o-mini", description="LLM model to use for extraction")
    target_country: str = Field("CO", description="Target country code for regional price parsing (CO, MX, AR, etc.)")
    language: str = Field("es", description="Language for extraction prompts (es, en)")
    default_currency: LatinAmericaCurrency = Field(LatinAmericaCurrency.COP, description="Default currency for the target market")

# Product Schemas
class CompetitorProductBase(BaseModel):
    """Base schema for competitor product"""
    name: str = Field(..., description="Product or service name")
    description: Optional[str] = Field(None, description="Product description")
    product_type: ProductTypeEnum = Field(ProductTypeEnum.PRODUCT, description="Type of product or service")
    price_text: Optional[str] = Field(None, description="Original price text as extracted")
    currency: Optional[str] = Field(None, description="Currency code (USD, EUR, etc.)")
    product_url: Optional[str] = Field(None, description="Direct URL to the product page")
    pricing_page_url: Optional[str] = Field(None, description="URL of the pricing page where this was found")
    image_urls: Optional[List[str]] = Field(None, description="List of product image URLs")
    additional_features: Optional[List[str]] = Field(None, description="List of product features")
    category: Optional[str] = Field(None, description="Product category")
    availability: Optional[str] = Field(None, description="Product availability status")

class CompetitorProductCreate(CompetitorProductBase):
    """Schema for creating a competitor product"""
    competitor_id: str = Field(..., description="ID of the competitor this product belongs to")
    business_id: str = Field(..., description="ID of the business idea")
    price: Optional[Decimal] = Field(None, description="Parsed price value")
    is_range: bool = Field(False, description="Whether the price is a range")
    min_price: Optional[Decimal] = Field(None, description="Minimum price for ranges")
    max_price: Optional[Decimal] = Field(None, description="Maximum price for ranges")
    source_url: Optional[str] = Field(None, description="The URL where this product was found")
    extraction_method: Optional[str] = Field(None, description="Method used for extraction")

class CompetitorProductUpdate(BaseModel):
    """Schema for updating a competitor product"""
    name: Optional[str] = None
    description: Optional[str] = None
    product_type: Optional[ProductTypeEnum] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    price_text: Optional[str] = None
    is_range: Optional[bool] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    product_url: Optional[str] = None
    pricing_page_url: Optional[str] = None
    image_urls: Optional[List[str]] = None
    additional_features: Optional[List[str]] = None
    category: Optional[str] = None
    availability: Optional[str] = None
    source_url: Optional[str] = None

class CompetitorProduct(CompetitorProductBase):
    """Schema for competitor product response"""
    id: str
    competitor_id: str
    business_id: str
    price: Optional[Decimal] = None
    is_range: bool = False
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    source_url: Optional[str] = None
    extraction_method: Optional[str] = None
    extracted_at: datetime

    class Config:
        from_attributes = True

# Pricing Extraction Schemas
class CompetitorPricingExtractionBase(BaseModel):
    """Base schema for pricing extraction"""
    competitor_id: str
    business_id: str
    status: PricingStatusEnum = PricingStatusEnum.PENDING

class CompetitorPricingExtractionCreate(CompetitorPricingExtractionBase):
    """Schema for creating a pricing extraction record"""
    pricing_urls: Optional[List[str]] = None
    products_urls: Optional[List[str]] = None

class CompetitorPricingExtractionUpdate(BaseModel):
    """Schema for updating a pricing extraction record"""
    status: Optional[PricingStatusEnum] = None
    pricing_urls: Optional[List[str]] = None
    products_urls: Optional[List[str]] = None
    total_products_found: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None

class CompetitorPricingExtraction(CompetitorPricingExtractionBase):
    """Schema for pricing extraction response"""
    id: str
    pricing_urls: Optional[List[str]] = None
    products_urls: Optional[List[str]] = None
    total_products_found: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Response Schemas
class PricingExtractionResponse(BaseModel):
    """Response schema for pricing extraction"""
    extraction_id: str = Field(..., description="ID of the extraction process")
    status: str = Field(..., description="Status of the extraction")
    message: str = Field(..., description="Status message")

class CompetitorPricingAnalysisResponse(BaseModel):
    """Response schema for competitor pricing analysis"""
    competitor_id: str
    competitor_name: str
    website_url: Optional[str]
    extraction: Optional[CompetitorPricingExtraction]
    products: List[CompetitorProduct]
    total_products: int
    pricing_summary: Dict[str, Any] = Field(default_factory=dict)

class BatchPricingExtractionResponse(BaseModel):
    """Response schema for batch pricing extraction"""
    task_id: str = Field(..., description="ID of the batch extraction task")
    status: str = Field(..., description="Status of the batch extraction")
    competitors_processed: List[str] = Field(..., description="List of competitor IDs being processed")
    message: str = Field(..., description="Status message")

# Analysis Schemas
class PricingInsight(BaseModel):
    """Schema for pricing insights"""
    metric: str = Field(..., description="The pricing metric (avg_price, min_price, max_price, etc.)")
    value: Optional[float] = Field(None, description="The calculated value")
    currency: Optional[str] = Field(None, description="Currency for the value")
    description: str = Field(..., description="Description of the insight")

class CompetitorPricingComparison(BaseModel):
    """Schema for competitor pricing comparison"""
    business_id: str
    total_competitors: int
    total_products: int
    currency_distribution: Dict[str, int] = Field(default_factory=dict)
    price_ranges: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    product_categories: Dict[str, int] = Field(default_factory=dict)
    insights: List[PricingInsight] = Field(default_factory=list)
    competitors: List[CompetitorPricingAnalysisResponse] = Field(default_factory=list)

# Search and Filter Schemas
class ProductSearchFilter(BaseModel):
    """Schema for filtering products"""
    competitor_ids: Optional[List[str]] = None
    product_types: Optional[List[ProductTypeEnum]] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    currency: Optional[str] = None
    categories: Optional[List[str]] = None
    search_term: Optional[str] = None
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)

class ProductSearchResponse(BaseModel):
    """Schema for product search response"""
    products: List[CompetitorProduct]
    total: int
    limit: int
    offset: int
    filters_applied: ProductSearchFilter 