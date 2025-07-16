import openai
from typing import List, Dict, Optional
from app.core.config import settings
import logging
import json

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.model = settings.AI_MODEL
        self.temperature = settings.AI_TEMPERATURE
        self.max_tokens = settings.AI_MAX_TOKENS
    
    def generate_subject_lines(
        self,
        content: str,
        tone: str = "professional",
        industry: Optional[str] = None,
        target_audience: Optional[str] = None,
        count: int = 5
    ) -> List[str]:
        """Generate email subject lines using AI"""
        try:
            prompt = f"""Generate {count} compelling email subject lines for the following email content.
            
Tone: {tone}
{f'Industry: {industry}' if industry else ''}
{f'Target Audience: {target_audience}' if target_audience else ''}

Email Content:
{content[:500]}...

Requirements:
- Keep subject lines under 50 characters
- Make them attention-grabbing and relevant
- Avoid spam trigger words
- Include emotional triggers when appropriate
- Consider personalization opportunities

Generate {count} different subject lines:"""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert email marketing copywriter."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=300
            )
            
            # Parse response
            content = response.choices[0].message.content
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            # Clean up numbering if present
            subject_lines = []
            for line in lines:
                # Remove common numbering patterns
                cleaned = line.lstrip('0123456789.-) ')
                if cleaned and len(cleaned) > 5:
                    subject_lines.append(cleaned)
            
            return subject_lines[:count]
            
        except Exception as e:
            logger.error(f"Failed to generate subject lines: {e}")
            # Fallback subject lines
            return [
                "Don't Miss Out on This Opportunity",
                "Important Update for You",
                "Your Exclusive Offer Inside",
                "Quick Question for You",
                "Here's What You've Been Waiting For"
            ][:count]
    
    def generate_email_content(
        self,
        purpose: str,
        tone: str = "professional",
        length: str = "medium",
        key_points: Optional[List[str]] = None,
        call_to_action: Optional[str] = None,
        personalization_fields: Optional[List[str]] = None
    ) -> str:
        """Generate complete email content"""
        try:
            length_guide = {
                "short": "100-150 words",
                "medium": "200-300 words",
                "long": "400-500 words"
            }
            
            prompt = f"""Write a compelling marketing email with the following specifications:

Purpose: {purpose}
Tone: {tone}
Length: {length_guide.get(length, "200-300 words")}
{f'Key Points to Include: {", ".join(key_points)}' if key_points else ''}
{f'Call to Action: {call_to_action}' if call_to_action else ''}
{f'Available Personalization Fields: {", ".join(personalization_fields)}' if personalization_fields else ''}

Requirements:
- Start with an engaging opening
- Use clear, concise language
- Include the key points naturally
- End with a strong call to action
- Use personalization tokens like {{first_name}} where appropriate
- Format with proper paragraphs
- Make it scannable with short paragraphs

Generate the email content:"""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert email marketing copywriter who creates high-converting emails."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Failed to generate email content: {e}")
            # Fallback content
            return f"""Hi {{{{first_name}}}},

{purpose}

We wanted to reach out to share something important with you.

{' '.join(key_points) if key_points else 'This is an opportunity you won\'t want to miss.'}

{call_to_action if call_to_action else 'Click here to learn more'}

Best regards,
{{{{sender_name}}}}"""
    
    def optimize_email(
        self,
        subject: str,
        content: str,
        target_audience: Optional[str] = None
    ) -> Dict:
        """Analyze and optimize email for better performance"""
        try:
            prompt = f"""Analyze this email for marketing effectiveness and provide optimization suggestions.

Subject Line: {subject}
{f'Target Audience: {target_audience}' if target_audience else ''}

Email Content:
{content}

Provide analysis in JSON format with:
1. "score": Overall effectiveness score (0-100)
2. "improvements": List of specific improvement suggestions
3. "optimized_subject": An improved version of the subject line
4. "optimized_content": Key sections that should be rewritten (don't rewrite the entire email)

Focus on:
- Subject line effectiveness
- Opening paragraph impact
- Call-to-action clarity
- Readability and scannability
- Emotional triggers
- Personalization opportunities
- Mobile optimization
- Spam trigger words to avoid"""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an email marketing optimization expert. Respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=1000
            )
            
            # Parse JSON response
            try:
                result = json.loads(response.choices[0].message.content)
                return result
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    "score": 75,
                    "improvements": [
                        {"area": "Subject Line", "suggestion": "Make it more specific and urgent"},
                        {"area": "Opening", "suggestion": "Start with a question or surprising fact"},
                        {"area": "CTA", "suggestion": "Make the call-to-action more prominent"},
                        {"area": "Mobile", "suggestion": "Break up long paragraphs for better mobile reading"}
                    ],
                    "optimized_subject": subject,
                    "optimized_content": None
                }
                
        except Exception as e:
            logger.error(f"Failed to optimize email: {e}")
            return {
                "score": 70,
                "improvements": [
                    {"area": "General", "suggestion": "Consider A/B testing different versions"}
                ]
            }
    
    def analyze_campaign_performance(
        self,
        campaign_data: Dict
    ) -> Dict:
        """Analyze campaign performance and provide insights"""
        try:
            prompt = f"""Analyze this email campaign performance data and provide actionable insights:

Campaign Metrics:
- Open Rate: {campaign_data.get('open_rate', 0)}%
- Click Rate: {campaign_data.get('click_rate', 0)}%
- Unsubscribe Rate: {campaign_data.get('unsubscribe_rate', 0)}%
- Bounce Rate: {campaign_data.get('bounce_rate', 0)}%

Subject Line: {campaign_data.get('subject', 'N/A')}
Send Time: {campaign_data.get('send_time', 'N/A')}
Audience Size: {campaign_data.get('audience_size', 0)}

Provide insights on:
1. What worked well
2. Areas for improvement
3. Specific recommendations for next campaign
4. Industry benchmark comparison
5. Predicted impact of suggested changes"""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an email marketing analytics expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=800
            )
            
            return {
                "insights": response.choices[0].message.content,
                "performance_rating": self._calculate_performance_rating(campaign_data)
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze campaign: {e}")
            return {
                "insights": "Unable to generate insights at this time.",
                "performance_rating": "average"
            }
    
    def _calculate_performance_rating(self, campaign_data: Dict) -> str:
        """Calculate overall performance rating"""
        open_rate = campaign_data.get('open_rate', 0)
        click_rate = campaign_data.get('click_rate', 0)
        
        # Industry average benchmarks
        if open_rate > 25 and click_rate > 3:
            return "excellent"
        elif open_rate > 20 and click_rate > 2:
            return "good"
        elif open_rate > 15 and click_rate > 1:
            return "average"
        else:
            return "needs improvement"