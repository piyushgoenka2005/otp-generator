// Web SDK-style helper for OTP request + verify.
const API_BASE = 'http://127.0.0.1:8000/api/v1';

export async function requestOtp({ phone, email, locale = 'en', preferredChannel = 'sms' }) {
  const response = await fetch(`${API_BASE}/otp/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phone,
      email,
      locale,
      preferred_channel: preferredChannel,
      template_key: 'default_otp',
    }),
  });

  if (!response.ok) {
    throw new Error(`OTP request failed: ${response.status}`);
  }
  return response.json();
}

export async function verifyOtp({ sessionId, code }) {
  const response = await fetch(`${API_BASE}/otp/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, code }),
  });

  if (!response.ok) {
    throw new Error(`OTP verify failed: ${response.status}`);
  }
  return response.json();
}
