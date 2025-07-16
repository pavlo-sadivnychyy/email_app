from pydantic import BaseModel, EmailStr, constr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.models import UserPlan, CampaignStatus, ContactStatus

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    company_name: Optional[str] = None

class UserCreate(UserBase):
    password: constr(min_length=8)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[EmailStr] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    plan: UserPlan
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class User(UserInDB):
    pass

# Auth schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Campaign schemas
class CampaignBase(BaseModel):
    name: str
    subject: str
    content: str
    from_name: Optional[str] = None
    from_email: Optional[EmailStr] = None

class CampaignCreate(CampaignBase):
    scheduled_at: Optional[datetime] = None
    contact_ids: Optional[List[int]] = []
    tags: Optional[List[str]] = []

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[EmailStr] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[CampaignStatus] = None

class Campaign(CampaignBase):
    id: int
    user_id: int
    status: CampaignStatus
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    recipients_count: int
    opens_count: int
    clicks_count: int
    unsubscribes_count: int
    bounces_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    ai_suggestions: Optional[Dict[str, Any]]
    optimization_score: Optional[float]
    
    class Config:
        from_attributes = True

# Contact schemas
class ContactBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    tags: Optional[List[str]] = []
    custom_fields: Optional[Dict[str, Any]] = {}

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    status: Optional[ContactStatus] = None

class Contact(ContactBase):
    id: int
    user_id: int
    status: ContactStatus
    subscribed_at: datetime
    unsubscribed_at: Optional[datetime]
    last_activity: Optional[datetime]
    engagement_score: float
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ContactImport(BaseModel):
    contacts: List[ContactBase]
    update_existing: bool = False

# Template schemas
class TemplateBase(BaseModel):
    name: str
    subject: Optional[str] = None
    content: str
    category: Optional[str] = None

class TemplateCreate(TemplateBase):
    pass

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None

class Template(TemplateBase):
    id: int
    user_id: int
    is_default: bool
    usage_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Analytics schemas
class AnalyticsOverview(BaseModel):
    total_campaigns: int
    total_contacts: int
    total_sent: int
    avg_open_rate: float
    avg_click_rate: float
    total_unsubscribes: int
    total_bounces: int

class CampaignAnalytics(BaseModel):
    campaign_id: int
    sent_count: int
    open_rate: float
    click_rate: float
    unsubscribe_rate: float
    bounce_rate: float
    engagement_over_time: List[Dict[str, Any]]
    top_links: List[Dict[str, Any]]
    device_stats: Dict[str, int]
    location_stats: Dict[str, int]

# AI schemas
class SubjectLineRequest(BaseModel):
    content: str
    tone: Optional[str] = "professional"
    industry: Optional[str] = None
    target_audience: Optional[str] = None

class SubjectLineResponse(BaseModel):
    suggestions: List[str]
    analysis: Dict[str, Any]

class EmailContentRequest(BaseModel):
    purpose: str
    tone: Optional[str] = "professional"
    length: Optional[str] = "medium"
    key_points: Optional[List[str]] = []
    call_to_action: Optional[str] = None
    personalization_fields: Optional[List[str]] = []

class EmailContentResponse(BaseModel):
    content: str
    subject_suggestions: List[str]
    optimization_tips: List[str]

class EmailOptimizationRequest(BaseModel):
    subject: str
    content: str
    target_audience: Optional[str] = None

class EmailOptimizationResponse(BaseModel):
    score: float
    improvements: List[Dict[str, str]]
    optimized_subject: Optional[str]
    optimized_content: Optional[str]

# Payment schemas
class CreateCheckoutSession(BaseModel):
    plan: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str

class SubscriptionStatus(BaseModel):
    active: bool
    plan: UserPlan
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    contact_usage: int
    contact_limit: int

# Webhook schemas
class WebhookEvent(BaseModel):
    type: str
    data: Dict[str, Any]
    created: datetime

# Pagination schemas
class PaginationParams(BaseModel):
    skip: int = 0
    limit: int = 20
    
class PaginatedResponse(BaseModel):
    total: int
    items: List[Any]
    skip: int
    limit: int