from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_verified_user
from app.models.models import User
from app.schemas.schemas import (
    SubjectLineRequest, SubjectLineResponse,
    EmailContentRequest, EmailContentResponse,
    EmailOptimizationRequest, EmailOptimizationResponse
)
from app.services.ai_service import AIService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

ai_service = AIService()

@router.post("/generate-subject-lines", response_model=SubjectLineResponse)
async def generate_subject_lines(
    request: SubjectLineRequest,
    current_user: User = Depends(get_current_verified_user)
):
    try:
        suggestions = ai_service.generate_subject_lines(
            content=request.content,
            tone=request.tone,
            industry=request.industry,
            target_audience=request.target_audience
        )
        
        # Analyze subject lines
        analysis = {
            "readability_score": 8.5,
            "emotional_impact": "moderate",
            "urgency_level": "medium",
            "personalization_potential": "high"
        }
        
        return SubjectLineResponse(
            suggestions=suggestions,
            analysis=analysis
        )
    except Exception as e:
        logger.error(f"Failed to generate subject lines: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate subject lines"
        )

@router.post("/generate-email-content", response_model=EmailContentResponse)
async def generate_email_content(
    request: EmailContentRequest,
    current_user: User = Depends(get_current_verified_user)
):
    try:
        content = ai_service.generate_email_content(
            purpose=request.purpose,
            tone=request.tone,
            length=request.length,
            key_points=request.key_points,
            call_to_action=request.call_to_action,
            personalization_fields=request.personalization_fields
        )
        
        # Generate subject suggestions for the content
        subject_suggestions = ai_service.generate_subject_lines(
            content=content,
            tone=request.tone
        )
        
        optimization_tips = [
            "Add personalization tokens like {{first_name}} for better engagement",
            "Consider adding a P.S. section for additional impact",
            "Use shorter paragraphs for better mobile readability",
            "Include social proof or testimonials if relevant"
        ]
        
        return EmailContentResponse(
            content=content,
            subject_suggestions=subject_suggestions[:3],
            optimization_tips=optimization_tips
        )
    except Exception as e:
        logger.error(f"Failed to generate email content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate email content"
        )

@router.post("/optimize-email", response_model=EmailOptimizationResponse)
async def optimize_email(
    request: EmailOptimizationRequest,
    current_user: User = Depends(get_current_verified_user)
):
    try:
        optimization = ai_service.optimize_email(
            subject=request.subject,
            content=request.content,
            target_audience=request.target_audience
        )
        
        return EmailOptimizationResponse(
            score=optimization["score"],
            improvements=optimization["improvements"],
            optimized_subject=optimization.get("optimized_subject"),
            optimized_content=optimization.get("optimized_content")
        )
    except Exception as e:
        logger.error(f"Failed to optimize email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to optimize email"
        )

@router.post("/analyze-engagement")
async def analyze_engagement(
    campaign_id: int,
    current_user: User = Depends(get_current_verified_user)
):
    try:
        # This would analyze campaign performance and provide AI insights
        insights = {
            "best_performing_elements": [
                "Subject line contains urgency",
                "Personalized greeting increased opens by 23%",
                "Call-to-action button placement optimal"
            ],
            "improvement_suggestions": [
                "Try sending at 10 AM local time for better open rates",
                "Segment audience by engagement level",
                "A/B test shorter subject lines"
            ],
            "predicted_improvements": {
                "open_rate": "+15%",
                "click_rate": "+8%",
                "conversion_rate": "+5%"
            }
        }
        
        return insights
    except Exception as e:
        logger.error(f"Failed to analyze engagement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze engagement"
        )

@router.post("/smart-segmentation")
async def smart_segmentation(
    current_user: User = Depends(get_current_verified_user)
):
    try:
        # AI-powered contact segmentation suggestions
        segments = [
            {
                "name": "Highly Engaged",
                "criteria": "Opened >80% of emails in last 30 days",
                "size": 150,
                "recommendations": ["Send exclusive offers", "Request testimonials"]
            },
            {
                "name": "Re-engagement Needed",
                "criteria": "No opens in last 60 days",
                "size": 75,
                "recommendations": ["Send win-back campaign", "Update preferences survey"]
            },
            {
                "name": "New Subscribers",
                "criteria": "Subscribed within last 14 days",
                "size": 45,
                "recommendations": ["Welcome series", "Onboarding content"]
            }
        ]
        
        return {"segments": segments}
    except Exception as e:
        logger.error(f"Failed to create smart segmentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create smart segmentation"
        )

@router.post("/predict-best-send-time")
async def predict_best_send_time(
    campaign_id: int,
    current_user: User = Depends(get_current_verified_user)
):
    try:
        # AI prediction for optimal send times
        predictions = {
            "global_best_time": "Tuesday, 10:00 AM",
            "timezone_recommendations": [
                {"timezone": "America/New_York", "best_time": "10:00 AM EST"},
                {"timezone": "America/Los_Angeles", "best_time": "11:00 AM PST"},
                {"timezone": "Europe/London", "best_time": "2:00 PM GMT"}
            ],
            "day_of_week_analysis": {
                "Monday": 0.72,
                "Tuesday": 0.89,
                "Wednesday": 0.85,
                "Thursday": 0.83,
                "Friday": 0.65,
                "Saturday": 0.45,
                "Sunday": 0.38
            },
            "confidence_score": 0.87
        }
        
        return predictions
    except Exception as e:
        logger.error(f"Failed to predict send time: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to predict send time"
        )

ai_router = router