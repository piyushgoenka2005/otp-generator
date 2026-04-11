from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any
from urllib import error, request as urlrequest
from uuid import uuid4

from .settings import settings
from .store import connect, ensure_seeded, iso_now, parse_dt, utcnow
from .twilio_sender import sender as twilio_sender


CHANNEL_PRIORITY = ["sms", "whatsapp", "email"]


@dataclass(frozen=True)
class IssueResult:
    session_id: str
    destination: str
    channel_used: str
    fallback_channels: list[str]
    expires_at: datetime
    sender_id: str
    fraud_blocked: bool
    notes: list[str]
    test_code: str | None


@dataclass(frozen=True)
class VerifyResult:
    verified: bool
    verified_at: datetime | None
    webhook_signature: str | None
    message: str


class OtpPlatformService:
    def __init__(self) -> None:
        ensure_seeded()

    def issue_otp(self, payload: dict[str, Any]) -> IssueResult:
        phone = payload["phone"]
        email = payload.get("email")
        locale = payload.get("locale", "en")
        preferred_channel = payload.get("preferred_channel")
        template_key = payload.get("template_key", "default_otp")
        ip_address = payload.get("ip_address")

        limited, limit_reason = self._rate_limit_block(phone, ip_address)
        if limited:
            channel_used = preferred_channel or "sms"
            return self._store_session(
                phone=phone,
                email=email,
                locale=locale,
                channel=channel_used,
                fallback_channels=self._fallback_channels(channel_used),
                template_key=template_key,
                ip_address=ip_address,
                fraud_score=100.0,
                fraud_reason=limit_reason,
                blocked=True,
                notes=["Request blocked by rate limits."],
            )

        fraud_score, fraud_reason, blocked = self._score_fraud(phone, ip_address)
        if blocked:
            channel_used = preferred_channel or "sms"
            return self._store_session(
                phone=phone,
                email=email,
                locale=locale,
                channel=channel_used,
                fallback_channels=self._fallback_channels(channel_used),
                template_key=template_key,
                ip_address=ip_address,
                fraud_score=fraud_score,
                fraud_reason=fraud_reason,
                blocked=True,
                notes=["Request blocked by fraud controls."],
            )

        channel_used = self._select_channel(preferred_channel)
        fallback_channels = self._fallback_channels(channel_used)
        notes = ["Least-cost routing selected a healthy gateway."]
        if channel_used != preferred_channel and preferred_channel:
            notes.append(f"Preferred channel {preferred_channel} was unavailable, failover engaged.")

        return self._store_session(
            phone=phone,
            email=email,
            locale=locale,
            channel=channel_used,
            fallback_channels=fallback_channels,
            template_key=template_key,
            ip_address=ip_address,
            fraud_score=fraud_score,
            fraud_reason=fraud_reason,
            blocked=False,
            notes=notes,
        )

    def verify_otp(self, payload: dict[str, Any]) -> VerifyResult:
        session_id = payload["session_id"]
        code = payload["code"]
        ip_address = payload.get("ip_address")

        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return VerifyResult(False, None, None, "Session not found.")

            if row["status"] == "verified":
                return VerifyResult(True, parse_dt(row["verified_at"]), row["webhook_signature"], "OTP already verified.")

            if parse_dt(row["expires_at"]) < utcnow():
                connection.execute(
                    "UPDATE sessions SET status = 'expired' WHERE session_id = ?",
                    (session_id,),
                )
                return VerifyResult(False, None, None, "OTP has expired.")

            if int(row["verify_attempts"] or 0) >= settings.otp_verify_attempt_limit:
                connection.execute(
                    "UPDATE sessions SET status = 'blocked' WHERE session_id = ?",
                    (session_id,),
                )
                connection.execute(
                    "INSERT INTO events (session_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                    (
                        session_id,
                        "verification_rate_limited",
                        json.dumps({"ip_address": ip_address}),
                        iso_now(),
                    ),
                )
                return VerifyResult(False, None, None, "Too many verification attempts. Session blocked.")

            expected_hash = self._hash_code(code, row["salt"])
            if expected_hash != row["code_hash"]:
                connection.execute(
                    "UPDATE sessions SET verify_attempts = verify_attempts + 1 WHERE session_id = ?",
                    (session_id,),
                )
                connection.execute(
                    "INSERT INTO events (session_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                    (session_id, "verification_failed", json.dumps({"ip_address": ip_address}), iso_now()),
                )
                return VerifyResult(False, None, None, "Invalid verification code.")

            verified_at = utcnow()
            signature = self._sign_webhook({
                "session_id": session_id,
                "phone": row["phone"],
                "verified_at": verified_at.isoformat(),
                "channel": row["channel"],
            })
            connection.execute(
                """
                UPDATE sessions
                SET status = 'verified', verified_at = ?, webhook_signature = ?
                WHERE session_id = ?
                """,
                (verified_at.isoformat(), signature, session_id),
            )
            connection.execute(
                "INSERT INTO events (session_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (session_id, "verified", json.dumps({"ip_address": ip_address}), iso_now()),
            )
            self._bill_verified_session(connection, row)

            webhook_payload = {
                "session_id": session_id,
                "phone": row["phone"],
                "verified_at": verified_at.isoformat(),
                "channel": row["channel"],
            }
            webhook_status = self._dispatch_verified_webhook(webhook_payload, signature)
            connection.execute(
                "INSERT INTO events (session_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (
                    session_id,
                    "webhook_delivered" if webhook_status.get("success") else "webhook_failed",
                    json.dumps(webhook_status),
                    iso_now(),
                ),
            )
            return VerifyResult(True, verified_at, signature, "OTP verified successfully.")

    def list_templates(self) -> list[dict[str, Any]]:
        with connect() as connection:
            rows = connection.execute("SELECT * FROM templates ORDER BY key, language").fetchall()
            return [self._template_row(row) for row in rows]

    def create_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO templates (key, language, body, channel, variables, active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(key, language) DO UPDATE SET
                    body = excluded.body,
                    channel = excluded.channel,
                    variables = excluded.variables,
                    active = 1
                """,
                (
                    payload["key"],
                    payload.get("language", "en"),
                    payload["body"],
                    payload.get("channel", "sms"),
                    json.dumps(payload.get("variables", [])),
                    iso_now(),
                ),
            )
        return self.get_template(payload["key"], payload.get("language", "en"))

    def get_template(self, key: str, language: str) -> dict[str, Any]:
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM templates WHERE key = ? AND language = ?",
                (key, language),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT * FROM templates WHERE key = ? AND language = 'en'",
                    (key,),
                ).fetchone()
            if row is None:
                raise ValueError(f"Template '{key}' not found")
            return self._template_row(row)

    def analytics_summary(self) -> dict[str, Any]:
        with connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            verified = connection.execute("SELECT COUNT(*) FROM sessions WHERE status = 'verified'").fetchone()[0]
            blocked = connection.execute("SELECT COUNT(*) FROM sessions WHERE status = 'blocked'").fetchone()[0]
            avg_latency = connection.execute("SELECT COALESCE(AVG(latency_ms), 0) FROM sessions").fetchone()[0]
            channel_rows = connection.execute(
                "SELECT channel, COUNT(*) AS count FROM sessions GROUP BY channel"
            ).fetchall()

            delivery_rate = round((verified / total) * 100, 1) if total else 0.0
            return {
                "generated_at": iso_now(),
                "delivery_rate": delivery_rate,
                "avg_latency_ms": round(float(avg_latency), 1),
                "verified_sessions": verified,
                "blocked_sessions": blocked,
                "total_sessions": total,
                "channel_mix": {row["channel"]: row["count"] for row in channel_rows},
            }

    def billing_summary(self) -> dict[str, Any]:
        with connect() as connection:
            balance = connection.execute(
                "SELECT COALESCE(SUM(cost), 0) FROM sessions WHERE billed = 1"
            ).fetchone()[0]
            invoices = connection.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
            invoice_total = connection.execute(
                "SELECT COALESCE(SUM(amount + gst_amount), 0) FROM invoices"
            ).fetchone()[0]
            return {
                "current_balance": round(float(balance), 2),
                "currency": "INR",
                "gst_rate": settings.gst_rate,
                "invoice_total": round(float(invoice_total), 2),
                "issued_invoices": invoices,
            }

    def fraud_signals(self) -> list[dict[str, Any]]:
        with connect() as connection:
            rows = connection.execute(
                "SELECT session_id, phone, ip_address, fraud_score, fraud_reason, status FROM sessions ORDER BY created_at DESC LIMIT 25"
            ).fetchall()
            return [
                {
                    "session_id": row["session_id"],
                    "phone": row["phone"],
                    "ip_address": row["ip_address"],
                    "score": round(float(row["fraud_score"]), 2),
                    "reason": row["fraud_reason"] or "No suspicious activity detected.",
                    "blocked": row["status"] == "blocked",
                }
                for row in rows
            ]

    def vendor_routes(self) -> list[dict[str, Any]]:
        with connect() as connection:
            rows = connection.execute("SELECT * FROM vendors ORDER BY channel, latency_ms").fetchall()
            return [
                {
                    "name": row["name"],
                    "channel": row["channel"],
                    "cost_per_message": row["cost_per_message"],
                    "latency_ms": row["latency_ms"],
                    "healthy": bool(row["healthy"]),
                }
                for row in rows
            ]

    def roles(self) -> list[dict[str, Any]]:
        with connect() as connection:
            rows = connection.execute("SELECT * FROM roles ORDER BY name").fetchall()
            return [
                {"name": row["name"], "permissions": json.loads(row["permissions"])} for row in rows
            ]

    def health(self) -> dict[str, Any]:
        with connect() as connection:
            sessions = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            templates = connection.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
            vendors = connection.execute("SELECT COUNT(*) FROM vendors WHERE healthy = 1").fetchone()[0]
            return {
                "status": "ok",
                "database": "ready",
                "sessions": sessions,
                "templates": templates,
                "healthy_vendors": vendors,
                "redis_bus_enabled": settings.use_redis_bus,
            }

    def _store_session(
        self,
        *,
        phone: str,
        email: str | None,
        locale: str,
        channel: str,
        fallback_channels: list[str],
        template_key: str,
        ip_address: str | None,
        fraud_score: float,
        fraud_reason: str | None,
        blocked: bool,
        notes: list[str],
    ) -> IssueResult:
        session_id = str(uuid4())
        code = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_hex(8)
        created_at = utcnow()
        expires_at = created_at + timedelta(minutes=5)
        template = self.get_template(template_key, locale)
        latency_ms = self._gateway_latency(channel)
        cost = self._gateway_cost(channel)
        status = "blocked" if blocked else "issued"
        sender_id = settings.default_sender_id
        
        # Render message template with the OTP code
        message = self._render_template(template["body"], code)
        
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id, phone, email, channel, fallback_channels, code_hash, salt,
                    template_key, locale, sender_id, status, created_at, expires_at,
                    verified_at, latency_ms, ip_address, fraud_score, fraud_reason, cost, billed, verify_attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, 0, 0)
                """,
                (
                    session_id,
                    phone,
                    email,
                    channel,
                    json.dumps(fallback_channels),
                    self._hash_code(code, salt),
                    salt,
                    template["key"],
                    locale,
                    sender_id,
                    status,
                    created_at.isoformat(),
                    expires_at.isoformat(),
                    latency_ms,
                    ip_address,
                    fraud_score,
                    fraud_reason,
                    cost,
                ),
            )
            connection.execute(
                "INSERT INTO events (session_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (
                    session_id,
                    "issued" if not blocked else "blocked",
                    json.dumps({"destination": phone, "channel": channel, "template": template["key"]}),
                    iso_now(),
                ),
            )
        
        # Send OTP via selected channel and automatic fallback channels (unless blocked)
        send_status = None
        delivery_channel = channel
        if not blocked:
            for candidate_channel in [channel] + fallback_channels:
                if candidate_channel == "email" and not email:
                    with connect() as connection:
                        connection.execute(
                            "INSERT INTO events (session_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                            (
                                session_id,
                                "otp_send_failed",
                                json.dumps({"channel": candidate_channel, "error": "Missing email destination"}),
                                iso_now(),
                            ),
                        )
                    continue

                send_status = self._send_otp_via_channel(phone, email, candidate_channel, message)
                with connect() as connection:
                    if send_status.get("success"):
                        connection.execute(
                            "INSERT INTO events (session_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                            (
                                session_id,
                                "otp_sent",
                                json.dumps({
                                    "channel": candidate_channel,
                                    "message_sid": send_status.get("message_sid"),
                                    "status": send_status.get("status"),
                                }),
                                iso_now(),
                            ),
                        )
                    else:
                        connection.execute(
                            "INSERT INTO events (session_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                            (
                                session_id,
                                "otp_send_failed",
                                json.dumps({"channel": candidate_channel, "error": send_status.get("error")}),
                                iso_now(),
                            ),
                        )

                if send_status.get("success"):
                    delivery_channel = candidate_channel
                    if candidate_channel != channel:
                        notes.append(f"Primary channel {channel} failed. Failover delivered OTP via {candidate_channel}.")
                    notes.append(f"OTP sent via {candidate_channel}")
                    break

            if not send_status or not send_status.get("success"):
                notes.append(f"OTP send failed on all channels. Last error: {send_status.get('error') if send_status else 'No channel available'}")

        return IssueResult(
            session_id=session_id,
            destination=phone if delivery_channel != "email" else (email or phone),
            channel_used=delivery_channel,
            fallback_channels=fallback_channels,
            expires_at=expires_at,
            sender_id=sender_id,
            fraud_blocked=blocked,
            notes=notes + [f"Template {template['key']} applied."] + ([f"Fraud score: {fraud_score:.2f}"] if fraud_reason else []),
            test_code=code if settings.otp_expose_test_code else None,
        )

    def _render_template(self, template_body: str, code: str) -> str:
        """Render OTP template with the generated code."""
        return template_body.replace("{{code}}", code)

    def _send_otp_via_channel(self, phone: str, email: str | None, channel: str, message: str) -> dict[str, Any]:
        """Send OTP via the selected channel using Twilio."""
        return twilio_sender.send_otp(phone, email, channel, message)

    def _select_channel(self, preferred_channel: str | None) -> str:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT channel, MIN(cost_per_message) AS min_cost, MIN(latency_ms) AS min_latency
                FROM vendors
                WHERE healthy = 1
                GROUP BY channel
                """
            ).fetchall()
            healthy_channels = {row["channel"] for row in rows}
            channel_scores = {
                row["channel"]: float(row["min_cost"]) * 1000 + float(row["min_latency"]) / 1000 for row in rows
            }

        if preferred_channel and preferred_channel in healthy_channels:
            return preferred_channel

        if channel_scores:
            ranked = sorted(channel_scores.items(), key=lambda item: item[1])
            return ranked[0][0]

        candidate_order = ([preferred_channel] if preferred_channel else []) + CHANNEL_PRIORITY
        for candidate in candidate_order:
            if candidate and candidate in healthy_channels:
                return candidate
        return "sms"

    def _rate_limit_block(self, phone: str, ip_address: str | None) -> tuple[bool, str | None]:
        phone_window = (utcnow() - timedelta(minutes=settings.otp_phone_limit_window_minutes)).isoformat()
        ip_window = (utcnow() - timedelta(minutes=settings.otp_ip_limit_window_minutes)).isoformat()
        with connect() as connection:
            phone_count = connection.execute(
                "SELECT COUNT(*) FROM sessions WHERE phone = ? AND created_at >= ?",
                (phone, phone_window),
            ).fetchone()[0]
            if phone_count >= settings.otp_phone_limit_count:
                return True, "Phone request rate exceeded."

            if ip_address:
                ip_count = connection.execute(
                    "SELECT COUNT(*) FROM sessions WHERE ip_address = ? AND created_at >= ?",
                    (ip_address, ip_window),
                ).fetchone()[0]
                if ip_count >= settings.otp_ip_limit_count:
                    return True, "IP request rate exceeded."

        return False, None

    def _fallback_channels(self, channel: str) -> list[str]:
        return [candidate for candidate in CHANNEL_PRIORITY if candidate != channel]

    def _gateway_latency(self, channel: str) -> int:
        with connect() as connection:
            row = connection.execute(
                "SELECT latency_ms FROM vendors WHERE channel = ? AND healthy = 1 ORDER BY latency_ms LIMIT 1",
                (channel,),
            ).fetchone()
            return int(row[0]) if row else 1200

    def _gateway_cost(self, channel: str) -> float:
        with connect() as connection:
            row = connection.execute(
                "SELECT cost_per_message FROM vendors WHERE channel = ? AND healthy = 1 ORDER BY cost_per_message LIMIT 1",
                (channel,),
            ).fetchone()
            return float(row[0]) if row else 0.01

    def _score_fraud(self, phone: str, ip_address: str | None) -> tuple[float, str | None, bool]:
        with connect() as connection:
            recent_phone_count = connection.execute(
                """
                SELECT COUNT(*) FROM sessions
                WHERE phone = ? AND created_at >= ?
                """,
                (phone, (utcnow() - timedelta(minutes=10)).isoformat()),
            ).fetchone()[0]
            recent_ip_count = 0
            if ip_address:
                recent_ip_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM sessions
                    WHERE ip_address = ? AND created_at >= ?
                    """,
                    (ip_address, (utcnow() - timedelta(minutes=5)).isoformat()),
                ).fetchone()[0]

        score = min(100.0, float(recent_phone_count * 34 + recent_ip_count * 18))
        if score >= 70:
            return score, "OTP pumping suspected due to request velocity.", True
        if score >= 40:
            return score, "Suspicious request rate detected.", False
        return score, None, False

    def _hash_code(self, code: str, salt: str) -> str:
        digest = hashlib.sha256()
        digest.update(f"{salt}:{code}".encode("utf-8"))
        return digest.hexdigest()

    def _sign_webhook(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            settings.webhook_secret.encode("utf-8"),
            serialized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _bill_verified_session(self, connection, row) -> None:
        if row["billed"]:
            return
        amount = float(row["cost"] or 0.0)
        gst_amount = round(amount * settings.gst_rate, 2)
        invoice_no = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.randbelow(10000):04d}"
        connection.execute(
            "INSERT INTO invoices (invoice_no, amount, gst_amount, created_at) VALUES (?, ?, ?, ?)",
            (invoice_no, amount, gst_amount, iso_now()),
        )
        connection.execute(
            "UPDATE sessions SET billed = 1 WHERE session_id = ?",
            (row["session_id"],),
        )

    def _dispatch_verified_webhook(self, payload: dict[str, Any], signature: str) -> dict[str, Any]:
        if not settings.webhook_url:
            return {"success": True, "status": "skipped", "reason": "OTP_WEBHOOK_URL not configured"}

        data = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            settings.webhook_url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-OTP-Signature": signature,
            },
        )

        try:
            with urlrequest.urlopen(req, timeout=settings.webhook_timeout_seconds) as response:
                return {
                    "success": True,
                    "status": "delivered",
                    "http_status": response.status,
                }
        except error.HTTPError as exc:
            return {
                "success": False,
                "status": "http_error",
                "http_status": exc.code,
                "error": str(exc),
            }
        except Exception as exc:
            return {
                "success": False,
                "status": "network_error",
                "error": str(exc),
            }

    def _template_row(self, row) -> dict[str, Any]:
        return {
            "key": row["key"],
            "language": row["language"],
            "body": row["body"],
            "channel": row["channel"],
            "variables": json.loads(row["variables"]),
            "active": bool(row["active"]),
            "created_at": parse_dt(row["created_at"]),
        }


service = OtpPlatformService()
