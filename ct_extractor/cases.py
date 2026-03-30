from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from .config import Settings


class UntitledCasesClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._paths = ("/ct/cases", "/ct/cases.json")

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

    def _base_params(self, per_page: int, page: int) -> dict[str, Any]:
        return {
            "per_page": per_page,
            "current_page": page,
            "sort_col": "",
            "sort_dir": "",
            "filters[code][value]": "C-",
            "filters[code][type]": "like",
            "filters[title][value]": "Sin título",
            "filters[title][type]": "like",
            "filters[url][value]": "0",
            "filters[url][type]": "is_null",
            "filters[active][value]": "1",
            "filters[active][type]": "equal",
            "associations": "client,matter,court,case_state,child_cases",
        }

    @staticmethod
    def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = payload.get("results")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        rows = payload.get("cases")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        rows = payload.get("data")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        return []

    @staticmethod
    def _extract_total_pages(payload: dict[str, Any], per_page: int) -> int | None:
        pagination = payload.get("pagination", {})
        candidates = []
        if isinstance(pagination, dict):
            candidates.extend(
                [
                    pagination.get("total_pages"),
                    pagination.get("pages"),
                    pagination.get("last_page"),
                ]
            )
            total_entries = pagination.get("total_entries") or pagination.get("total_count")
            if total_entries:
                try:
                    total_entries_int = int(total_entries)
                    pages = (total_entries_int + per_page - 1) // per_page
                    candidates.append(pages)
                except (ValueError, TypeError):
                    pass
        # Algunos endpoints entregan estos campos al tope.
        candidates.extend(
            [
                payload.get("total_pages"),
                payload.get("pages"),
                payload.get("last_page"),
            ]
        )
        top_level_total = payload.get("total_entries") or payload.get("total_count")
        if top_level_total:
            try:
                total_entries_int = int(top_level_total)
                pages = (total_entries_int + per_page - 1) // per_page
                candidates.append(pages)
            except (ValueError, TypeError):
                pass

        for value in candidates:
            try:
                pages = int(value)
            except (ValueError, TypeError):
                continue
            if pages > 0:
                return pages
        return None

    def _request_json(
        self,
        token: str,
        email: str | None,
        per_page: int,
        page: int,
    ) -> dict[str, Any]:
        params = self._base_params(per_page=per_page, page=page)
        auth_header_candidates = self._build_auth_headers(token=token, email=email)
        with httpx.Client(timeout=self.settings.timeout_seconds) as client:
            last_response: httpx.Response | None = None
            for path in self._paths:
                url = f"{self.settings.base_url}{path}"
                for auth_headers in auth_header_candidates:
                    headers = {
                        "Accept": "application/json",
                        "Content-Type": "application/json;charset=UTF-8",
                        "User-Agent": "ct-cases-extractor/1.0",
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
                    if "json" not in (response.headers.get("content-type") or "").lower():
                        continue
                    try:
                        payload = response.json()
                    except ValueError:
                        continue
                    if isinstance(payload, dict):
                        return payload

        status_code = last_response.status_code if last_response else "desconocido"
        body = last_response.text if last_response else ""
        raise RuntimeError(
            "No fue posible consultar causas sin titulo. "
            f"Ultimo status: {status_code}. "
            f"Respuesta: {body[:300]}"
        )

    async def _request_json_async(
        self,
        token: str,
        email: str | None,
        per_page: int,
        page: int,
    ) -> dict[str, Any]:
        params = self._base_params(per_page=per_page, page=page)
        auth_header_candidates = self._build_auth_headers(token=token, email=email)
        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            last_response: httpx.Response | None = None
            for path in self._paths:
                url = f"{self.settings.base_url}{path}"
                for auth_headers in auth_header_candidates:
                    headers = {
                        "Accept": "application/json",
                        "Content-Type": "application/json;charset=UTF-8",
                        "User-Agent": "ct-cases-extractor/1.0",
                        **auth_headers,
                    }
                    response = await client.get(
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
                    if "json" not in (response.headers.get("content-type") or "").lower():
                        continue
                    try:
                        payload = response.json()
                    except ValueError:
                        continue
                    if isinstance(payload, dict):
                        return payload

        status_code = last_response.status_code if last_response else "desconocido"
        body = last_response.text if last_response else ""
        raise RuntimeError(
            "No fue posible consultar causas sin titulo. "
            f"Ultimo status: {status_code}. "
            f"Respuesta: {body[:300]}"
        )

    def iter_pages(
        self, token: str, email: str | None = None, per_page: int = 100
    ) -> Iterator[dict[str, Any]]:
        current_page = 1
        while True:
            payload = self._request_json(
                token=token, email=email, per_page=per_page, page=current_page
            )
            yield payload
            rows = self._extract_rows(payload)
            total_pages = self._extract_total_pages(payload, per_page)
            if len(rows) < per_page:
                break
            if total_pages is not None and current_page >= total_pages:
                break
            current_page += 1

    async def iter_pages_async(
        self, token: str, email: str | None = None, per_page: int = 100
    ) -> AsyncIterator[dict[str, Any]]:
        current_page = 1
        while True:
            payload = await self._request_json_async(
                token=token, email=email, per_page=per_page, page=current_page
            )
            yield payload
            rows = self._extract_rows(payload)
            total_pages = self._extract_total_pages(payload, per_page)
            if len(rows) < per_page:
                break
            if total_pages is not None and current_page >= total_pages:
                break
            current_page += 1
