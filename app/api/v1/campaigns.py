from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_verified_user
from app.models.models import User, Campaign, Contact, Email, CampaignStatus
from app.schemas.schemas import (
    CampaignCreate, CampaignUpdate, Campaign as CampaignSchema,
    PaginatedResponse
)
from app.services.email_service import EmailService
from app.services.ai_service import AIService
from app.utils.validators import validate_campaign_recipients
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=CampaignSchema)
async def create_campaign(
    campaign_data: CampaignCreate,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Validate recipients
    if campaign_data.contact_ids:
        recipients = db.query(Contact).filter(
            and_(
                Contact.user_id == current_user.id,
                Contact.id.in_(campaign_data.contact_ids),
                Contact.status == "active"
            )
        ).all()
    elif campaign_data.tags:
        recipients = db.query(Contact).filter(
            and_(
                Contact.user_id == current_user.id,
                Contact.tags.contains(campaign_data.tags),
                Contact.status == "active"
            )
        ).all()
    else:
        recipients = db.query(Contact).filter(
            and_(
                Contact.user_id == current_user.id,
                Contact.status == "active"
            )
        ).all()
    
    # Check contact limits
    if not validate_campaign_recipients(current_user, len(recipients)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Campaign exceeds your plan's contact limit"
        )
    
    # Create campaign
    db_campaign = Campaign(
        user_id=current_user.id,
        name=campaign_data.name,
        subject=campaign_data.subject,
        content=campaign_data.content,
        from_name=campaign_data.from_name or current_user.full_name,
        from_email=campaign_data.from_email or current_user.email,
        scheduled_at=campaign_data.scheduled_at,
        recipients_count=len(recipients)
    )
    
    # Get AI suggestions
    ai_service = AIService()
    try:
        optimization = ai_service.optimize_email(
            campaign_data.subject,
            campaign_data.content
        )
        db_campaign.ai_suggestions = optimization.get("improvements")
        db_campaign.optimization_score = optimization.get("score", 0)
    except Exception as e:
        logger.error(f"AI optimization failed: {e}")
    
    db.add(db_campaign)
    db.commit()
    db.refresh(db_campaign)
    
    # Create email records for recipients
    for contact in recipients:
        email = Email(
            campaign_id=db_campaign.id,
            contact_id=contact.id
        )
        db.add(email)
    
    db.commit()
    
    return db_campaign

@router.get("/", response_model=PaginatedResponse)
async def get_campaigns(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[CampaignStatus] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    query = db.query(Campaign).filter(Campaign.user_id == current_user.id)
    
    if status:
        query = query.filter(Campaign.status == status)
    
    if search:
        query = query.filter(
            or_(
                Campaign.name.ilike(f"%{search}%"),
                Campaign.subject.ilike(f"%{search}%")
            )
        )
    
    total = query.count()
    campaigns = query.order_by(Campaign.created_at.desc()).offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        total=total,
        items=campaigns,
        skip=skip,
        limit=limit
    )

@router.get("/{campaign_id}", response_model=CampaignSchema)
async def get_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        and_(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id
        )
    ).first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    return campaign

@router.put("/{campaign_id}", response_model=CampaignSchema)
async def update_campaign(
    campaign_id: int,
    campaign_update: CampaignUpdate,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        and_(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id
        )
    ).first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    if campaign.status in [CampaignStatus.SENDING, CampaignStatus.SENT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update campaign that is sending or already sent"
        )
    
    # Update fields
    update_data = campaign_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)
    
    # Re-optimize if content changed
    if "subject" in update_data or "content" in update_data:
        ai_service = AIService()
        try:
            optimization = ai_service.optimize_email(
                campaign.subject,
                campaign.content
            )
            campaign.ai_suggestions = optimization.get("improvements")
            campaign.optimization_score = optimization.get("score", 0)
        except Exception as e:
            logger.error(f"AI optimization failed: {e}")
    
    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    
    return campaign

@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        and_(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id
        )
    ).first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    if campaign.status in [CampaignStatus.SENDING, CampaignStatus.SENT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete campaign that is sending or already sent"
        )
    
    db.delete(campaign)
    db.commit()
    
    return {"message": "Campaign deleted successfully"}

@router.post("/{campaign_id}/send")
async def send_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        and_(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id
        )
    ).first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    if campaign.status != CampaignStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign must be in draft status to send"
        )
    
    # Update campaign status
    campaign.status = CampaignStatus.SCHEDULED if campaign.scheduled_at else CampaignStatus.SENDING
    db.commit()
    
    # Queue sending task
    email_service = EmailService()
    background_tasks.add_task(
        email_service.send_campaign,
        campaign_id
    )
    
    return {"message": "Campaign queued for sending"}

@router.post("/{campaign_id}/test")
async def send_test_email(
    campaign_id: int,
    test_email: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        and_(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id
        )
    ).first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    # Send test email
    email_service = EmailService()
    background_tasks.add_task(
        email_service.send_test_email,
        campaign,
        test_email
    )
    
    return {"message": "Test email sent"}

@router.post("/{campaign_id}/duplicate", response_model=CampaignSchema)
async def duplicate_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        and_(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id
        )
    ).first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    # Create duplicate
    new_campaign = Campaign(
        user_id=current_user.id,
        name=f"{campaign.name} (Copy)",
        subject=campaign.subject,
        content=campaign.content,
        from_name=campaign.from_name,
        from_email=campaign.from_email,
        status=CampaignStatus.DRAFT
    )
    
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)
    
    return new_campaign