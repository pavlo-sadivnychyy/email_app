from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, get_password_hash
from app.models.models import User
from app.schemas.schemas import UserUpdate, User as UserSchema
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/me", response_model=UserSchema)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    return current_user

@router.put("/me", response_model=UserSchema)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Update user fields
    update_data = user_update.dict(exclude_unset=True)
    
    # Check if email is being changed
    if "email" in update_data and update_data["email"] != current_user.email:
        # Check if new email already exists
        existing_user = db.query(User).filter(
            User.email == update_data["email"]
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify current password
    from app.core.security import verify_password
    
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}

@router.delete("/me")
async def delete_account(
    confirm: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please confirm account deletion"
        )
    
    # Cancel subscription if exists
    if current_user.stripe_subscription_id:
        from app.services.stripe_service import StripeService
        stripe_service = StripeService()
        
        try:
            stripe_service.cancel_subscription(
                current_user.stripe_subscription_id
            )
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {e}")
    
    # Delete user and all related data (cascade delete)
    db.delete(current_user)
    db.commit()
    
    return {"message": "Account deleted successfully"}