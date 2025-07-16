from liqpay import LiqPay
import json
import base64
from typing import Dict, Optional
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)

class LiqPayService:
    def __init__(self):
        self.liqpay = LiqPay(
            public_key=settings.LIQPAY_PUBLIC_KEY,
            private_key=settings.LIQPAY_PRIVATE_KEY
        )
        self.sandbox_mode = settings.LIQPAY_SANDBOX_MODE
    
    def create_subscription_payment(
        self,
        user_id: int,
        email: str,
        plan: str,
        amount: float
    ) -> Dict:
        """Створити платіж для підписки"""
        order_id = f"sub_{user_id}_{plan}_{int(time.time())}"
        
        params = {
            'action': 'subscribe',
            'amount': amount,
            'currency': 'UAH',
            'description': f'Підписка "{plan.title()}" - AI Email Marketing',
            'order_id': order_id,
            'version': '3',
            'sandbox': '1' if self.sandbox_mode else '0',
            'subscribe_periodicity': 'month',
            'subscribe_date_start': None,  # Почати одразу
            'result_url': f'{settings.APP_URL}/payment/success?order_id={order_id}',
            'server_url': f'{settings.API_URL}/api/v1/webhooks/liqpay',
            'customer': email,
            'customer_user_id': str(user_id),
            'product_name': f'Підписка {plan.title()}',
            'product_category': 'SaaS підписка'
        }
        
        data = self.liqpay.cnb_data(params)
        signature = self.liqpay.cnb_signature(params)
        
        return {
            'data': data,
            'signature': signature,
            'checkout_url': f'https://www.liqpay.ua/api/3/checkout?data={data}&signature={signature}',
            'order_id': order_id
        }
    
    def create_onetime_payment(
        self,
        user_id: int,
        email: str,
        plan: str,
        amount: float,
        months: int = 1
    ) -> Dict:
        """Створити одноразовий платіж"""
        order_id = f"pay_{user_id}_{plan}_{int(time.time())}"
        
        params = {
            'action': 'pay',
            'amount': amount * months,
            'currency': 'UAH',
            'description': f'Оплата {months} міс. тарифу "{plan.title()}"',
            'order_id': order_id,
            'version': '3',
            'sandbox': '1' if self.sandbox_mode else '0',
            'result_url': f'{settings.APP_URL}/payment/success?order_id={order_id}',
            'server_url': f'{settings.API_URL}/api/v1/webhooks/liqpay',
            'customer': email,
            'customer_user_id': str(user_id),
            'product_name': f'Тариф {plan.title()} ({months} міс.)',
            'product_category': 'SaaS підписка'
        }
        
        data = self.liqpay.cnb_data(params)
        signature = self.liqpay.cnb_signature(params)
        
        return {
            'data': data,
            'signature': signature,
            'checkout_url': f'https://www.liqpay.ua/api/3/checkout?data={data}&signature={signature}',
            'order_id': order_id
        }
    
    def verify_callback(self, data: str, signature: str) -> bool:
        """Перевірити підпис колбеку"""
        return signature == self.liqpay.str_to_sign(
            self.liqpay.private_key + data + self.liqpay.private_key
        )
    
    def decode_callback_data(self, data: str) -> Dict:
        """Декодувати дані колбеку"""
        decoded = base64.b64decode(data).decode('utf-8')
        return json.loads(decoded)
    
    def check_payment_status(self, order_id: str) -> Dict:
        """Перевірити статус платежу"""
        params = {
            'action': 'status',
            'version': '3',
            'order_id': order_id
        }
        
        data = self.liqpay.cnb_data(params)
        signature = self.liqpay.cnb_signature(params)
        
        # API запит для перевірки статусу
        import requests
        response = requests.post(
            'https://www.liqpay.ua/api/request',
            data={'data': data, 'signature': signature}
        )
        
        return response.json()
    
    def cancel_subscription(self, order_id: str) -> Dict:
        """Скасувати підписку"""
        params = {
            'action': 'unsubscribe',
            'version': '3',
            'order_id': order_id
        }
        
        data = self.liqpay.cnb_data(params)
        signature = self.liqpay.cnb_signature(params)
        
        import requests
        response = requests.post(
            'https://www.liqpay.ua/api/request',
            data={'data': data, 'signature': signature}
        )
        
        return response.json()
    
    def create_refund(self, order_id: str, amount: Optional[float] = None) -> Dict:
        """Створити повернення коштів"""
        params = {
            'action': 'refund',
            'version': '3',
            'order_id': order_id
        }
        
        if amount:
            params['amount'] = amount
        
        data = self.liqpay.cnb_data(params)
        signature = self.liqpay.cnb_signature(params)
        
        import requests
        response = requests.post(
            'https://www.liqpay.ua/api/request',
            data={'data': data, 'signature': signature}
        )
        
        return response.json()