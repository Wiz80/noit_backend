from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from decimal import Decimal

from app.api.v1.endpoints.crud.base import CRUDBase
from app.models.business.competitive_analysis.competitor_products import (
    CompetitorProduct, 
    CompetitorPricingExtraction,
    ProductType,
    PricingStatus
)
from app.schemas.business.competitor_pricing import (
    CompetitorProductCreate,
    CompetitorProductUpdate,
    CompetitorPricingExtractionCreate,
    CompetitorPricingExtractionUpdate,
    ProductSearchFilter
)

class CRUDCompetitorProduct(CRUDBase[CompetitorProduct, CompetitorProductCreate, CompetitorProductUpdate]):
    def create_with_business(
        self, 
        db: Session, 
        *, 
        obj_in: CompetitorProductCreate
    ) -> CompetitorProduct:
        """Create a competitor product with business and competitor associations."""
        obj_in_data = obj_in.dict()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_competitor(
        self, 
        db: Session, 
        *, 
        competitor_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[CompetitorProduct]:
        """Get all products for a specific competitor."""
        return (
            db.query(self.model)
            .filter(CompetitorProduct.competitor_id == competitor_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_business(
        self, 
        db: Session, 
        *, 
        business_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[CompetitorProduct]:
        """Get all products for a specific business idea."""
        return (
            db.query(self.model)
            .filter(CompetitorProduct.business_id == business_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def search_products(
        self, 
        db: Session, 
        *, 
        business_id: str,
        filters: ProductSearchFilter
    ) -> tuple[List[CompetitorProduct], int]:
        """Search products with advanced filtering."""
        query = db.query(self.model).filter(CompetitorProduct.business_id == business_id)

        # Apply filters
        if filters.competitor_ids:
            query = query.filter(CompetitorProduct.competitor_id.in_(filters.competitor_ids))

        if filters.product_types:
            query = query.filter(CompetitorProduct.product_type.in_(filters.product_types))

        if filters.min_price is not None:
            query = query.filter(
                or_(
                    CompetitorProduct.price >= filters.min_price,
                    CompetitorProduct.min_price >= filters.min_price
                )
            )

        if filters.max_price is not None:
            query = query.filter(
                or_(
                    CompetitorProduct.price <= filters.max_price,
                    CompetitorProduct.max_price <= filters.max_price
                )
            )

        if filters.currency:
            query = query.filter(CompetitorProduct.currency == filters.currency)

        if filters.categories:
            query = query.filter(CompetitorProduct.category.in_(filters.categories))

        if filters.search_term:
            search_pattern = f"%{filters.search_term}%"
            query = query.filter(
                or_(
                    CompetitorProduct.name.ilike(search_pattern),
                    CompetitorProduct.description.ilike(search_pattern),
                    CompetitorProduct.category.ilike(search_pattern)
                )
            )

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        products = (
            query
            .order_by(desc(CompetitorProduct.extracted_at))
            .offset(filters.offset)
            .limit(filters.limit)
            .all()
        )

        return products, total

    def get_pricing_statistics(
        self, 
        db: Session, 
        *, 
        business_id: str,
        competitor_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get pricing statistics for competitors."""
        query = db.query(self.model).filter(CompetitorProduct.business_id == business_id)
        
        if competitor_ids:
            query = query.filter(CompetitorProduct.competitor_id.in_(competitor_ids))

        # Basic statistics
        total_products = query.count()
        
        # Currency distribution
        currency_stats = (
            query
            .filter(CompetitorProduct.currency.isnot(None))
            .with_entities(
                CompetitorProduct.currency,
                func.count(CompetitorProduct.id).label('count')
            )
            .group_by(CompetitorProduct.currency)
            .all()
        )

        # Product type distribution
        type_stats = (
            query
            .with_entities(
                CompetitorProduct.product_type,
                func.count(CompetitorProduct.id).label('count')
            )
            .group_by(CompetitorProduct.product_type)
            .all()
        )

        # Category distribution
        category_stats = (
            query
            .filter(CompetitorProduct.category.isnot(None))
            .with_entities(
                CompetitorProduct.category,
                func.count(CompetitorProduct.id).label('count')
            )
            .group_by(CompetitorProduct.category)
            .all()
        )

        # Price statistics by currency
        price_stats = {}
        for currency, _ in currency_stats:
            currency_query = query.filter(
                and_(
                    CompetitorProduct.currency == currency,
                    CompetitorProduct.price.isnot(None)
                )
            )
            
            price_values = currency_query.with_entities(CompetitorProduct.price).all()
            if price_values:
                prices = [float(p[0]) for p in price_values if p[0] is not None]
                if prices:
                    price_stats[currency] = {
                        'min': min(prices),
                        'max': max(prices),
                        'avg': sum(prices) / len(prices),
                        'count': len(prices)
                    }

        return {
            'total_products': total_products,
            'currency_distribution': {c: count for c, count in currency_stats},
            'product_type_distribution': {str(t): count for t, count in type_stats},
            'category_distribution': {c: count for c, count in category_stats},
            'price_statistics': price_stats
        }

    def delete_by_competitor(self, db: Session, *, competitor_id: str) -> int:
        """Delete all products for a specific competitor."""
        deleted_count = (
            db.query(self.model)
            .filter(CompetitorProduct.competitor_id == competitor_id)
            .delete()
        )
        db.commit()
        return deleted_count

class CRUDCompetitorPricingExtraction(CRUDBase[CompetitorPricingExtraction, CompetitorPricingExtractionCreate, CompetitorPricingExtractionUpdate]):
    def create_with_business(
        self, 
        db: Session, 
        *, 
        obj_in: CompetitorPricingExtractionCreate
    ) -> CompetitorPricingExtraction:
        """Create a pricing extraction record."""
        obj_in_data = obj_in.dict()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_competitor(
        self, 
        db: Session, 
        *, 
        competitor_id: str
    ) -> Optional[CompetitorPricingExtraction]:
        """Get the latest extraction record for a competitor."""
        return (
            db.query(self.model)
            .filter(CompetitorPricingExtraction.competitor_id == competitor_id)
            .order_by(desc(CompetitorPricingExtraction.created_at))
            .first()
        )

    def get_by_business(
        self, 
        db: Session, 
        *, 
        business_id: str,
        status: Optional[PricingStatus] = None
    ) -> List[CompetitorPricingExtraction]:
        """Get all extraction records for a business."""
        query = db.query(self.model).filter(CompetitorPricingExtraction.business_id == business_id)
        
        if status:
            query = query.filter(CompetitorPricingExtraction.status == status)
            
        return query.order_by(desc(CompetitorPricingExtraction.created_at)).all()

    def get_pending_extractions(self, db: Session) -> List[CompetitorPricingExtraction]:
        """Get all pending extraction records."""
        return (
            db.query(self.model)
            .filter(CompetitorPricingExtraction.status == PricingStatus.PENDING)
            .order_by(CompetitorPricingExtraction.created_at)
            .all()
        )

    def update_status(
        self, 
        db: Session, 
        *, 
        extraction_id: str, 
        status: PricingStatus,
        error_message: Optional[str] = None
    ) -> Optional[CompetitorPricingExtraction]:
        """Update the status of an extraction."""
        extraction = db.query(self.model).filter(self.model.id == extraction_id).first()
        if extraction:
            extraction.status = status
            if error_message:
                extraction.error_message = error_message
            if status == PricingStatus.COMPLETED:
                from datetime import datetime, UTC
                extraction.completed_at = datetime.now(UTC)
            db.commit()
            db.refresh(extraction)
        return extraction

# Create instances
competitor_product = CRUDCompetitorProduct(CompetitorProduct)
competitor_pricing_extraction = CRUDCompetitorPricingExtraction(CompetitorPricingExtraction) 