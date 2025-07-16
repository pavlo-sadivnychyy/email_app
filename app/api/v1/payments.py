from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_verified_user
from app.core.config import settings
from app.models.models import User, UserPlan
from app.schemas.schemas import (
    CreateCheckoutSession, CheckoutSessionResponse,
    SubscriptionStatus
)
from app.services.stripe_service import StripeService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

stripe_service = StripeService()

@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    session_data: CreateCheckoutSession,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    try:
        # Get price ID for plan
        price_id = settings.get_stripe_price_id(session_data.plan)
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid plan selected"
            )
        
        # Create Stripe checkout session
        checkout_session = stripe_service.create_checkout_session(
            customer_id=current_user.stripe_customer_id,
            price_id=price_id,
            success_url=session_data.success_url or f"{settings.APP_URL}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=session_data.cancel_url or f"{settings.APP_URL}/pricing",
            metadata={
                "user_id": str(current_user.id),
                "plan": session_data.plan
            }
        )
        
        return CheckoutSessionResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id
        )
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )

@router.get("/subscription", response_model=SubscriptionStatus)
async def get_subscription_status(
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    try:
        # Get subscription from Stripe
        if current_user.stripe_subscription_id:
            subscription = stripe_service.get_subscription(
                current_user.stripe_subscription_id
            )
            
            # Calculate contact usage
            from app.models.models import Contact
            contact_count = db.query(Contact).filter(
                Contact.user_id == current_user.id
            ).count()
            
            contact_limit = settings.get_contact_limit(current_user.plan.value)
            
            return SubscriptionStatus(
                active=subscription.status == "active",
                plan=current_user.plan,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
                contact_usage=contact_count,
                contact_limit=contact_limit
            )
        else:
            # Free plan
            from app.models.models import Contact
            contact_count = db.query(Contact).filter(
                Contact.user_id == current_user.id
            ).count()
            
            return SubscriptionStatus(
                active=True,
                plan=UserPlan.FREE,
                current_period_end=None,
                cancel_at_period_end=False,
                contact_usage=contact_count,
                contact_limit=100  # Free plan limit
            )
    except Exception as e:
        logger.error(f"Failed to get subscription status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subscription status"
        )

@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    try:
        if not current_user.stripe_subscription_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription found"
            )
        
        # Cancel at period end
        subscription = stripe_service.cancel_subscription(
            current_user.stripe_subscription_id
        )
        
        return {
            "message": "Subscription will be cancelled at the end of the billing period",
            "cancel_at": subscription.cancel_at
        }
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )

@router.post("/resume-subscription")
async def resume_subscription(
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    try:
        if not current_user.stripe_subscription_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No subscription found"
            )
        
        # Resume subscription
        subscription = stripe_service.resume_subscription(
            current_user.stripe_subscription_id
        )
        
        return {
            "message": "Subscription resumed successfully",
            "status": subscription.status
        }
    except Exception as e:
        logger.error(f"Failed to resume subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume subscription"
        )

@router.post("/update-payment-method")
async def update_payment_method(
    current_user: User = Depends(get_current_verified_user)
):
    try:
        # Create setup session for updating payment method
        session = stripe_service.create_setup_session(
            customer_id=current_user.stripe_customer_id,
            success_url=f"{settings.APP_URL}/settings/billing?success=true",
            cancel_url=f"{settings.APP_URL}/settings/billing"
        )
        
        return {
            "setup_url": session.url,
            "session_id": session.id
        }
    except Exception as e:
        logger.error(f"Failed to create setup session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create setup session"
        )

@router.get("/invoices")
async def get_invoices(
    limit: int = 10,
    current_user: User = Depends(get_current_verified_user)
):
    try:
        if not current_user.stripe_customer_id:
            return {"invoices": []}
        
        invoices = stripe_service.get_customer_invoices(
            current_user.stripe_customer_id,
            limit=limit
        )
        
        return {
            "invoices": [
                {
                    "id": invoice.id,
                    "number": invoice.number,
                    "amount": invoice.amount_paid / 100,
                    "currency": invoice.currency,
                    "status": invoice.status,
                    "created": invoice.created,
                    "pdf_url": invoice.invoice_pdf,
                    "hosted_url": invoice.hosted_invoice_url
                }
                for invoice in invoices
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get invoices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get invoices"
        )

@router.get("/payment-methods")
async def get_payment_methods(
    current_user: User = Depends(get_current_verified_user)
):
    try:
        if not current_user.stripe_customer_id:
            return {"payment_methods": []}
        
        payment_methods = stripe_service.get_payment_methods(
            current_user.stripe_customer_id
        )
        
        return {
            "payment_methods": [
                {
                    "id": pm.id,
                    "type": pm.type,
                    "card": {
                        "brand": pm.card.brand,
                        "last4": pm.card.last4,
                        "exp_month": pm.card.exp_month,
                        "exp_year": pm.card.exp_year
                    } if pm.type == "card" else None
                }
                for pm in payment_methods
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get payment methods: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get payment methods"
        )