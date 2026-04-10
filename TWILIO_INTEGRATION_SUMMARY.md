# Twilio Integration - Quick Summary

This document summarizes the changes made to integrate Twilio for sending OTP codes via SMS and WhatsApp.

## Files Modified

### 1. **backend/app/settings.py**
Added Twilio configuration settings:
- `TWILIO_ENABLED`: Enable/disable Twilio (default: false)
- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token
- `TWILIO_PHONE_NUMBER`: Twilio SMS phone number
- `TWILIO_WHATSAPP_NUMBER`: Twilio WhatsApp sandbox/production number

### 2. **backend/app/twilio_sender.py** (NEW)
New module that handles all Twilio operations:
- `TwilioSender`: Main class for sending OTPs
- `send_sms()`: Send OTP via SMS
- `send_whatsapp()`: Send OTP via WhatsApp
- `send_email()`: Placeholder for email delivery
- `send_otp()`: Route to appropriate channel

### 3. **backend/app/services.py**
Updated OTP issue flow:
- Imports `twilio_sender`
- Added `_render_template()`: Renders template with OTP code
- Added `_send_otp_via_channel()`: Calls Twilio sender
- Modified `_store_session()`: Now sends OTP after session creation
- Logs OTP send success/failure in event table

### 4. **backend/requirements.txt**
Added Twilio SDK:
- `twilio==9.0.4`

### 5. **Documentation Files**
- **TWILIO_SETUP.md**: Comprehensive step-by-step guide for Twilio setup
- **README.md**: Updated with Twilio info
- **backend/README.md**: Updated with Twilio configuration

## How It Works

1. **OTP Request Flow**:
   - User calls `POST /api/v1/otp/request` with phone/email
   - Backend generates 6-digit OTP code
   - Backend stores session in database
   - Backend renders template with OTP code
   - Backend sends OTP via selected channel (SMS/WhatsApp)
   - Events logged for send success/failure

2. **Channel Selection**:
   - SMS: Sent via Twilio SMS API
   - WhatsApp: Sent via Twilio WhatsApp API
   - Email: Placeholder (can integrate SendGrid/Mailgun)

3. **Fallback Handling**:
   - If preferred channel fails, routing system can try fallback channels
   - All attempts are logged in event table

## Quick Start

### Development (Twilio Disabled)
```bash
cd /c/Users/goenk/Desktop/OTP
source .venv/Scripts/activate  # or .venv\Scripts\Activate.ps1 on Windows
uvicorn app.main:app --reload --app-dir backend
```

API will work but won't actually send messages (safe for testing).

### Production (Twilio Enabled)

1. **Get Twilio credentials** (see TWILIO_SETUP.md)

2. **Set environment variables**:
   ```bash
   export TWILIO_ENABLED=true
   export TWILIO_ACCOUNT_SID="your_account_sid"
   export TWILIO_AUTH_TOKEN="your_auth_token"
   export TWILIO_PHONE_NUMBER="+1234567890"
   export TWILIO_WHATSAPP_NUMBER="whatsapp:+1234567890"
   ```

3. **Start backend**:
   ```bash
   uvicorn app.main:app --reload --app-dir backend
   ```

4. **Test OTP request**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/otp/request \
     -H "Content-Type: application/json" \
     -d '{"phone": "+1234567890", "email": "user@example.com"}'
   ```

   You should receive an SMS/WhatsApp message with the OTP code.

## Event Logging

All OTP sends are logged in the `events` table with:
- **issued**: OTP session created
- **otp_sent**: Successfully sent via channel
- **otp_send_failed**: Send failed with error details
- **verification_failed**: Incorrect code attempt
- **verified**: OTP verified successfully

## Error Handling

- If Twilio is disabled: Returns graceful error message
- If Twilio config is missing: Logs warning and continues
- If send fails: Logs error event and returns status to caller
- Network failures are handled gracefully

## Testing Without Twilio

Use the live OTP panel in the web UI at http://localhost:5173 to:
1. Request OTP (no actual SMS/WhatsApp sent)
2. Get session ID from response
3. Manually enter code to verify
4. See results in browser

This allows testing the full flow without Twilio setup.

## Next Steps

1. Follow [TWILIO_SETUP.md](./TWILIO_SETUP.md) to get API keys
2. Configure environment variables
3. Deploy and start sending real OTPs!

## Support

For issues:
- Check Twilio logs at https://www.twilio.com/console/logs
- Review event logs in SQLite at `backend/data/otp.db`
- Check backend logs for error messages
