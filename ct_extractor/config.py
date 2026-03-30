from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    subdomain: str
    email: str
    password: str
    base_domain: str = "thecasetracking.com"
    token_file: Path = Path(".ct_token.json")
    timeout_seconds: float = 30.0

    @property
    def base_url(self) -> str:
        return f"https://{self.subdomain}.{self.base_domain}"

    @classmethod
    def from_env(cls) -> "Settings":
        subdomain = os.getenv("CT_SUBDOMAIN", "").strip()
        email = os.getenv("CT_EMAIL", "").strip()
        password = os.getenv("CT_PASSWORD", "").strip()
        base_domain = os.getenv("CT_BASE_DOMAIN", "thecasetracking.com").strip()
        token_file_raw = os.getenv("CT_TOKEN_FILE", ".ct_token.json").strip()
        timeout_raw = os.getenv("CT_TIMEOUT_SECONDS", "30").strip()

        missing = [
            env_name
            for env_name, value in (
                ("CT_SUBDOMAIN", subdomain),
                ("CT_EMAIL", email),
                ("CT_PASSWORD", password),
            )
            if not value
        ]
        if missing:
            missing_items = ", ".join(missing)
            raise ValueError(f"Faltan variables de entorno requeridas: {missing_items}")

        try:
            timeout_seconds = float(timeout_raw)
        except ValueError as exc:
            raise ValueError("CT_TIMEOUT_SECONDS debe ser numérico.") from exc

        token_file = Path(token_file_raw).expanduser()
        return cls(
            subdomain=subdomain,
            email=email,
            password=password,
            base_domain=base_domain,
            token_file=token_file,
            timeout_seconds=timeout_seconds,
        )

