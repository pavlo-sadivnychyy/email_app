import stripe
from typing import Optional, List, Dict
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class StripeService:
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
    
    def create_customer(self, email: str, name: Optional[str] = None) -> stripe.Customer:
        """Create a new Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"platform": "email_marketing_ai"}
            )
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer: {e}")
            raise
    
    def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict] = None
    ) -> stripe.checkout.Session:
        """Create a checkout session for subscription"""
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {},
                subscription_data={
                    'trial_period_days': 14,  # 14-day free trial
                }
            )
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise
    
    def create_setup_session(
        self,
        customer_id: str,
        success_url: str,
        cancel_url: str
    ) -> stripe.checkout.Session:
        """Create a setup session for updating payment method"""
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                mode='setup',
                success_url=success_url,
                cancel_url=cancel_url,
                setup_intent_data={
                    'metadata': {
                        'customer_id': customer_id,
                    },
                },
            )
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create setup session: {e}")
            raise
    
    def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Get subscription details"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get subscription: {e}")
            raise
    
    def cancel_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Cancel subscription at period end"""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise
    
    def resume_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Resume a cancelled subscription"""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False
            )
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to resume subscription: {e}")
            raise
    
    def update_subscription(
        self,
        subscription_id: str,
        new_price_id: str
    ) -> stripe.Subscription:
        """Update subscription to a different plan"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update the subscription item with new price
            stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': new_price_id,
                }],
                proration_behavior='create_prorations'
            )
            
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update subscription: {e}")
            raise
    
    def get_customer_invoices(
        self,
        customer_id: str,
        limit: int = 10
    ) -> List[stripe.Invoice]:
        """Get customer invoices"""
        try:
            invoices = stripe.Invoice.list(
                customer=customer_id,
                limit=limit
            )
            return invoices.data
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get invoices: {e}")
            raise
    
    def get_payment_methods(self, customer_id: str) -> List[stripe.PaymentMethod]:
        """Get customer payment methods"""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card"
            )
            return payment_methods.data
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get payment methods: {e}")
            raise
    
    def create_usage_record(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: Optional[int] = None
    ):
        """Create usage record for metered billing"""
        try:
            stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=quantity,
                timestamp=timestamp
            )
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create usage record: {e}")
            raise