# Import all CRUD operations
from .crud.crud_user import user
from .crud.crud_business_idea import business_idea
from .crud.crud_competitor_pricing import competitor_product, competitor_pricing_extraction

# TODO: Add crud_competitor import when available
# For now, create a placeholder
class CompetitorCRUD:
    def get(self, db, *, id: str):
        from app.models.business.competitive_analysis.competitors import Competitor
        return db.query(Competitor).filter(Competitor.id == id).first()
    
    def get_by_business(self, db, *, business_id: str):
        from app.models.business.competitive_analysis.competitors import Competitor
        return db.query(Competitor).filter(Competitor.business_idea_id == business_id).all()
    
    def get_by_business_and_id(self, db, *, business_id: str, competitor_id: str):
        from app.models.business.competitive_analysis.competitors import Competitor
        return db.query(Competitor).filter(
            Competitor.business_idea_id == business_id,
            Competitor.id == competitor_id
        ).first()

competitor = CompetitorCRUD() 