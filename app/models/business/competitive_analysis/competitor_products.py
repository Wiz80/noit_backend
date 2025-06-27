import uuid
import enum
from decimal import Decimal
from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, DECIMAL, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.models.base import Base
from datetime import datetime, UTC

class ProductType(str, enum.Enum):
    """Type of product or service"""
    PRODUCT = "product"
    SERVICE = "service"
    SUBSCRIPTION = "subscription"
    OTHER = "other"

class PricingStatus(str, enum.Enum):
    """Status of pricing extraction"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class CompetitorProduct(Base):
    """Model for storing competitor products/services information"""
    __tablename__ = "competitor_products"
    
    id = Column(String, primary_key=True, index=True)
    competitor_id = Column(String, ForeignKey("competitors.id"), nullable=False)
    business_id = Column(String, ForeignKey("business_ideas.id"), nullable=False)
    
    # Product/Service Information
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    product_type = Column(Enum(ProductType), default=ProductType.PRODUCT)
    
    # Pricing Information
    price = Column(DECIMAL(10, 2), nullable=True)
    currency = Column(String(3), nullable=True)  # ISO currency code (USD, EUR, etc.)
    price_text = Column(String, nullable=True)  # Original price text as extracted
    is_range = Column(Boolean, default=False)  # True if price is a range
    min_price = Column(DECIMAL(10, 2), nullable=True)  # For price ranges
    max_price = Column(DECIMAL(10, 2), nullable=True)  # For price ranges
    
    # URLs and Images
    product_url = Column(String, nullable=True)
    pricing_page_url = Column(String, nullable=True)
    image_urls = Column(ARRAY(Text), nullable=True)  # Array of image URLs
    
    # Metadata
    extracted_at = Column(DateTime, default=datetime.now(UTC))
    source_url = Column(String, nullable=True)  # The URL where this was found
    extraction_method = Column(String, nullable=True)  # Method used for extraction
    
    # Additional data as JSON
    additional_features = Column(ARRAY(Text), nullable=True)  # Product features
    category = Column(String, nullable=True)
    availability = Column(String, nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = str(uuid.uuid4())

class CompetitorPricingExtraction(Base):
    """Model for tracking pricing extraction processes"""
    __tablename__ = "competitor_pricing_extractions"
    
    id = Column(String, primary_key=True, index=True)
    competitor_id = Column(String, ForeignKey("competitors.id"), nullable=False)
    business_id = Column(String, ForeignKey("business_ideas.id"), nullable=False)
    
    # Process Information
    status = Column(Enum(PricingStatus), default=PricingStatus.PENDING)
    
    # URLs found during extraction
    pricing_urls = Column(ARRAY(Text), nullable=True)  # URLs where pricing was found
    products_urls = Column(ARRAY(Text), nullable=True)  # URLs where products were found
    
    # Extraction details
    total_products_found = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now(UTC))
    updated_at = Column(DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = str(uuid.uuid4()) 