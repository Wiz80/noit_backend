from typing import List, Optional
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from app.api.v1.endpoints.crud.base import CRUDBase
from app.models.business.business_idea import BusinessIdea
from app.schemas.business.business_idea import BusinessIdeaCreate, BusinessIdeaUpdate

class CRUDBusinessIdea(CRUDBase[BusinessIdea, BusinessIdeaCreate, BusinessIdeaUpdate]):
    def get_by_title_and_owner(
        self, db: Session, *, title: str, owner_id: int
    ) -> Optional[BusinessIdea]:
        """
        Verifica si ya existe una idea de negocio con el mismo título para el usuario
        """
        return db.query(self.model).filter(
            BusinessIdea.title == title,
            BusinessIdea.user_id == owner_id
        ).first()
    
    def create_with_owner(
        self, db: Session, *, obj_in: BusinessIdeaCreate, owner_id: int
    ) -> BusinessIdea:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data, user_id=owner_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[BusinessIdea]:
        return (
            db.query(self.model)
            .filter(BusinessIdea.user_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

crud_business_idea = CRUDBusinessIdea(BusinessIdea)