from fastapi import APIRouter, Form, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import User, UserPlan, Payment
from app.services.liqpay_service import LiqPayService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

liqpay_service = LiqPayService()

@router.post("/liqpay")
async def liqpay_webhook(
    data: str = Form(...),
    signature: str = Form(...),
    db: Session = Depends(get_db)
):
    """Обробка webhook від LiqPay"""
    try:
        # Перевіряємо підпис
        if not liqpay_service.verify_callback(data, signature):
            logger.error("Невірний підпис webhook")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Невірний підпис"
            )
        
        # Декодуємо дані
        payment_data = liqpay_service.decode_callback_data(data)
        
        logger.info(f"LiqPay webhook: {payment_data}")
        
        # Отримуємо order_id та статус
        order_id = payment_data.get('order_id')
        status = payment_data.get('status')
        
        if not order_id:
            logger.error("Відсутній order_id в webhook")
            return {"status": "error", "message": "Missing order_id"}
        
        # Знаходимо платіж
        payment = db.query(Payment).filter(
            Payment.order_id == order_id
        ).first()
        
        if not payment:
            logger.error(f"Платіж не знайдено: {order_id}")
            return {"status": "error", "message": "Payment not found"}
        
        # Оновлюємо статус платежу
        payment.status = status
        payment.liqpay_payment_id = payment_data.get('payment_id')
        payment.updated_at = datetime.utcnow()
        
        # Обробляємо успішний платіж
        if status == 'success':
            user = db.query(User).filter(User.id == payment.user_id).first()
            
            if user:
                # Оновлюємо план користувача
                user.plan = UserPlan(payment.plan)
                
                # Встановлюємо термін дії
                if payment.payment_type == 'subscription':
                    payment.expires_at = datetime.utcnow() + timedelta(days=30)
                else:
                    payment.expires_at = datetime.utcnow() + timedelta(days=30 * payment.months)
                
                logger.info(f"Оновлено план користувача {user.id} на {payment.plan}")
        
        # Обробляємо невдалий платіж
        elif status in ['error', 'failure']:
            payment.error_description = payment_data.get('err_description')
            logger.warning(f"Платіж невдалий: {order_id}, причина: {payment.error_description}")
        
        # Обробляємо скасування
        elif status == 'reversed':
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user and user.plan != UserPlan.FREE:
                # Повертаємо на безкоштовний план
                user.plan = UserPlan.FREE
                logger.info(f"Користувач {user.id} повернутий на FREE план через refund")
        
        # Обробляємо підписку
        elif status == 'subscribed':
            payment.subscription_id = payment_data.get('acq_id')
            logger.info(f"Підписка активована: {order_id}")
        
        # Обробляємо скасування підписки
        elif status == 'unsubscribed':
            payment.cancelled_at = datetime.utcnow()
            logger.info(f"Підписка скасована: {order_id}")
        
        db.commit()
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Помилка обробки LiqPay webhook: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Помилка обробки webhook"
        )

@router.get("/liqpay/test")
async def test_webhook_endpoint():
    """Тестовий endpoint для перевірки доступності"""
    return {"status": "ok", "message": "LiqPay webhook endpoint is working"}