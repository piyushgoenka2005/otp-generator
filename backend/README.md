# Backend API

FastAPI service for the OTP authentication proposal.

## Run locally

1. Install the backend dependencies:

```bash
pip install -r backend/requirements.txt
```

2. Start the API:

```bash
uvicorn app.main:app --reload --app-dir backend
```

3. Open the API docs:

```bash
http://127.0.0.1:8000/docs
```

## Twilio Integration

To send OTP codes via SMS and WhatsApp, configure Twilio credentials:

**Environment Variables:**
```
TWILIO_ENABLED=true
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890
OTP_WEBHOOK_URL=https://your-app.example.com/webhooks/otp-verified
```

See [TWILIO_SETUP.md](../TWILIO_SETUP.md) for step-by-step instructions to obtain API keys and phone numbers.

## Key endpoints

- `GET /health`
- `GET /api/overview`
- `POST /api/v1/otp/request`
- `POST /api/v1/otp/verify`
- `POST /api/v1/admin/login`
- `GET /api/v1/admin/me` (protected)
- `GET /api/v1/admin/overview` (protected)
- `GET /api/v1/templates` (protected)
- `POST /api/v1/templates` (protected)
- `GET /api/v1/analytics` (protected)
- `GET /api/v1/billing` (protected)
- `GET /api/v1/fraud` (protected)
- `GET /api/v1/routes` (protected)
- `GET /api/v1/rbac` (protected)
- `POST /api/v1/webhooks/verify`

## Admin credentials

Set admin credentials using environment variables before starting the backend:

```bash
OTP_ADMIN_USERNAME=your_admin_username
OTP_ADMIN_PASSWORD=your_admin_password
```

If not provided, no default admin is auto-created.

## SDK integration samples

- Web: `backend/samples/sdk_web.js`
- Android: `backend/samples/sdk_android.kt`
- iOS: `backend/samples/sdk_ios.swift`

## Notes

- SQLite is used for durable local state.
- Fraud detection, least-cost routing, billing, webhook signing, and webhook delivery are implemented in the backend logic.
- Redis support is optional and can be enabled later with a bus adapter if needed.
