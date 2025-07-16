from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.models import User, UserPlan
from app.services.stripe_service import StripeService
import stripe
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

stripe_service = StripeService()

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    try:
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            # Get user from metadata
            user_id = int(session['metadata']['user_id'])
            user = db.query(User).filter(User.id == user_id).first()
            
            if user:
                # Update user's subscription info
                user.stripe_subscription_id = session['subscription']
                
                # Update plan based on metadata
                plan_name = session['metadata']['plan']
                user.plan = UserPlan(plan_name)
                
                db.commit()
                logger.info(f"Updated subscription for user {user_id}")
        
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            
            # Find user by subscription ID
            user = db.query(User).filter(
                User.stripe_subscription_id == subscription['id']
            ).first()
            
            if user:
                # Update plan based on price ID
                price_id = subscription['items']['data'][0]['price']['id']
                
                # Map price ID to plan
                if price_id == settings.STRIPE_PRICE_ID_STARTER:
                    user.plan = UserPlan.STARTER
                elif price_id == settings.STRIPE_PRICE_ID_BUSINESS:
                    user.plan = UserPlan.BUSINESS
                elif price_id == settings.STRIPE_PRICE_ID_PROFESSIONAL:
                    user.plan = UserPlan.PROFESSIONAL
                elif price_id == settings.STRIPE_PRICE_ID_ENTERPRISE:
                    user.plan = UserPlan.ENTERPRISE
                
                db.commit()
                logger.info(f"Updated plan for user {user.id}")
        
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            
            # Find user by subscription ID
            user = db.query(User).filter(
                User.stripe_subscription_id == subscription['id']
            ).first()
            
            if user:
                # Downgrade to free plan
                user.plan = UserPlan.FREE
                user.stripe_subscription_id = None
                
                db.commit()
                logger.info(f"Cancelled subscription for user {user.id}")
        
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            
            # Find user by customer ID
            user = db.query(User).filter(
                User.stripe_customer_id == invoice['customer']
            ).first()
            
            if user:
                # Send payment failed email
                # TODO: Implement email notification
                logger.warning(f"Payment failed for user {user.id}")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error processing webhook"
        )

@router.post("/resend")
async def resend_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle email service webhooks (opens, clicks, etc.)"""
    try:
        payload = await request.json()
        event_type = payload.get('type')
        data = payload.get('data', {})
        
        if event_type == 'email.opened':
            # Update email open statistics
            message_id = data.get('message_id')
            # TODO: Update email record
            
        elif event_type == 'email.clicked':
            # Update click statistics
            message_id = data.get('message_id')
            # TODO: Update email record
            
        elif event_type == 'email.bounced':
            # Handle bounced email
            email = data.get('email')
            # TODO: Update contact status
            
        elif event_type == 'email.complained':
            # Handle spam complaint
            email = data.get('email')
            # TODO: Update contact status
            
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing Resend webhook: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error processing webhook"
        )