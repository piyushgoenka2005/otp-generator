from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Iterator

from .settings import settings


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS templates (
    key TEXT NOT NULL,
    language TEXT NOT NULL,
    body TEXT NOT NULL,
    channel TEXT NOT NULL,
    variables TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    PRIMARY KEY (key, language)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    phone TEXT NOT NULL,
    email TEXT,
    channel TEXT NOT NULL,
    fallback_channels TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    template_key TEXT NOT NULL,
    locale TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    verified_at TEXT,
    latency_ms INTEGER NOT NULL,
    ip_address TEXT,
    fraud_score REAL NOT NULL DEFAULT 0,
    fraud_reason TEXT,
    webhook_signature TEXT,
    cost REAL NOT NULL DEFAULT 0,
    billed INTEGER NOT NULL DEFAULT 0,
    verify_attempts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendors (
    name TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    cost_per_message REAL NOT NULL,
    latency_ms INTEGER NOT NULL,
    healthy INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT NOT NULL,
    amount REAL NOT NULL,
    gst_amount REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
    name TEXT PRIMARY KEY,
    permissions TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_users (
    username TEXT PRIMARY KEY,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


SEED_TEMPLATES = [
    ("default_otp", "en", "Your verification code is {{code}}.", "sms", '["code"]'),
    ("default_otp", "hi", "आपका सत्यापन कोड {{code}} है।", "sms", '["code"]'),
    ("welcome_otp", "en", "Use {{code}} to complete sign in for {{brand}}.", "whatsapp", '["code", "brand"]'),
]

SEED_VENDORS = [
    ("Primary SMS Gateway", "sms", 0.012, 1200, 1),
    ("Backup SMS Gateway", "sms", 0.015, 1350, 1),
    ("Email Relay", "email", 0.004, 900, 1),
    ("WhatsApp Cloud", "whatsapp", 0.02, 1100, 1),
]

SEED_ROLES = [
    ("support", '["read_sessions", "resend_otp"]'),
    ("finance", '["read_billing", "export_invoices"]'),
    ("admin", '["read_sessions", "resend_otp", "manage_templates", "read_billing", "read_fraud", "manage_roles"]'),
]


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)
        session_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "verify_attempts" not in session_columns:
            connection.execute("ALTER TABLE sessions ADD COLUMN verify_attempts INTEGER NOT NULL DEFAULT 0")
        for record in SEED_TEMPLATES:
            connection.execute(
                """
                INSERT OR IGNORE INTO templates (key, language, body, channel, variables, active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (*record, datetime.now(timezone.utc).isoformat()),
            )
        for record in SEED_VENDORS:
            connection.execute(
                """
                INSERT OR IGNORE INTO vendors (name, channel, cost_per_message, latency_ms, healthy)
                VALUES (?, ?, ?, ?, ?)
                """,
                record,
            )
        for record in SEED_ROLES:
            connection.execute(
                """
                INSERT OR IGNORE INTO roles (name, permissions)
                VALUES (?, ?)
                """,
                record,
            )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utcnow().isoformat()


def parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def ensure_seeded() -> None:
    if not settings.database_path.exists():
        initialize_database()
