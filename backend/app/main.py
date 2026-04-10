from __future__ import annotations

import json
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminProfile,
    AnalyticsResponse,
    BillingResponse,
    FraudSignal,
    GatewayRecord,
    OtpRequest,
    OtpResponse,
    TemplateCreate,
    TemplateRecord,
    VerifyRequest,
    VerifyResponse,
)
from .auth import authenticate_admin, create_access_token, ensure_default_admin, get_current_admin, require_permissions
from .settings import settings
from .services import service
from .store import initialize_database


app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    ensure_default_admin()


@app.get("/health")
def health() -> dict[str, Any]:
    return service.health()


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    return {
        "platform": settings.app_name,
        "health": service.health(),
        "message": "Use /api/v1/admin/login and /api/v1/admin/overview for protected operational data.",
    }


@app.post("/api/v1/admin/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest) -> AdminLoginResponse:
    admin = authenticate_admin(payload.username, payload.password)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

    token = create_access_token(
        username=admin["username"],
        role=admin["role"],
        permissions=admin["permissions"],
    )
    return AdminLoginResponse(
        access_token=token,
        expires_in_seconds=settings.auth_ttl_minutes * 60,
        role=admin["role"],
        permissions=admin["permissions"],
    )


@app.get("/api/v1/admin/me", response_model=AdminProfile)
def admin_me(current_admin: dict[str, Any] = Depends(get_current_admin)) -> AdminProfile:
    return AdminProfile(
        username=current_admin["username"],
        role=current_admin["role"],
        permissions=current_admin["permissions"],
    )


@app.get("/api/v1/admin/overview")
def admin_overview(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return {
        "platform": settings.app_name,
        "health": service.health(),
        "analytics": service.analytics_summary(),
        "billing": service.billing_summary(),
        "routes": service.vendor_routes(),
    }


@app.post("/api/v1/otp/request", response_model=OtpResponse)
def request_otp(payload: OtpRequest, request: Request) -> OtpResponse:
    data = payload.model_dump()
    data["ip_address"] = data.get("ip_address") or request.client.host if request.client else None
    result = service.issue_otp(data)
    return OtpResponse(
        session_id=result.session_id,
        destination=result.destination,
        channel_used=result.channel_used,  # type: ignore[arg-type]
        fallback_channels=result.fallback_channels,  # type: ignore[arg-type]
        expires_at=result.expires_at,
        sender_id=result.sender_id,
        fraud_blocked=result.fraud_blocked,
        notes=result.notes,
    )


@app.post("/api/v1/otp/verify", response_model=VerifyResponse)
def verify_otp(payload: VerifyRequest, request: Request) -> VerifyResponse:
    data = payload.model_dump()
    data["ip_address"] = data.get("ip_address") or request.client.host if request.client else None
    result = service.verify_otp(data)
    return VerifyResponse(
        verified=result.verified,
        verified_at=result.verified_at,
        webhook_signature=result.webhook_signature,
        message=result.message,
    )


@app.get("/api/v1/templates", response_model=list[TemplateRecord])
def templates(_: dict[str, Any] = Depends(require_permissions(["manage_templates"]))) -> list[TemplateRecord]:
    return [TemplateRecord(**template) for template in service.list_templates()]


@app.post("/api/v1/templates", response_model=TemplateRecord)
def create_template(
    payload: TemplateCreate,
    _: dict[str, Any] = Depends(require_permissions(["manage_templates"])),
) -> TemplateRecord:
    template = service.create_template(payload.model_dump())
    return TemplateRecord(**template)


@app.get("/api/v1/analytics", response_model=AnalyticsResponse)
def analytics(_: dict[str, Any] = Depends(require_permissions(["read_sessions"]))) -> AnalyticsResponse:
    return AnalyticsResponse(**service.analytics_summary())


@app.get("/api/v1/billing", response_model=BillingResponse)
def billing(_: dict[str, Any] = Depends(require_permissions(["read_billing"]))) -> BillingResponse:
    return BillingResponse(**service.billing_summary())


@app.get("/api/v1/fraud", response_model=list[FraudSignal])
def fraud_signals(_: dict[str, Any] = Depends(require_permissions(["read_fraud"]))) -> list[FraudSignal]:
    return [FraudSignal(**signal) for signal in service.fraud_signals()]


@app.get("/api/v1/routes", response_model=list[GatewayRecord])
def routes(_: dict[str, Any] = Depends(require_permissions(["read_sessions"]))) -> list[GatewayRecord]:
    return [GatewayRecord(**route) for route in service.vendor_routes()]


@app.get("/api/v1/rbac")
def rbac(_: dict[str, Any] = Depends(require_permissions(["manage_roles"]))) -> dict[str, Any]:
    return {"roles": service.roles()}


@app.post("/api/v1/webhooks/verify")
def webhook_test(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("session_id") or not payload.get("phone"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id and phone are required")
    signature = service._sign_webhook(payload)
    return {"signature": signature, "payload": payload}


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/")
def root() -> dict[str, Any]:
    return {"message": "OTP Authentication Service API", "docs": "/docs"}
