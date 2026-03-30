from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class CredentialsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._credentials_paths = (
            "/ct/credentials",
            "/ct/credentials.json",
            "/api/credentials",
            "/credentials.json",
            "/credentials",
        )

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

    def _request_json(
        self,
        token: str,
        email: str | None,
        page: int,
        per_page: int,
        sort_by: str,
        order: str,
    ) -> dict[str, Any]:
        params = {
            "page": page,
            "per_page": per_page,
            "sort_by": sort_by,
            "order": order,
        }
        auth_header_candidates = self._build_auth_headers(token=token, email=email)

        with httpx.Client(timeout=self.settings.timeout_seconds) as client:
            last_response: httpx.Response | None = None
            for path in self._credentials_paths:
                url = f"{self.settings.base_url}{path}"
                for auth_headers in auth_header_candidates:
                    headers = {
                        "Accept": "application/json",
                        "Content-Type": "application/json;charset=UTF-8",
                        "User-Agent": "ct-credentials-extractor/1.0",
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

                    content_type = (response.headers.get("content-type") or "").lower()
                    if "json" not in content_type:
                        continue

                    try:
                        return response.json()
                    except ValueError:
                        continue

        status_code = last_response.status_code if last_response else "desconocido"
        body = last_response.text if last_response else ""
        raise RuntimeError(
            "No fue posible autenticar/consultar credenciales. "
            f"Ultimo status: {status_code}. "
            f"Respuesta: {body[:300]}"
        )

    def get_page(
        self,
        token: str,
        email: str | None = None,
        page: int = 1,
        per_page: int = 10,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> dict[str, Any]:
        return self._request_json(
            token=token,
            email=email,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            order=order,
        )

    def get_all(
        self,
        token: str,
        email: str | None = None,
        per_page: int = 100,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> dict[str, Any]:
        first_page = self.get_page(
            token=token,
            email=email,
            page=1,
            per_page=per_page,
            sort_by=sort_by,
            order=order,
        )
        results = list(first_page.get("results", []))
        pagination = first_page.get("pagination", {})
        total_pages = int(pagination.get("total_pages", 1) or 1)

        for page in range(2, total_pages + 1):
            payload = self.get_page(
                token=token,
                email=email,
                page=page,
                per_page=per_page,
                sort_by=sort_by,
                order=order,
            )
            results.extend(payload.get("results", []))

        pagination["current_page"] = total_pages
        pagination["page_size"] = per_page
        pagination["total_entries"] = pagination.get("total_entries", len(results))
        pagination["total_pages"] = total_pages
        return {"results": results, "pagination": pagination}
