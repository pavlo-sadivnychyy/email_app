#!/usr/bin/env python
"""
Скрипт для міграції бази даних
Створює всі таблиці включно з новою таблицею payments
"""

import sys
import logging
from app.core.database import engine, Base
from app.models.models import *  # Імпортуємо всі моделі

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    try:
        logger.info("Початок міграції...")
        
        # Створюємо всі таблиці
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Міграція успішна! Всі таблиці створено.")
        return True
        
    except Exception as e:
        logger.error(f"❌ Помилка міграції: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)