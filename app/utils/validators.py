from app.models.models import User, UserPlan
from app.core.config import settings

def validate_contact_limit(user: User, new_total: int) -> bool:
    """Check if user can add more contacts based on their plan"""
    limit = settings.get_contact_limit(user.plan.value)
    return new_total <= limit

def validate_campaign_recipients(user: User, recipient_count: int) -> bool:
    """Check if campaign recipient count is within plan limits"""
    limit = settings.get_contact_limit(user.plan.value)
    return recipient_count <= limit

def validate_email_format(email: str) -> bool:
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_plan_features(plan: UserPlan) -> dict:
    """Get features available for a plan"""
    features = {
        UserPlan.FREE: {
            "contacts": 100,
            "campaigns_per_month": 5,
            "ai_credits": 10,
            "templates": 3,
            "support": "community",
            "analytics": "basic",
            "api_access": False,
            "custom_domain": False
        },
        UserPlan.STARTER: {
            "contacts": 1000,
            "campaigns_per_month": 50,
            "ai_credits": 100,
            "templates": 10,
            "support": "email",
            "analytics": "basic",
            "api_access": False,
            "custom_domain": False
        },
        UserPlan.BUSINESS: {
            "contacts": 5000,
            "campaigns_per_month": 200,
            "ai_credits": 500,
            "templates": 50,
            "support": "priority",
            "analytics": "advanced",
            "api_access": True,
            "custom_domain": False
        },
        UserPlan.PROFESSIONAL: {
            "contacts": 15000,
            "campaigns_per_month": 1000,
            "ai_credits": 2000,
            "templates": "unlimited",
            "support": "priority",
            "analytics": "advanced",
            "api_access": True,
            "custom_domain": True
        },
        UserPlan.ENTERPRISE: {
            "contacts": "unlimited",
            "campaigns_per_month": "unlimited",
            "ai_credits": "unlimited",
            "templates": "unlimited",
            "support": "dedicated",
            "analytics": "custom",
            "api_access": True,
            "custom_domain": True
        }
    }
    
    return features.get(plan, features[UserPlan.FREE])