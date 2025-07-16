from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token, 
    create_refresh_token, decode_token, generate_verification_token,
    create_password_reset_token, verify_password_reset_token
)
from app.models.models import User
from app.schemas.schemas import (
    UserCreate, User as UserSchema, Token, LoginRequest
)
from app.services.email_service import EmailService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/register", response_model=UserSchema)
async def register(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        company_name=user_data.company_name
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Send verification email
    email_service = EmailService()
    verification_token = generate_verification_token()
    # Store token in cache/db for verification
    
    background_tasks.add_task(
        email_service.send_verification_email,
        user_data.email,
        verification_token
    )
    
    return db_user

@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    # Authenticate user
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    payload = decode_token(refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

@router.post("/verify-email")
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    # Verify token and update user
    # This would check against stored tokens in cache/db
    # For now, simplified implementation
    
    return {"message": "Email verified successfully"}

@router.post("/forgot-password")
async def forgot_password(
    email: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Don't reveal if email exists
        return {"message": "If the email exists, a reset link has been sent"}
    
    reset_token = create_password_reset_token(email)
    
    email_service = EmailService()
    background_tasks.add_task(
        email_service.send_password_reset_email,
        email,
        reset_token
    )
    
    return {"message": "If the email exists, a reset link has been sent"}

@router.post("/reset-password")
async def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    email = verify_password_reset_token(token)
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )
    
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return {"message": "Password reset successfully"}