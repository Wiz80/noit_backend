# app/db/init_db.py
from sqlalchemy.orm import Session
from app.db.base import Base
from app.core.config import settings

from app.db.session import engine

def init_db(db: Session) -> None:
    Base.metadata.create_all(bind=engine)