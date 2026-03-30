from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import Settings


@dataclass(frozen=True)
class AuthSession:
    auth_token: str
    email: str
    user_id: int | None
    generated_at: str
    base_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "auth_token": self.auth_token,
            "email": self.email,
            "id": self.user_id,
            "generated_at": self.generated_at,
            "base_url": self.base_url,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuthSession":
        return cls(
            auth_token=str(payload["auth_token"]),
            email=str(payload.get("email", "")),
            user_id=payload.get("id"),
            generated_at=str(payload.get("generated_at", "")),
            base_url=str(payload.get("base_url", "")),
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_token_file(path: Path) -> Path:
    return path.resolve() if not path.is_absolute() else path


class TokenStore:
    def __init__(self, token_file: Path) -> None:
        self.token_file = _resolve_token_file(token_file)

    def load(self) -> AuthSession | None:
        if not self.token_file.exists():
            return None
        content = json.loads(self.token_file.read_text(encoding="utf-8"))
        return AuthSession.from_dict(content)

    def save(self, session: AuthSession) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class AuthClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def sign_in(self) -> AuthSession:
        url = f"{self.settings.base_url}/api/sign_in"
        payload = {
            "email": self.settings.email,
            "password": self.settings.password,
        }
        with httpx.Client(timeout=self.settings.timeout_seconds) as client:
            response = client.post(url, json=payload)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Error autenticando ({response.status_code}) en {url}: {response.text}"
            ) from exc

        data = response.json()
        token = str(data.get("auth_token", "")).strip()
        if not token:
            raise RuntimeError("La respuesta de sign_in no incluyó auth_token.")

        return AuthSession(
            auth_token=token,
            email=str(data.get("email", self.settings.email)),
            user_id=data.get("id"),
            generated_at=_utc_now_iso(),
            base_url=self.settings.base_url,
        )

