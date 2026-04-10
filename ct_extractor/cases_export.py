from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import httpx

from .config import Settings


class CasesExportClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._path = "/ct/cases.xlsx"

    def _build_auth_headers(self, token: str, email: str | None) -> list[dict[str, str]]:
        headers = [
            {"AUTHTOKEN": token},
            {"Authorization": f"Token token={token}"},
            {"Authorization": f"Bearer {token}"},
            {"X-Auth-Token": token},
            {"Auth-Token": token},
        ]
        if email:
            headers.append({"X-User-Token": token, "X-User-Email": email})
        return headers

    @staticmethod
    def _is_sign_in_redirect(response: httpx.Response) -> bool:
        if response.status_code not in (301, 302, 303, 307, 308):
            return False
        location = (response.headers.get("location") or "").lower()
        return "/users/sign_in" in location

    @staticmethod
    def _filtered_params() -> dict[str, Any]:
        return {
            "filters[code][value]": "C-",
            "filters[code][type]": "like",
            "filters[url][value]": "1",
            "filters[url][type]": "is_null",
            "filters[active][value]": "1",
            "filters[active][type]": "equal",
            "report": "",
            "cols[]": [
                "extra_text_1",
                "code",
                "extra_num_10",
                "extra_ref_16.name",
            ],
            "sort_col": "",
            "sort_dir": "",
            "size_limit_exceeded": "true",
            "size": "1648",
        }

    @staticmethod
    def _full_ct_params() -> dict[str, Any]:
        return {
            "report": "",
            "cols[]": [
                "extra_text_1",
                "code",
                "court.name",
                "extra_num_10",
                "active_str",
                "extra_text_74",
                "extra_text_75",
                "extra_ref_15.name",
                "extra_text_78",
                "extra_num_11",
                "extra_ref_4.name",
                "extra_ref_14.name",
                "extra_date_36__DAYSSINCE",
                "last_label.name",
                "prioritized_milestone.name",
                "last_movement_title",
                "last_review",
                "credential.id",
                "credential.name",
                "credential.username",
                "court.last_daily_scrap",
                "extra_date_29",
                "title",
                "last_movement_official_date",
                "extra_date_13",
                "extra_date_14",
                "extra_ref_16.name",
            ],
            "sort_col": "",
            "sort_dir": "",
            "size_limit_exceeded": "true",
            "size": "876",
        }

    @staticmethod
    def _looks_like_xlsx(content: bytes) -> bool:
        return len(content) > 4 and content[:2] == b"PK"

    @staticmethod
    def _extract_attachment_id(response: httpx.Response) -> str | None:
        text = response.text.strip()
        if re.fullmatch(r"[0-9a-f]{24}", text):
            return text
        return None

    def _download_attachment(
        self,
        client: httpx.Client,
        auth_headers: dict[str, str],
        attachment_id: str,
    ) -> bytes | None:
        url = f"{self.settings.base_url}/attachments/{attachment_id}/download"
        response = client.get(
            url,
            headers={
                "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream,*/*",
                "User-Agent": "ct-cases-export/1.0",
                **auth_headers,
            },
            follow_redirects=True,
        )
        if response.status_code == 404:
            return None
        if response.status_code == 401 or self._is_sign_in_redirect(response):
            raise RuntimeError("Token invalido/expirado al consultar /attachments/:id/download.")
        if response.status_code >= 400:
            body = response.text[:300]
            raise RuntimeError(
                "Error descargando /attachments/:id/download. "
                f"Status: {response.status_code}. Respuesta: {body}"
            )
        if self._looks_like_xlsx(response.content):
            return response.content
        return None

    def download_by_attachment_id(
        self,
        token: str,
        email: str | None,
        attachment_id: str,
        output_path: Path,
    ) -> Path | None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        auth_header_candidates = self._build_auth_headers(token=token, email=email)
        with httpx.Client(timeout=self.settings.timeout_seconds) as client:
            for auth_headers in auth_header_candidates:
                content = self._download_attachment(
                    client=client,
                    auth_headers=auth_headers,
                    attachment_id=attachment_id,
                )
                if content:
                    output_path.write_bytes(content)
                    return output_path.resolve()
        return None

    def download(
        self,
        token: str,
        email: str | None,
        output_path: Path,
        export_mode: str = "filtered",
        wait_timeout_seconds: int = 0,
        poll_interval_seconds: int = 10,
    ) -> tuple[Path | None, str | None]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"{self.settings.base_url}{self._path}"
        params = (
            self._full_ct_params() if export_mode == "full-ct" else self._filtered_params()
        )
        auth_header_candidates = self._build_auth_headers(token=token, email=email)

        with httpx.Client(timeout=self.settings.timeout_seconds) as client:
            last_response: httpx.Response | None = None
            attachment_id: str | None = None
            selected_auth_headers: dict[str, str] | None = None
            for auth_headers in auth_header_candidates:
                headers = {
                    "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream,*/*",
                    "User-Agent": "ct-cases-export/1.0",
                    **auth_headers,
                }
                response = client.get(
                    url,
                    params=params,
                    headers=headers,
                    follow_redirects=False,
                )
                last_response = response

                if response.status_code == 401 or self._is_sign_in_redirect(response):
                    continue
                if response.status_code >= 400:
                    continue
                if not response.content:
                    continue
                if self._looks_like_xlsx(response.content):
                    output_path.write_bytes(response.content)
                    return output_path.resolve(), None
                attachment_id = self._extract_attachment_id(response)
                if attachment_id:
                    selected_auth_headers = auth_headers
                    break
            if attachment_id and selected_auth_headers:
                if wait_timeout_seconds <= 0:
                    return None, attachment_id

                started_at = time.monotonic()
                while time.monotonic() - started_at < wait_timeout_seconds:
                    content = self._download_attachment(
                        client=client,
                        auth_headers=selected_auth_headers,
                        attachment_id=attachment_id,
                    )
                    if content:
                        output_path.write_bytes(content)
                        return output_path.resolve(), attachment_id
                    time.sleep(max(1, poll_interval_seconds))

                return None, attachment_id

        status_code = last_response.status_code if last_response else "desconocido"
        body = last_response.text if last_response else ""
        raise RuntimeError(
            "No fue posible descargar cases.xlsx. "
            f"Ultimo status: {status_code}. "
            f"Respuesta: {body[:300]}"
        )
