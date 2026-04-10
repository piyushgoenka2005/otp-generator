from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "OTP Authentication Service"
    database_path: Path = Path(
        os.getenv(
            "OTP_DB_PATH",
            "/tmp/otp.db" if os.getenv("VERCEL") == "1" else Path(__file__).resolve().parent.parent / "data" / "otp.db",
        )
    )
    webhook_secret: str = os.getenv("OTP_WEBHOOK_SECRET", "dev-webhook-secret")
    webhook_url: str = os.getenv("OTP_WEBHOOK_URL", "")
    webhook_timeout_seconds: int = int(os.getenv("OTP_WEBHOOK_TIMEOUT_SECONDS", "5"))
    api_base_path: str = "/api"
    default_sender_id: str = os.getenv("OTP_DEFAULT_SENDER_ID", "GV-TECH")
    use_redis_bus: bool = os.getenv("OTP_USE_REDIS", "false").lower() == "true"
    gst_rate: float = float(os.getenv("OTP_GST_RATE", "0.18"))
    auth_secret: str = os.getenv("OTP_AUTH_SECRET", "change-this-secret")
    auth_ttl_minutes: int = int(os.getenv("OTP_AUTH_TTL_MINUTES", "180"))
    default_admin_username: str = os.getenv("OTP_ADMIN_USERNAME", "")
    default_admin_password: str = os.getenv("OTP_ADMIN_PASSWORD", "")
    twilio_enabled: bool = os.getenv("TWILIO_ENABLED", "false").lower() == "true"
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_phone_number: str = os.getenv("TWILIO_PHONE_NUMBER", "+1234567890")
    twilio_whatsapp_number: str = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+1234567890")
    otp_phone_limit_window_minutes: int = int(os.getenv("OTP_PHONE_LIMIT_WINDOW_MINUTES", "10"))
    otp_phone_limit_count: int = int(os.getenv("OTP_PHONE_LIMIT_COUNT", "5"))
    otp_ip_limit_window_minutes: int = int(os.getenv("OTP_IP_LIMIT_WINDOW_MINUTES", "5"))
    otp_ip_limit_count: int = int(os.getenv("OTP_IP_LIMIT_COUNT", "20"))
    otp_verify_attempt_limit: int = int(os.getenv("OTP_VERIFY_ATTEMPT_LIMIT", "5"))


settings = Settings()
