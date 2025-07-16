from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional
import csv
import io
from app.core.database import get_db
from app.core.security import get_current_verified_user
from app.models.models import User, Contact, ContactStatus
from app.schemas.schemas import (
    ContactCreate, ContactUpdate, Contact as ContactSchema,
    ContactImport, PaginatedResponse
)
from app.utils.validators import validate_contact_limit
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=ContactSchema)
async def create_contact(
    contact_data: ContactCreate,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Check contact limit
    current_count = db.query(Contact).filter(
        Contact.user_id == current_user.id
    ).count()
    
    if not validate_contact_limit(current_user, current_count + 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contact limit reached for your plan"
        )
    
    # Check if contact already exists
    existing = db.query(Contact).filter(
        and_(
            Contact.user_id == current_user.id,
            Contact.email == contact_data.email
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact with this email already exists"
        )
    
    # Create contact
    db_contact = Contact(
        user_id=current_user.id,
        **contact_data.dict()
    )
    
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    
    return db_contact

@router.get("/", response_model=PaginatedResponse)
async def get_contacts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContactStatus] = None,
    tags: Optional[List[str]] = Query(None),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    query = db.query(Contact).filter(Contact.user_id == current_user.id)
    
    if status:
        query = query.filter(Contact.status == status)
    
    if tags:
        for tag in tags:
            query = query.filter(Contact.tags.contains([tag]))
    
    if search:
        query = query.filter(
            or_(
                Contact.email.ilike(f"%{search}%"),
                Contact.first_name.ilike(f"%{search}%"),
                Contact.last_name.ilike(f"%{search}%"),
                Contact.company.ilike(f"%{search}%")
            )
        )
    
    total = query.count()
    contacts = query.order_by(Contact.created_at.desc()).offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        total=total,
        items=contacts,
        skip=skip,
        limit=limit
    )

@router.get("/{contact_id}", response_model=ContactSchema)
async def get_contact(
    contact_id: int,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(
        and_(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    return contact

@router.put("/{contact_id}", response_model=ContactSchema)
async def update_contact(
    contact_id: int,
    contact_update: ContactUpdate,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(
        and_(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    # Check if email is being changed and already exists
    if contact_update.email and contact_update.email != contact.email:
        existing = db.query(Contact).filter(
            and_(
                Contact.user_id == current_user.id,
                Contact.email == contact_update.email
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact with this email already exists"
            )
    
    # Update fields
    update_data = contact_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)
    
    contact.updated_at = func.now()
    db.commit()
    db.refresh(contact)
    
    return contact

@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: int,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(
        and_(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    db.delete(contact)
    db.commit()
    
    return {"message": "Contact deleted successfully"}

@router.post("/import")
async def import_contacts(
    file: UploadFile = File(...),
    update_existing: bool = False,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported"
        )
    
    # Read CSV
    contents = await file.read()
    csv_reader = csv.DictReader(io.StringIO(contents.decode('utf-8')))
    
    imported = 0
    updated = 0
    errors = []
    
    # Check total limit
    current_count = db.query(Contact).filter(
        Contact.user_id == current_user.id
    ).count()
    
    for row_num, row in enumerate(csv_reader, start=2):
        try:
            email = row.get('email', '').strip().lower()
            if not email:
                errors.append(f"Row {row_num}: Missing email")
                continue
            
            # Check if contact exists
            existing = db.query(Contact).filter(
                and_(
                    Contact.user_id == current_user.id,
                    Contact.email == email
                )
            ).first()
            
            if existing:
                if update_existing:
                    # Update existing contact
                    existing.first_name = row.get('first_name', existing.first_name)
                    existing.last_name = row.get('last_name', existing.last_name)
                    existing.company = row.get('company', existing.company)
                    
                    # Parse tags
                    tags_str = row.get('tags', '')
                    if tags_str:
                        new_tags = [tag.strip() for tag in tags_str.split(',')]
                        existing.tags = list(set(existing.tags + new_tags))
                    
                    updated += 1
                else:
                    errors.append(f"Row {row_num}: Contact already exists")
                continue
            
            # Check limit for new contacts
            if not validate_contact_limit(current_user, current_count + imported + 1):
                errors.append(f"Row {row_num}: Contact limit reached")
                break
            
            # Create new contact
            tags_str = row.get('tags', '')
            tags = [tag.strip() for tag in tags_str.split(',')] if tags_str else []
            
            new_contact = Contact(
                user_id=current_user.id,
                email=email,
                first_name=row.get('first_name', '').strip(),
                last_name=row.get('last_name', '').strip(),
                company=row.get('company', '').strip(),
                tags=tags
            )
            
            db.add(new_contact)
            imported += 1
            
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
    
    db.commit()
    
    return {
        "imported": imported,
        "updated": updated,
        "errors": errors[:10]  # Limit errors shown
    }

@router.get("/export/csv")
async def export_contacts(
    status: Optional[ContactStatus] = None,
    tags: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    query = db.query(Contact).filter(Contact.user_id == current_user.id)
    
    if status:
        query = query.filter(Contact.status == status)
    
    if tags:
        for tag in tags:
            query = query.filter(Contact.tags.contains([tag]))
    
    contacts = query.all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'email', 'first_name', 'last_name', 'company', 
        'tags', 'status', 'subscribed_at', 'engagement_score'
    ])
    
    # Data
    for contact in contacts:
        writer.writerow([
            contact.email,
            contact.first_name or '',
            contact.last_name or '',
            contact.company or '',
            ','.join(contact.tags),
            contact.status,
            contact.subscribed_at.isoformat(),
            contact.engagement_score
        ])
    
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=contacts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )

@router.post("/bulk-update")
async def bulk_update_contacts(
    contact_ids: List[int],
    update_data: ContactUpdate,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Get contacts
    contacts = db.query(Contact).filter(
        and_(
            Contact.user_id == current_user.id,
            Contact.id.in_(contact_ids)
        )
    ).all()
    
    if not contacts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No contacts found"
        )
    
    # Update contacts
    update_dict = update_data.dict(exclude_unset=True)
    for contact in contacts:
        for field, value in update_dict.items():
            if field == "tags" and value is not None:
                # Merge tags instead of replacing
                contact.tags = list(set(contact.tags + value))
            else:
                setattr(contact, field, value)
    
    db.commit()
    
    return {"message": f"Updated {len(contacts)} contacts"}

@router.post("/bulk-delete")
async def bulk_delete_contacts(
    contact_ids: List[int],
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Delete contacts
    deleted = db.query(Contact).filter(
        and_(
            Contact.user_id == current_user.id,
            Contact.id.in_(contact_ids)
        )
    ).delete(synchronize_session=False)
    
    db.commit()
    
    return {"message": f"Deleted {deleted} contacts"}

@router.get("/tags/all")
async def get_all_tags(
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    # Get all unique tags
    contacts = db.query(Contact).filter(
        Contact.user_id == current_user.id
    ).all()
    
    all_tags = set()
    for contact in contacts:
        all_tags.update(contact.tags)
    
    return {"tags": sorted(list(all_tags))}

@router.post("/{contact_id}/unsubscribe")
async def unsubscribe_contact(
    contact_id: int,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(
        and_(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    contact.status = ContactStatus.UNSUBSCRIBED
    contact.unsubscribed_at = func.now()
    db.commit()
    
    return {"message": "Contact unsubscribed"}

from datetime import datetime