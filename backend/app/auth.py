from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .settings import settings
from .store import connect, initialize_database, utcnow


http_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()


def make_password_salt() -> str:
    return secrets.token_hex(16)


def _encode_part(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_part(value: str) -> dict[str, Any]:
    pad = "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(f"{value}{pad}".encode("ascii"))
    return json.loads(decoded.decode("utf-8"))


def create_access_token(*, username: str, role: str, permissions: list[str]) -> str:
    now = utcnow()
    exp = now + timedelta(minutes=settings.auth_ttl_minutes)
    header = {"alg": "HS256", "typ": "JWT"}
    body = {
        "sub": username,
        "role": role,
        "permissions": permissions,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    encoded_header = _encode_part(header)
    encoded_body = _encode_part(body)
    signature_payload = f"{encoded_header}.{encoded_body}".encode("utf-8")
    signature = hmac.new(settings.auth_secret.encode("utf-8"), signature_payload, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{encoded_header}.{encoded_body}.{encoded_signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    encoded_header, encoded_body, encoded_signature = parts
    signature_payload = f"{encoded_header}.{encoded_body}".encode("utf-8")
    expected_signature = hmac.new(settings.auth_secret.encode("utf-8"), signature_payload, hashlib.sha256).digest()
    expected_encoded_signature = base64.urlsafe_b64encode(expected_signature).rstrip(b"=").decode("ascii")

    if not hmac.compare_digest(expected_encoded_signature, encoded_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

    body = _decode_part(encoded_body)
    if int(body.get("exp", 0)) < int(utcnow().timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return body


def ensure_default_admin() -> None:
    initialize_database()
    username = settings.default_admin_username
    password = settings.default_admin_password
    if not username or not password:
        return
    with connect() as connection:
        role_row = connection.execute("SELECT permissions FROM roles WHERE name = 'admin'").fetchone()
        if role_row is None:
            permissions = ["manage_platform"]
        else:
            permissions = json.loads(role_row["permissions"])

        row = connection.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()
        if row is None:
            salt = make_password_salt()
            pwd_hash = hash_password(password, salt)
            now = utcnow().isoformat()
            connection.execute(
                """
                INSERT INTO admin_users (username, password_salt, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (username, salt, pwd_hash, "admin", now, now),
            )

        # Keep role permissions available even if role table changes later.
        if permissions:
            connection.execute(
                "UPDATE roles SET permissions = ? WHERE name = 'admin'",
                (json.dumps(permissions),),
            )


def authenticate_admin(username: str, password: str) -> dict[str, Any] | None:
    ensure_default_admin()
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM admin_users WHERE username = ? AND is_active = 1",
            (username,),
        ).fetchone()
        if row is None:
            return None

        expected_hash = hash_password(password, row["password_salt"])
        if not hmac.compare_digest(expected_hash, row["password_hash"]):
            return None

        role = row["role"]
        role_row = connection.execute("SELECT permissions FROM roles WHERE name = ?", (role,)).fetchone()
        permissions = json.loads(role_row["permissions"]) if role_row else []
        return {"username": row["username"], "role": role, "permissions": permissions}


def get_current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer)) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token_claims = decode_access_token(credentials.credentials)
    username = token_claims.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    initialize_database()
    with connect() as connection:
        row = connection.execute(
            "SELECT username, role, is_active FROM admin_users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None or not bool(row["is_active"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin user is inactive")

        role_row = connection.execute("SELECT permissions FROM roles WHERE name = ?", (row["role"],)).fetchone()
        permissions = json.loads(role_row["permissions"]) if role_row else []
        return {"username": row["username"], "role": row["role"], "permissions": permissions}


def require_permissions(required_permissions: list[str]):
    def dependency(current_admin: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
        granted = set(current_admin.get("permissions", []))
        missing = [perm for perm in required_permissions if perm not in granted]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing)}",
            )
        return current_admin

    return dependency
