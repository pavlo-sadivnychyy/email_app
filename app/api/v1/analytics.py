from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_verified_user
from app.models.models import User, Campaign, Contact, Email, EmailEvent
from app.schemas.schemas import AnalyticsOverview, CampaignAnalytics
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get total campaigns
    total_campaigns = db.query(Campaign).filter(
        and_(
            Campaign.user_id == current_user.id,
            Campaign.created_at >= start_date
        )
    ).count()
    
    # Get total contacts
    total_contacts = db.query(Contact).filter(
        Contact.user_id == current_user.id
    ).count()
    
    # Get email statistics
    email_stats = db.query(
        func.count(Email.id).label('total_sent'),
        func.count(Email.opened_at).label('total_opened'),
        func.count(Email.clicked_at).label('total_clicked'),
        func.count(Email.unsubscribed_at).label('total_unsubscribed'),
        func.count(Email.bounced_at).label('total_bounced')
    ).join(Campaign).filter(
        and_(
            Campaign.user_id == current_user.id,
            Email.sent_at >= start_date
        )
    ).first()
    
    # Calculate rates
    total_sent = email_stats.total_sent or 1  # Avoid division by zero
    avg_open_rate = (email_stats.total_opened / total_sent) * 100 if total_sent > 0 else 0
    avg_click_rate = (email_stats.total_clicked / total_sent) * 100 if total_sent > 0 else 0
    
    return AnalyticsOverview(
        total_campaigns=total_campaigns,
        total_contacts=total_contacts,
        total_sent=email_stats.total_sent,
        avg_open_rate=round(avg_open_rate, 2),
        avg_click_rate=round(avg_click_rate, 2),
        total_unsubscribes=email_stats.total_unsubscribed,
        total_bounces=email_stats.total_bounced
    )

@router.get("/campaigns/{campaign_id}", response_model=CampaignAnalytics)
async def get_campaign_analytics(
    campaign_id: int,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Get campaign
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
    
    # Get email statistics
    email_stats = db.query(
        func.count(Email.id).label('sent_count'),
        func.count(Email.opened_at).label('open_count'),
        func.count(Email.clicked_at).label('click_count'),
        func.count(Email.unsubscribed_at).label('unsubscribe_count'),
        func.count(Email.bounced_at).label('bounce_count')
    ).filter(Email.campaign_id == campaign_id).first()
    
    # Calculate rates
    sent_count = email_stats.sent_count or 1
    open_rate = (email_stats.open_count / sent_count) * 100
    click_rate = (email_stats.click_count / sent_count) * 100
    unsubscribe_rate = (email_stats.unsubscribe_count / sent_count) * 100
    bounce_rate = (email_stats.bounce_count / sent_count) * 100
    
    # Get engagement over time (hourly for first 48 hours)
    engagement_data = []
    if campaign.sent_at:
        for hour in range(48):
            hour_start = campaign.sent_at + timedelta(hours=hour)
            hour_end = hour_start + timedelta(hours=1)
            
            opens = db.query(func.count(EmailEvent.id)).filter(
                and_(
                    EmailEvent.event_type == "open",
                    EmailEvent.created_at >= hour_start,
                    EmailEvent.created_at < hour_end,
                    EmailEvent.email_id.in_(
                        db.query(Email.id).filter(Email.campaign_id == campaign_id)
                    )
                )
            ).scalar()
            
            clicks = db.query(func.count(EmailEvent.id)).filter(
                and_(
                    EmailEvent.event_type == "click",
                    EmailEvent.created_at >= hour_start,
                    EmailEvent.created_at < hour_end,
                    EmailEvent.email_id.in_(
                        db.query(Email.id).filter(Email.campaign_id == campaign_id)
                    )
                )
            ).scalar()
            
            engagement_data.append({
                "hour": hour,
                "opens": opens,
                "clicks": clicks
            })
    
    # Get top clicked links
    top_links = db.query(
        EmailEvent.metadata['url'].label('url'),
        func.count(EmailEvent.id).label('clicks')
    ).filter(
        and_(
            EmailEvent.event_type == "click",
            EmailEvent.email_id.in_(
                db.query(Email.id).filter(Email.campaign_id == campaign_id)
            )
        )
    ).group_by(EmailEvent.metadata['url']).order_by(
        func.count(EmailEvent.id).desc()
    ).limit(5).all()
    
    # Get device statistics
    device_stats = db.query(
        EmailEvent.metadata['device_type'].label('device'),
        func.count(EmailEvent.id).label('count')
    ).filter(
        and_(
            EmailEvent.event_type == "open",
            EmailEvent.email_id.in_(
                db.query(Email.id).filter(Email.campaign_id == campaign_id)
            )
        )
    ).group_by(EmailEvent.metadata['device_type']).all()
    
    # Get location statistics (by country)
    location_stats = db.query(
        EmailEvent.metadata['country'].label('country'),
        func.count(EmailEvent.id).label('count')
    ).filter(
        and_(
            EmailEvent.event_type == "open",
            EmailEvent.email_id.in_(
                db.query(Email.id).filter(Email.campaign_id == campaign_id)
            )
        )
    ).group_by(EmailEvent.metadata['country']).limit(10).all()
    
    return CampaignAnalytics(
        campaign_id=campaign_id,
        sent_count=sent_count,
        open_rate=round(open_rate, 2),
        click_rate=round(click_rate, 2),
        unsubscribe_rate=round(unsubscribe_rate, 2),
        bounce_rate=round(bounce_rate, 2),
        engagement_over_time=engagement_data,
        top_links=[{"url": link.url, "clicks": link.clicks} for link in top_links],
        device_stats={device.device: device.count for device in device_stats if device.device},
        location_stats={loc.country: loc.count for loc in location_stats if loc.country}
    )

@router.get("/contacts/engagement")
async def get_contact_engagement(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Calculate engagement scores for contacts
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get engagement data
    engagement_data = db.query(
        Contact.id,
        Contact.email,
        Contact.first_name,
        Contact.last_name,
        func.count(Email.opened_at).label('opens'),
        func.count(Email.clicked_at).label('clicks'),
        func.count(Email.id).label('received')
    ).join(Email).filter(
        and_(
            Contact.user_id == current_user.id,
            Email.sent_at >= start_date
        )
    ).group_by(Contact.id).order_by(
        func.count(Email.opened_at).desc()
    ).limit(50).all()
    
    # Format results
    results = []
    for contact in engagement_data:
        engagement_score = 0
        if contact.received > 0:
            open_rate = (contact.opens / contact.received) * 100
            click_rate = (contact.clicks / contact.received) * 100
            engagement_score = (open_rate * 0.6) + (click_rate * 0.4)
        
        results.append({
            "contact_id": contact.id,
            "email": contact.email,
            "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
            "opens": contact.opens,
            "clicks": contact.clicks,
            "received": contact.received,
            "engagement_score": round(engagement_score, 2)
        })
    
    return {"top_engaged_contacts": results}

@router.get("/growth")
async def get_growth_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Get subscriber growth
    growth_data = []
    end_date = datetime.utcnow().date()
    
    for i in range(days):
        date = end_date - timedelta(days=i)
        
        # New subscribers
        new_subscribers = db.query(func.count(Contact.id)).filter(
            and_(
                Contact.user_id == current_user.id,
                func.date(Contact.subscribed_at) == date
            )
        ).scalar()
        
        # Unsubscribes
        unsubscribes = db.query(func.count(Contact.id)).filter(
            and_(
                Contact.user_id == current_user.id,
                func.date(Contact.unsubscribed_at) == date
            )
        ).scalar()
        
        growth_data.append({
            "date": date.isoformat(),
            "new_subscribers": new_subscribers,
            "unsubscribes": unsubscribes,
            "net_growth": new_subscribers - unsubscribes
        })
    
    # Calculate summary metrics
    total_new = sum(d["new_subscribers"] for d in growth_data)
    total_unsub = sum(d["unsubscribes"] for d in growth_data)
    
    return {
        "growth_data": list(reversed(growth_data)),
        "summary": {
            "total_new_subscribers": total_new,
            "total_unsubscribes": total_unsub,
            "net_growth": total_new - total_unsub,
            "growth_rate": round((total_new - total_unsub) / days, 2)
        }
    }

@router.get("/performance/comparison")
async def compare_campaigns(
    campaign_ids: List[int] = Query(...),
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Get campaigns
    campaigns = db.query(Campaign).filter(
        and_(
            Campaign.id.in_(campaign_ids),
            Campaign.user_id == current_user.id
        )
    ).all()
    
    if len(campaigns) != len(campaign_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more campaigns not found"
        )
    
    comparison_data = []
    for campaign in campaigns:
        # Get metrics
        email_stats = db.query(
            func.count(Email.id).label('sent'),
            func.count(Email.opened_at).label('opened'),
            func.count(Email.clicked_at).label('clicked')
        ).filter(Email.campaign_id == campaign.id).first()
        
        sent = email_stats.sent or 1
        open_rate = (email_stats.opened / sent) * 100 if sent > 0 else 0
        click_rate = (email_stats.clicked / sent) * 100 if sent > 0 else 0
        
        comparison_data.append({
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "sent_at": campaign.sent_at.isoformat() if campaign.sent_at else None,
            "recipients": sent,
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
            "optimization_score": campaign.optimization_score or 0
        })
    
    return {"comparison": comparison_data}