from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_verified_user
from app.models.models import User, UserPlan, Payment
from app.schemas.schemas import CheckoutSessionResponse, SubscriptionStatus
from app.services.liqpay_service import LiqPayService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

liqpay_service = LiqPayService()

# Ціни в гривнях
PLAN_PRICES_UAH = {
    "starter": 1190,      # ~$29
    "business": 3240,     # ~$79
    "professional": 6110, # ~$149
    "enterprise": 12260   # ~$299
}

@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    plan: str,
    payment_type: str = "subscription",  # "subscription" або "onetime"
    months: int = 1,  # для одноразової оплати
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    """Створити сесію оплати через LiqPay"""
    try:
        # Перевірка плану
        if plan not in PLAN_PRICES_UAH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Невірний план"
            )
        
        amount = PLAN_PRICES_UAH[plan]
        
        # Створюємо платіж
        if payment_type == "subscription":
            payment_data = liqpay_service.create_subscription_payment(
                user_id=current_user.id,
                email=current_user.email,
                plan=plan,
                amount=amount
            )
        else:
            payment_data = liqpay_service.create_onetime_payment(
                user_id=current_user.id,
                email=current_user.email,
                plan=plan,
                amount=amount,
                months=months
            )
        
        # Зберігаємо інформацію про платіж
        payment = Payment(
            user_id=current_user.id,
            order_id=payment_data['order_id'],
            plan=plan,
            amount=amount * (months if payment_type == "onetime" else 1),
            currency='UAH',
            status='pending',
            payment_type=payment_type,
            months=months if payment_type == "onetime" else 1
        )
        db.add(payment)
        db.commit()
        
        return CheckoutSessionResponse(
            checkout_url=payment_data['checkout_url'],
            session_id=payment_data['order_id']
        )
        
    except Exception as e:
        logger.error(f"Помилка створення платежу: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не вдалося створити платіж"
        )

@router.get("/subscription", response_model=SubscriptionStatus)
async def get_subscription_status(
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    """Отримати статус підписки"""
    from app.models.models import Contact
    
    # Рахуємо контакти
    contact_count = db.query(Contact).filter(
        Contact.user_id == current_user.id
    ).count()
    
    # Отримуємо ліміт контактів для плану
    from app.core.config import settings
    contact_limit = settings.get_contact_limit(current_user.plan.value)
    
    # Перевіряємо активну підписку
    active_payment = db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.status == 'success',
        Payment.expires_at > datetime.utcnow()
    ).order_by(Payment.expires_at.desc()).first()
    
    return SubscriptionStatus(
        active=active_payment is not None,
        plan=current_user.plan,
        current_period_end=active_payment.expires_at if active_payment else None,
        cancel_at_period_end=False,  # LiqPay не має автоматичного скасування
        contact_usage=contact_count,
        contact_limit=contact_limit
    )

@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    """Скасувати підписку"""
    # Знаходимо активну підписку
    active_payment = db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.status == 'success',
        Payment.payment_type == 'subscription',
        Payment.expires_at > datetime.utcnow()
    ).first()
    
    if not active_payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Активна підписка не знайдена"
        )
    
    try:
        # Скасовуємо в LiqPay
        result = liqpay_service.cancel_subscription(active_payment.order_id)
        
        # Оновлюємо статус
        active_payment.cancelled_at = datetime.utcnow()
        db.commit()
        
        return {
            "message": "Підписку буде скасовано в кінці поточного періоду",
            "expires_at": active_payment.expires_at
        }
        
    except Exception as e:
        logger.error(f"Помилка скасування підписки: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не вдалося скасувати підписку"
        )

@router.get("/payment-history")
async def get_payment_history(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    """Отримати історію платежів"""
    payments = db.query(Payment).filter(
        Payment.user_id == current_user.id
    ).order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "payments": [
            {
                "id": p.id,
                "order_id": p.order_id,
                "amount": p.amount,
                "currency": p.currency,
                "status": p.status,
                "plan": p.plan,
                "payment_type": p.payment_type,
                "created_at": p.created_at,
                "expires_at": p.expires_at
            }
            for p in payments
        ]
    }

@router.post("/check-payment-status/{order_id}")
async def check_payment_status(
    order_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    """Перевірити статус платежу вручну"""
    payment = db.query(Payment).filter(
        Payment.order_id == order_id,
        Payment.user_id == current_user.id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Платіж не знайдено"
        )
    
    try:
        # Перевіряємо статус в LiqPay
        status_data = liqpay_service.check_payment_status(order_id)
        
        # Оновлюємо статус якщо змінився
        if status_data.get('status') != payment.status:
            payment.status = status_data.get('status')
            
            if status_data.get('status') == 'success':
                # Оновлюємо план користувача
                current_user.plan = UserPlan(payment.plan)
                
                # Встановлюємо дату закінчення
                if payment.payment_type == 'subscription':
                    payment.expires_at = datetime.utcnow() + timedelta(days=30)
                else:
                    payment.expires_at = datetime.utcnow() + timedelta(days=30 * payment.months)
            
            db.commit()
        
        return {
            "status": payment.status,
            "liqpay_status": status_data.get('status'),
            "updated": status_data.get('status') != payment.status
        }
        
    except Exception as e:
        logger.error(f"Помилка перевірки статусу: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не вдалося перевірити статус"
        )