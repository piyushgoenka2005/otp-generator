from __future__ import annotations

import logging
from typing import Any

from .settings import settings

logger = logging.getLogger(__name__)


class TwilioSender:
    """Send OTP codes via Twilio SMS and WhatsApp."""

    def __init__(self) -> None:
        self._client = None
        if settings.twilio_enabled:
            try:
                from twilio.rest import Client

                self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
                logger.info("Twilio client initialized successfully.")
            except ImportError:
                logger.warning("Twilio SDK not installed. Install with: pip install twilio")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio: {e}")

    def send_sms(self, phone: str, message: str) -> dict[str, Any]:
        """Send OTP via SMS using Twilio."""
        if not settings.twilio_enabled or not self._client:
            return {"success": False, "error": "Twilio is not enabled or not configured."}

        try:
            msg = self._client.messages.create(
                body=message,
                from_=settings.twilio_phone_number,
                to=phone,
            )
            return {
                "success": True,
                "message_sid": msg.sid,
                "status": msg.status,
                "channel": "sms",
            }
        except Exception as e:
            logger.error(f"SMS send failed for {phone}: {e}")
            return {"success": False, "error": str(e), "channel": "sms"}

    def send_whatsapp(self, phone: str, message: str) -> dict[str, Any]:
        """Send OTP via WhatsApp using Twilio."""
        if not settings.twilio_enabled or not self._client:
            return {"success": False, "error": "Twilio is not enabled or not configured."}

        try:
            msg = self._client.messages.create(
                body=message,
                from_=settings.twilio_whatsapp_number,
                to=f"whatsapp:{phone if phone.startswith('+') else '+' + phone}",
            )
            return {
                "success": True,
                "message_sid": msg.sid,
                "status": msg.status,
                "channel": "whatsapp",
            }
        except Exception as e:
            logger.error(f"WhatsApp send failed for {phone}: {e}")
            return {"success": False, "error": str(e), "channel": "whatsapp"}

    def send_email(self, email: str, message: str) -> dict[str, Any]:
        """Placeholder for email sending (future enhancement with SendGrid/Mailgun)."""
        logger.info(f"Email delivery placeholder for {email}")
        return {
            "success": True,
            "message_sid": "email-placeholder",
            "status": "queued",
            "channel": "email",
        }

    def send_otp(self, phone: str, email: str | None, channel: str, message: str) -> dict[str, Any]:
        """Route OTP send to appropriate channel."""
        if channel == "sms":
            return self.send_sms(phone, message)
        elif channel == "whatsapp":
            return self.send_whatsapp(phone, message)
        elif channel == "email":
            return self.send_email(email or phone, message)
        else:
            return {"success": False, "error": f"Unknown channel: {channel}"}


sender = TwilioSender()
