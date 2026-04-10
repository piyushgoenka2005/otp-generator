# Twilio OTP Integration Guide

This guide walks you through obtaining Twilio API credentials and configuring them for sending OTP codes via SMS and WhatsApp.

## Step-by-Step Instructions to Get Twilio API Keys

### Step 1: Create a Twilio Account

1. Go to [https://www.twilio.com/console](https://www.twilio.com/console)
2. Click **Sign Up** (top-right corner)
3. Enter your details:
   - Email address
   - Password
   - Full name
4. Click **Get Started**
5. Select your use case (e.g., "Send SMS messages to users")
6. Verify your email address (check your inbox for confirmation link)
7. Create a new project or use the default one

### Step 2: Get Your Account SID and Auth Token

1. After login, navigate to the [Twilio Console Dashboard](https://www.twilio.com/console)
2. You'll see a section labeled **Account** with two values:
   - **Account SID**: Your unique account identifier (starts with `AC...`)
   - **Auth Token**: Your authentication token (appears as dots for security)
3. Click the eye icon next to **Auth Token** to reveal it
4. Save both values securely (you'll need them for configuration)

### Step 3: Get a Twilio Phone Number for SMS

1. In the console, go to **Phone Numbers** in the left sidebar
2. Click the **+** icon to get a new number
3. Select your country
4. Choose a phone number (search for availability)
5. Click **Buy** and confirm purchase
6. Your phone number will now be listed (e.g., `+1234567890`)
7. Save this number for SMS configuration

### Step 4: Enable WhatsApp (Optional)

1. In the console, go to **Messaging** > **Services** in the left sidebar
2. Click **Create Messaging Service**
3. Give it a name (e.g., "OTP WhatsApp Service")
4. Choose **Whatsapp** as the channel
5. Select **Sandbox** first for testing (free until production)
6. Follow the setup wizard to configure WhatsApp sandbox
7. You'll receive a sandbox WhatsApp number (e.g., `whatsapp:+1234567890`)
8. Save this number for WhatsApp configuration

### Step 5: Configure Environment Variables

Once you have your credentials, set them as environment variables before running the backend:

**On Linux/macOS:**
```bash
export TWILIO_ENABLED=true
export TWILIO_ACCOUNT_SID="AC1234567890abcdefghijklmnopqrst"
export TWILIO_AUTH_TOKEN="your_auth_token_here"
export TWILIO_PHONE_NUMBER="+1234567890"
export TWILIO_WHATSAPP_NUMBER="whatsapp:+1234567890"
```

**On Windows (PowerShell):**
```powershell
$env:TWILIO_ENABLED="true"
$env:TWILIO_ACCOUNT_SID="AC1234567890abcdefghijklmnopqrst"
$env:TWILIO_AUTH_TOKEN="your_auth_token_here"
$env:TWILIO_PHONE_NUMBER="+1234567890"
$env:TWILIO_WHATSAPP_NUMBER="whatsapp:+1234567890"
```

**Or create a `.env` file in the project root:**
```
TWILIO_ENABLED=true
TWILIO_ACCOUNT_SID=AC1234567890abcdefghijklmnopqrst
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890
```

### Step 6: Install Twilio Package (If Not Already Done)

```bash
pip install -r backend/requirements.txt
```

This installs the Twilio Python SDK automatically.

### Step 7: Test Your Configuration

1. Start the backend:
```bash
uvicorn app.main:app --reload --app-dir backend
```

2. In another terminal, test the OTP request endpoint:
```bash
curl -X POST http://localhost:8000/api/v1/otp/request \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+1234567890",
    "email": "user@example.com",
    "locale": "en",
    "preferred_channel": "sms"
  }'
```

3. Check the response for `"fraud_blocked": false` and look for "OTP sent via sms" in the notes
4. You should receive an SMS on the phone number you provided

## Troubleshooting

### "Twilio is not enabled or not configured"
- Verify `TWILIO_ENABLED=true` is set
- Check that `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are correctly set

### "Invalid phone number"
- Ensure phone numbers include country code (e.g., `+1` for US, `+91` for India)
- Phone numbers must be in E.164 format: `+{CountryCode}{PhoneNumber}`

### SMS not received
- Verify you have a valid Twilio phone number (purchased in Step 3)
- Check the Twilio Console > **Logs** to see any error messages
- Ensure you have sufficient account balance/credits

### WhatsApp sandbox issues
- WhatsApp sandbox requires two-way message exchange for testing
- First send "join TRIGGER_WORD" from your phone to the sandbox number
- Only then can the service send to you

## Production Considerations

1. **Upgrade WhatsApp**: Move from Sandbox to Production for commercial use
2. **Rate Limits**: Twilio has rate limits; check your account limits
3. **Costs**: SMS costs vary by country (typically $0.0075-$0.50 per message)
4. **Security**: Store credentials in a secrets manager, not in version control
5. **Fallback Strategy**: Configure fallback channels if one fails
6. **Monitoring**: Set up Twilio SNS webhooks to monitor delivery status

## API Reference

### OTP Request with Channel Selection

```bash
curl -X POST http://localhost:8000/api/v1/otp/request \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+919876543210",
    "email": "user@example.com",
    "locale": "en",
    "preferred_channel": "sms",
    "template_key": "default_otp"
  }'
```

**Response:**
```json
{
  "session_id": "uuid-here",
  "destination": "+919876543210",
  "channel_used": "sms",
  "fallback_channels": ["whatsapp", "email"],
  "expires_at": "2026-04-10T12:30:00+00:00",
  "sender_id": "GV-TECH",
  "fraud_blocked": false,
  "notes": [
    "Least-cost routing selected a healthy gateway.",
    "Template default_otp applied.",
    "OTP sent via sms"
  ]
}
```

## Support

For Twilio support and documentation:
- [Twilio Documentation](https://www.twilio.com/docs)
- [Twilio SMS Documentation](https://www.twilio.com/docs/sms)
- [Twilio WhatsApp Documentation](https://www.twilio.com/docs/whatsapp)
- [Twilio Support](https://support.twilio.com)
