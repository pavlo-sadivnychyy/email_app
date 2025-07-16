import resend
from typing import List, Dict, Optional
from app.core.config import settings
from app.models.models import Campaign, Contact, Email, EmailEvent, CampaignStatus
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY
        self.from_email = settings.FROM_EMAIL
    
    def send_verification_email(self, email: str, verification_token: str):
        """Send email verification"""
        try:
            verification_url = f"{settings.APP_URL}/verify-email?token={verification_token}"
            
            html_content = f"""
            <h2>Welcome to AI Email Marketing Assistant!</h2>
            <p>Please verify your email address to get started.</p>
            <p>
                <a href="{verification_url}" style="background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Verify Email
                </a>
            </p>
            <p>Or copy this link: {verification_url}</p>
            <p>This link will expire in 24 hours.</p>
            """
            
            response = resend.Emails.send({
                "from": self.from_email,
                "to": email,
                "subject": "Verify your email - AI Email Marketing Assistant",
                "html": html_content
            })
            
            logger.info(f"Verification email sent to {email}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send verification email: {e}")
            raise
    
    def send_password_reset_email(self, email: str, reset_token: str):
        """Send password reset email"""
        try:
            reset_url = f"{settings.APP_URL}/reset-password?token={reset_token}"
            
            html_content = f"""
            <h2>Password Reset Request</h2>
            <p>You requested to reset your password. Click the button below to create a new password.</p>
            <p>
                <a href="{reset_url}" style="background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Reset Password
                </a>
            </p>
            <p>Or copy this link: {reset_url}</p>
            <p>This link will expire in 24 hours. If you didn't request this, please ignore this email.</p>
            """
            
            response = resend.Emails.send({
                "from": self.from_email,
                "to": email,
                "subject": "Password Reset - AI Email Marketing Assistant",
                "html": html_content
            })
            
            logger.info(f"Password reset email sent to {email}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            raise
    
    def send_campaign(self, campaign_id: int, db: Session):
        """Send campaign emails"""
        try:
            # Get campaign and emails
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return
            
            # Update campaign status
            campaign.status = CampaignStatus.SENDING
            db.commit()
            
            # Get emails to send
            emails = db.query(Email).filter(
                Email.campaign_id == campaign_id,
                Email.status == "pending"
            ).all()
            
            sent_count = 0
            failed_count = 0
            
            for email_record in emails:
                try:
                    # Get contact
                    contact = email_record.contact
                    
                    # Personalize content
                    personalized_content = self._personalize_content(
                        campaign.content,
                        contact
                    )
                    
                    # Send email
                    response = resend.Emails.send({
                        "from": f"{campaign.from_name} <{campaign.from_email}>",
                        "to": contact.email,
                        "subject": self._personalize_content(campaign.subject, contact),
                        "html": personalized_content,
                        "headers": {
                            "X-Campaign-ID": str(campaign_id),
                            "X-Email-ID": str(email_record.id),
                            "List-Unsubscribe": f"<{settings.APP_URL}/unsubscribe?email={contact.email}&campaign={campaign_id}>"
                        }
                    })
                    
                    # Update email record
                    email_record.message_id = response['id']
                    email_record.status = "sent"
                    email_record.sent_at = datetime.utcnow()
                    sent_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to send email to {contact.email}: {e}")
                    email_record.status = "failed"
                    failed_count += 1
                
                # Commit batch
                if (sent_count + failed_count) % 50 == 0:
                    db.commit()
            
            # Final commit
            db.commit()
            
            # Update campaign
            campaign.status = CampaignStatus.SENT
            campaign.sent_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Campaign {campaign_id} sent. Success: {sent_count}, Failed: {failed_count}")
            
        except Exception as e:
            logger.error(f"Failed to send campaign {campaign_id}: {e}")
            campaign.status = CampaignStatus.FAILED
            db.commit()
            raise
    
    def send_test_email(self, campaign: Campaign, test_email: str):
        """Send test email for campaign"""
        try:
            # Create dummy contact for personalization
            dummy_contact = Contact(
                email=test_email,
                first_name="Test",
                last_name="User",
                company="Test Company"
            )
            
            personalized_content = self._personalize_content(
                campaign.content,
                dummy_contact
            )
            
            html_content = f"""
            <div style="background-color: #FEF3C7; padding: 10px; margin-bottom: 20px; border-radius: 4px;">
                <strong>⚠️ TEST EMAIL</strong> - This is a test version of your campaign
            </div>
            {personalized_content}
            """
            
            response = resend.Emails.send({
                "from": f"{campaign.from_name} <{campaign.from_email}>",
                "to": test_email,
                "subject": f"[TEST] {self._personalize_content(campaign.subject, dummy_contact)}",
                "html": html_content
            })
            
            logger.info(f"Test email sent to {test_email}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send test email: {e}")
            raise
    
    def _personalize_content(self, content: str, contact: Contact) -> str:
        """Replace personalization tokens with contact data"""
        replacements = {
            "{{first_name}}": contact.first_name or "there",
            "{{last_name}}": contact.last_name or "",
            "{{full_name}}": f"{contact.first_name or ''} {contact.last_name or ''}".strip() or "there",
            "{{email}}": contact.email,
            "{{company}}": contact.company or "your company"
        }
        
        # Add custom fields
        for key, value in (contact.custom_fields or {}).items():
            replacements[f"{{{{{key}}}}}"] = str(value)
        
        # Replace tokens
        for token, value in replacements.items():
            content = content.replace(token, value)
        
        return content
    
    def track_email_event(
        self,
        email_id: int,
        event_type: str,
        metadata: Optional[Dict] = None,
        db: Session = None
    ):
        """Track email events (opens, clicks, etc.)"""
        try:
            # Create event record
            event = EmailEvent(
                email_id=email_id,
                event_type=event_type,
                event_metadata=metadata or {},
                ip_address=metadata.get('ip') if metadata else None,
                user_agent=metadata.get('user_agent') if metadata else None
            )
            db.add(event)
            
            # Update email record
            email = db.query(Email).filter(Email.id == email_id).first()
            if email:
                if event_type == "open":
                    if not email.opened_at:
                        email.opened_at = datetime.utcnow()
                    email.open_count += 1
                elif event_type == "click":
                    if not email.clicked_at:
                        email.clicked_at = datetime.utcnow()
                    email.click_count += 1
                elif event_type == "unsubscribe":
                    email.unsubscribed_at = datetime.utcnow()
                elif event_type == "bounce":
                    email.bounced_at = datetime.utcnow()
                elif event_type == "complaint":
                    email.complained_at = datetime.utcnow()
                
                # Update campaign stats
                campaign = email.campaign
                if campaign:
                    if event_type == "open":
                        campaign.opens_count = db.query(Email).filter(
                            Email.campaign_id == campaign.id,
                            Email.opened_at.isnot(None)
                        ).count()
                    elif event_type == "click":
                        campaign.clicks_count = db.query(Email).filter(
                            Email.campaign_id == campaign.id,
                            Email.clicked_at.isnot(None)
                        ).count()
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to track email event: {e}")
            if db:
                db.rollback()
            raise