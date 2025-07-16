from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from app.core.database import get_db
from app.core.security import get_current_verified_user
from app.models.models import User, Template
from app.schemas.schemas import (
    TemplateCreate, TemplateUpdate, Template as TemplateSchema,
    PaginatedResponse
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=TemplateSchema)
async def create_template(
    template_data: TemplateCreate,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Create template
    db_template = Template(
        user_id=current_user.id,
        **template_data.dict()
    )
    
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    
    return db_template

@router.get("/", response_model=PaginatedResponse)
async def get_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    include_defaults: bool = True,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Build query
    query = db.query(Template)
    
    if include_defaults:
        query = query.filter(
            or_(
                Template.user_id == current_user.id,
                Template.is_default == True
            )
        )
    else:
        query = query.filter(Template.user_id == current_user.id)
    
    if category:
        query = query.filter(Template.category == category)
    
    if search:
        query = query.filter(
            or_(
                Template.name.ilike(f"%{search}%"),
                Template.subject.ilike(f"%{search}%"),
                Template.content.ilike(f"%{search}%")
            )
        )
    
    total = query.count()
    templates = query.order_by(Template.created_at.desc()).offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        total=total,
        items=templates,
        skip=skip,
        limit=limit
    )

@router.get("/categories")
async def get_template_categories(
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Get unique categories
    categories = db.query(Template.category).filter(
        or_(
            Template.user_id == current_user.id,
            Template.is_default == True
        ),
        Template.category.isnot(None)
    ).distinct().all()
    
    return {
        "categories": [cat[0] for cat in categories if cat[0]]
    }

@router.get("/{template_id}", response_model=TemplateSchema)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    template = db.query(Template).filter(
        Template.id == template_id,
        or_(
            Template.user_id == current_user.id,
            Template.is_default == True
        )
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    return template

@router.put("/{template_id}", response_model=TemplateSchema)
async def update_template(
    template_id: int,
    template_update: TemplateUpdate,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or you don't have permission"
        )
    
    # Update fields
    update_data = template_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    db.commit()
    db.refresh(template)
    
    return template

@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or you don't have permission"
        )
    
    db.delete(template)
    db.commit()
    
    return {"message": "Template deleted successfully"}

@router.post("/{template_id}/duplicate", response_model=TemplateSchema)
async def duplicate_template(
    template_id: int,
    new_name: Optional[str] = None,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Get original template
    template = db.query(Template).filter(
        Template.id == template_id,
        or_(
            Template.user_id == current_user.id,
            Template.is_default == True
        )
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Create duplicate
    new_template = Template(
        user_id=current_user.id,
        name=new_name or f"{template.name} (Copy)",
        subject=template.subject,
        content=template.content,
        category=template.category,
        is_default=False
    )
    
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    
    return new_template

@router.post("/default-templates/seed")
async def seed_default_templates(
    db: Session = Depends(get_db)
):
    """Seed default templates (admin only)"""
    # This would be protected by admin authentication in production
    
    default_templates = [
        {
            "name": "Welcome Email",
            "subject": "Welcome to {{company_name}}!",
            "content": """
                <h2>Welcome {{first_name}}!</h2>
                <p>We're thrilled to have you join our community.</p>
                <p>Here's what you can expect:</p>
                <ul>
                    <li>Weekly tips and insights</li>
                    <li>Exclusive offers for subscribers</li>
                    <li>Early access to new features</li>
                </ul>
                <p>Get started by exploring your dashboard.</p>
                <p>Best regards,<br>The {{company_name}} Team</p>
            """,
            "category": "Welcome",
            "is_default": True
        },
        {
            "name": "Newsletter",
            "subject": "{{company_name}} Newsletter - {{month}} Edition",
            "content": """
                <h2>{{month}} Newsletter</h2>
                <p>Hi {{first_name}},</p>
                <p>Here are this month's highlights:</p>
                <h3>Featured Article</h3>
                <p>[Add your featured content here]</p>
                <h3>Product Updates</h3>
                <p>[List recent updates or improvements]</p>
                <h3>Community Spotlight</h3>
                <p>[Highlight a customer success story]</p>
                <p>Thanks for being part of our community!</p>
                <p>Best,<br>{{sender_name}}</p>
            """,
            "category": "Newsletter",
            "is_default": True
        },
        {
            "name": "Product Announcement",
            "subject": "Introducing: {{product_name}}",
            "content": """
                <h2>Exciting News!</h2>
                <p>Hi {{first_name}},</p>
                <p>We're excited to announce the launch of {{product_name}}!</p>
                <p>[Describe the product and its benefits]</p>
                <h3>Key Features:</h3>
                <ul>
                    <li>[Feature 1]</li>
                    <li>[Feature 2]</li>
                    <li>[Feature 3]</li>
                </ul>
                <p>As a valued customer, you get early access!</p>
                <p><a href="{{cta_link}}" style="background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">Get Started</a></p>
                <p>Questions? Just reply to this email.</p>
                <p>Best,<br>{{sender_name}}</p>
            """,
            "category": "Announcement",
            "is_default": True
        },
        {
            "name": "Re-engagement",
            "subject": "We miss you, {{first_name}}!",
            "content": """
                <h2>It's been a while!</h2>
                <p>Hi {{first_name}},</p>
                <p>We noticed you haven't visited us in a while, and we wanted to check in.</p>
                <p>Here's what you've missed:</p>
                <ul>
                    <li>[Update 1]</li>
                    <li>[Update 2]</li>
                    <li>[Update 3]</li>
                </ul>
                <p>As a welcome back gift, here's a special offer just for you:</p>
                <p><strong>{{offer_description}}</strong></p>
                <p><a href="{{cta_link}}" style="background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">Claim Your Offer</a></p>
                <p>We'd love to have you back!</p>
                <p>Best,<br>The {{company_name}} Team</p>
            """,
            "category": "Re-engagement",
            "is_default": True
        }
    ]
    
    for template_data in default_templates:
        # Check if already exists
        existing = db.query(Template).filter(
            and_(
                Template.name == template_data["name"],
                Template.is_default == True
            )
        ).first()
        
        if not existing:
            template = Template(**template_data)
            db.add(template)
    
    db.commit()
    
    return {"message": f"Seeded {len(default_templates)} default templates"}