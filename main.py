from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth, users, campaigns, contacts, templates, analytics, payments_liqpay, webhooks_liqpay
from app.api.v1.ai import ai_router
from app.core.security import get_current_user
from app.utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    # Create database tables
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered email marketing platform for small businesses",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "email-marketing-api"}

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["Campaigns"])
app.include_router(contacts.router, prefix="/api/v1/contacts", tags=["Contacts"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["Templates"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(payments_liqpay.router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(ai_router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(webhooks_liqpay.router, prefix="/api/v1/webhooks", tags=["Webhooks"])

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Always use 8080 for Railway
    port = 8080
    
    print(f"Starting server on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)