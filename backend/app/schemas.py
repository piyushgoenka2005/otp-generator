from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Channel = Literal["sms", "email", "whatsapp"]


class OtpRequest(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20)
    email: str | None = None
    locale: str = Field(default="en")
    preferred_channel: Channel | None = None
    template_key: str = Field(default="default_otp")
    ip_address: str | None = None


class OtpResponse(BaseModel):
    session_id: str
    destination: str
    channel_used: Channel
    fallback_channels: list[Channel]
    expires_at: datetime
    sender_id: str
    fraud_blocked: bool = False
    notes: list[str] = Field(default_factory=list)


class VerifyRequest(BaseModel):
    session_id: str
    code: str = Field(..., min_length=4, max_length=8)
    ip_address: str | None = None


class VerifyResponse(BaseModel):
    verified: bool
    verified_at: datetime | None = None
    webhook_signature: str | None = None
    message: str


class TemplateCreate(BaseModel):
    key: str
    language: str = Field(default="en")
    body: str
    channel: Channel = "sms"
    variables: list[str] = Field(default_factory=list)


class TemplateRecord(BaseModel):
    key: str
    language: str
    body: str
    channel: Channel
    variables: list[str]
    active: bool
    created_at: datetime


class AnalyticsResponse(BaseModel):
    generated_at: datetime
    delivery_rate: float
    avg_latency_ms: float
    verified_sessions: int
    blocked_sessions: int
    total_sessions: int
    channel_mix: dict[str, int]


class BillingResponse(BaseModel):
    current_balance: float
    currency: str
    gst_rate: float
    invoice_total: float
    issued_invoices: int


class FraudSignal(BaseModel):
    session_id: str
    phone: str
    ip_address: str | None
    score: float
    reason: str
    blocked: bool


class GatewayRecord(BaseModel):
    name: str
    channel: Channel
    cost_per_message: float
    latency_ms: int
    healthy: bool


class AdminLoginRequest(BaseModel):
    username: str
    password: str = Field(..., min_length=8)


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    role: str
    permissions: list[str]


class AdminProfile(BaseModel):
    username: str
    role: str
    permissions: list[str]
