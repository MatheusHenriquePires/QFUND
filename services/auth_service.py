import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from database import db


class AuthService:
    ITERATIONS = 600_000
    ALGORITHM = "HS256"
    ISSUER = "qfund"
    AUDIENCE = "qfund-web"
    TOKEN_TTL_SECONDS = int(os.getenv("JWT_EXPIRE_MINUTES", "60")) * 60

    def __init__(self):
        self.secret = self._load_secret()

    def _load_secret(self):
        configured = os.getenv("JWT_SECRET")
        if configured:
            if len(configured.encode("utf-8")) < 32:
                raise RuntimeError("JWT_SECRET deve possuir pelo menos 32 bytes")
            return configured

        if os.getenv("VERCEL"):
            raise RuntimeError("Configure JWT_SECRET no ambiente de produção")

        secret_path = Path(__file__).resolve().parent.parent / "generated" / "jwt_secret.key"
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        if secret_path.exists():
            secret = secret_path.read_text(encoding="utf-8").strip()
            if len(secret.encode("utf-8")) >= 32:
                return secret

        secret = secrets.token_urlsafe(64)
        secret_path.write_text(secret, encoding="utf-8")
        return secret

    def hash_password(self, password: str):
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, self.ITERATIONS)
        return f"pbkdf2_sha256${self.ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"

    def verify_password(self, password: str, stored: str):
        try:
            algorithm, iterations, salt_b64, digest_b64 = stored.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(digest_b64)
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    def register(self, email: str, password: str, name: str, role: str):
        self._validate(email, password, name, role)
        user = db.create_user(email, self.hash_password(password), name, role)
        return user, self._issue_token(user)

    def login(self, email: str, password: str):
        user = db.get_user_by_email(email)
        if not user or not self.verify_password(password, user["password_hash"]):
            raise ValueError("E-mail ou senha inválidos")
        return user, self._issue_token(user)

    def _issue_token(self, user: dict):
        now = datetime.now(timezone.utc)
        session_id = db.create_session(user["id"], self.TOKEN_TTL_SECONDS)
        payload = {
            "iss": self.ISSUER,
            "aud": self.AUDIENCE,
            "sub": str(user["id"]),
            "jti": session_id,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(seconds=self.TOKEN_TTL_SECONDS),
            "type": "access",
        }
        return jwt.encode(payload, self.secret, algorithm=self.ALGORITHM)

    def decode_token(self, token: str, verify_expiration: bool = True):
        return jwt.decode(
            token,
            self.secret,
            algorithms=[self.ALGORITHM],
            audience=self.AUDIENCE,
            issuer=self.ISSUER,
            options={
                "require": ["iss", "aud", "sub", "jti", "iat", "nbf", "exp", "type"],
                "verify_exp": verify_expiration,
            },
        )

    def user_from_token(self, token: str | None):
        if not token:
            return None
        try:
            payload = self.decode_token(token)
            if payload.get("type") != "access":
                return None
            user = db.user_from_session(payload.get("jti"))
            if not user or str(user["id"]) != payload.get("sub"):
                return None
            return user
        except jwt.PyJWTError:
            return None

    def revoke_token(self, token: str | None):
        if not token:
            return
        try:
            payload = self.decode_token(token, verify_expiration=False)
            db.delete_session(payload.get("jti"))
        except jwt.PyJWTError:
            return

    def public_user(self, user: dict):
        return {
            "id": user["id"],
            "email": user["email"],
            "nome": user["name"],
            "tipo": user["role"],
            "disciplina_preferida": user.get("preferred_subject"),
        }

    def _validate(self, email, password, name, role):
        if "@" not in (email or "") or len(email) > 254:
            raise ValueError("Informe um e-mail válido")
        if len(password or "") < 8:
            raise ValueError("A senha deve ter pelo menos 8 caracteres")
        if not (name or "").strip():
            raise ValueError("Informe seu nome")
        if role not in ("professor", "usuario"):
            raise ValueError("Tipo de usuário inválido")


auth_service = AuthService()
