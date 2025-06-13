# app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
import httpx
import os
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.core.security import create_access_token
from app.api import deps
from app.schemas.user import UserCreate, UserInDBBase
from app.crud.crud_user import CRUDUser
from app.models.user import User
from app.core.config import settings

router = APIRouter()
crud_user = CRUDUser(User)

# Google OAuth2 Configuration
GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI = settings.GOOGLE_REDIRECT_URI

@router.post("/login")
async def login(
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """Login with email and password"""
    user = crud_user.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        user.id, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/google/login")
async def google_login(request: Request):
    """Initiate Google OAuth2 login"""
    # Check if Google OAuth is configured
    if not settings.google_oauth_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
        )
    
    redirect_uri = GOOGLE_REDIRECT_URI
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=openid email profile&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    
    return RedirectResponse(url=google_auth_url)

@router.get("/google/callback")
async def google_callback(code: str, db: Session = Depends(deps.get_db)):
    """Handle Google OAuth2 callback"""
    # Check if Google OAuth is configured
    if not settings.google_oauth_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured"
        )
    
    # Exchange authorization code for access token
    token_request_uri = "https://oauth2.googleapis.com/token"
    data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_request_uri, data=data)
            response.raise_for_status()
            token_response = response.json()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code for token"
            )
    
    # Verify and decode the ID token
    id_token_value = token_response.get('id_token')
    if not id_token_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing id_token in response"
        )
    
    try:
        # Verify the ID token
        id_info = id_token.verify_oauth2_token(
            id_token_value, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        # Extract user information
        google_user_id = id_info.get('sub')
        email = id_info.get('email')
        name = id_info.get('name')
        picture = id_info.get('picture')
        
        if not email or not google_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required user information from Google"
            )
        
        # Check if user exists in database
        user = crud_user.get_by_email(db, email=email)
        
        if not user:
            # Create new user if doesn't exist
            user_data = UserCreate(
                email=email,
                password=None,  # No password for Google users
                full_name=name,
                google_id=google_user_id,
                profile_picture=picture
            )
            user = crud_user.create_google_user(db, obj_in=user_data)
        else:
            # Update Google ID if user exists but doesn't have it
            if not user.google_id:
                user = crud_user.update_google_id(db, user=user, google_id=google_user_id)
        
        # Create JWT access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            user.id, expires_delta=access_token_expires
        )
        
        # Redirect to frontend with token (you can modify this based on your needs)
        redirect_url = f"{settings.FRONTEND_URL}?token={access_token}"
        return RedirectResponse(url=redirect_url)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Google ID token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google authentication failed"
        )

@router.post("/register", response_model=UserInDBBase)
async def register(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UserCreate
):
    """Register with email and password"""
    user = crud_user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    user = crud_user.create(db, obj_in=user_in)
    return user

@router.post("/create-superuser", response_model=UserInDBBase)
async def create_superuser(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UserCreate,
    secret_key: str = Header(..., alias="X-Superuser-Secret-Key")
):
    """Create superuser with secret key"""
    if secret_key != settings.SUPERUSER_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret key for creating a superuser"
        )
    
    user = crud_user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
        
    user = crud_user.create(db, obj_in=user_in, is_superuser=True)
    return user