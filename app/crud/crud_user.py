from typing import Optional
from sqlalchemy.orm import Session
from app.core.security import get_password_hash, verify_password
from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):

    def get(self, db: Session, *, id: int) -> Optional[User]:
        return db.query(User).filter(User.id == id).first()

    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def get_by_google_id(self, db: Session, *, google_id: str) -> Optional[User]:
        return db.query(User).filter(User.google_id == google_id).first()

    def create(self, db: Session, *, obj_in: UserCreate, is_superuser: bool = False) -> User:
        db_obj = User(
            email=obj_in.email,
            hashed_password=get_password_hash(obj_in.password) if obj_in.password else None,
            is_active=True,
            is_superuser=is_superuser,
            full_name=obj_in.full_name,
            google_id=obj_in.google_id,
            profile_picture=obj_in.profile_picture,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_google_user(self, db: Session, *, obj_in: UserCreate) -> User:
        """Create a user specifically for Google OAuth authentication"""
        db_obj = User(
            email=obj_in.email,
            hashed_password=None,  # No password for Google OAuth users
            is_active=True,
            is_superuser=False,
            full_name=obj_in.full_name,
            google_id=obj_in.google_id,
            profile_picture=obj_in.profile_picture,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_google_id(self, db: Session, *, user: User, google_id: str) -> User:
        """Update user with Google ID if they don't have one"""
        user.google_id = google_id
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def authenticate(self, db: Session, *, email: str, password: str) -> Optional[User]:
        user = self.get_by_email(db, email=email)
        if not user:
            return None
        if not user.hashed_password:  # Google OAuth user trying to login with password
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

crud_user = CRUDUser(User)