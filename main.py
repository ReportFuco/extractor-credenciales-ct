from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ct_extractor.auth import AuthClient, AuthSession, TokenStore
from ct_extractor.cases import UntitledCasesClient
from ct_extractor.config import Settings
from ct_extractor.credentials import CredentialsClient
from ct_extractor.exporters import IncrementalTableWriter


def load_dotenv(dotenv_path: str = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extractor modular de credenciales para TheCaseTracking."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    token_parser = subparsers.add_parser("token", help="Genera y guarda auth_token.")
    token_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenera token aunque exista uno persistido.",
    )

    cred_parser = subparsers.add_parser(
        "credentials", help="Obtiene credenciales (una pagina o todas)."
    )
    cred_parser.add_argument("--page", type=int, default=1, help="Pagina a consultar.")
    cred_parser.add_argument(
        "--per-page", type=int, default=100, help="Registros por pagina."
    )
    cred_parser.add_argument("--all", action="store_true", help="Obtiene todas las paginas.")
    cred_parser.add_argument(
        "--sort-by", default="created_at", help="Campo de ordenamiento."
    )
    cred_parser.add_argument("--order", default="desc", help="Orden: asc o desc.")
    cred_parser.add_argument(
        "--force-new-token",
        action="store_true",
        help="Fuerza autenticacion antes de consultar credenciales.",
    )
    cred_parser.add_argument(
        "--async-fetch",
        action="store_true",
        help="Obtiene paginas usando cliente async.",
    )
    cred_parser.add_argument(
        "--output",
        default="",
        help="Ruta de salida (.xlsx o .csv recomendado, .json opcional).",
    )

    cases_parser = subparsers.add_parser(
        "untitled-cases", help="Reporte de causas sin titulo."
    )
    cases_parser.add_argument(
        "--per-page", type=int, default=100, help="Registros por pagina."
    )
    cases_parser.add_argument(
        "--force-new-token",
        action="store_true",
        help="Fuerza autenticacion antes de consultar.",
    )
    cases_parser.add_argument(
        "--async-fetch",
        action="store_true",
        help="Obtiene paginas usando cliente async.",
    )
    cases_parser.add_argument(
        "--output",
        default="",
        help="Ruta de salida (.xlsx o .csv recomendado, .json opcional).",
    )

    return parser.parse_args()


def get_or_create_session(settings: Settings, force_new: bool = False):
    store = TokenStore(settings.token_file)
    if not force_new:
        cached = store.load()
        if cached and cached.auth_token:
            return cached

    auth_client = AuthClient(settings)
    session = auth_client.sign_in()
    store.save(session)
    return session


def resolve_output_path(output: str, prefix: str) -> Path:
    if output:
        return Path(output)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("output") / f"{prefix}_{stamp}.xlsx"


def save_json(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path.resolve()


def stream_pages_sync(
    client: CredentialsClient,
    session: AuthSession,
    writer: IncrementalTableWriter,
    per_page: int,
    sort_by: str,
    order: str,
    all_pages: bool,
    page: int,
) -> int:
    total = 0
    if all_pages:
        page_iter = client.iter_pages(
            token=session.auth_token,
            email=session.email,
            per_page=per_page,
            sort_by=sort_by,
            order=order,
        )
        for payload in page_iter:
            rows = payload.get("results", [])
            if isinstance(rows, list):
                writer.write_records(rows)
                total += len(rows)
    else:
        payload = client.get_page(
            token=session.auth_token,
            email=session.email,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            order=order,
        )
        rows = payload.get("results", [])
        if isinstance(rows, list):
            writer.write_records(rows)
            total += len(rows)
    return total


async def stream_pages_async(
    client: CredentialsClient,
    session: AuthSession,
    writer: IncrementalTableWriter,
    per_page: int,
    sort_by: str,
    order: str,
    all_pages: bool,
    page: int,
) -> int:
    total = 0
    if all_pages:
        async for payload in client.iter_pages_async(
            token=session.auth_token,
            email=session.email,
            per_page=per_page,
            sort_by=sort_by,
            order=order,
        ):
            rows = payload.get("results", [])
            if isinstance(rows, list):
                writer.write_records(rows)
                total += len(rows)
    else:
        payload = await client.get_page_async(
            token=session.auth_token,
            email=session.email,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            order=order,
        )
        rows = payload.get("results", [])
        if isinstance(rows, list):
            writer.write_records(rows)
            total += len(rows)
    return total


def export_tabular_incremental(
    client: CredentialsClient,
    session: AuthSession,
    output_path: Path,
    per_page: int,
    sort_by: str,
    order: str,
    all_pages: bool,
    page: int,
    async_fetch: bool,
    sheet_name: str = "data",
) -> tuple[Path, int]:
    writer = IncrementalTableWriter(output_path, sheet_name=sheet_name)
    try:
        if async_fetch:
            total = asyncio.run(
                stream_pages_async(
                    client=client,
                    session=session,
                    writer=writer,
                    per_page=per_page,
                    sort_by=sort_by,
                    order=order,
                    all_pages=all_pages,
                    page=page,
                )
            )
        else:
            total = stream_pages_sync(
                client=client,
                session=session,
                writer=writer,
                per_page=per_page,
                sort_by=sort_by,
                order=order,
                all_pages=all_pages,
                page=page,
            )
    finally:
        writer.close()
    return output_path.resolve(), total


def export_json(
    client: CredentialsClient,
    session: AuthSession,
    output_path: Path,
    per_page: int,
    sort_by: str,
    order: str,
    all_pages: bool,
    page: int,
    async_fetch: bool,
) -> tuple[Path, int]:
    if all_pages:
        if async_fetch:
            payload = asyncio.run(
                _get_all_async(
                    client=client,
                    session=session,
                    per_page=per_page,
                    sort_by=sort_by,
                    order=order,
                )
            )
        else:
            payload = client.get_all(
                token=session.auth_token,
                email=session.email,
                per_page=per_page,
                sort_by=sort_by,
                order=order,
            )
    else:
        if async_fetch:
            payload = asyncio.run(
                client.get_page_async(
                    token=session.auth_token,
                    email=session.email,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    order=order,
                )
            )
        else:
            payload = client.get_page(
                token=session.auth_token,
                email=session.email,
                page=page,
                per_page=per_page,
                sort_by=sort_by,
                order=order,
            )

    out_path = save_json(payload, output_path)
    total = len(payload.get("results", []))
    return out_path, total


async def _get_all_async(
    client: CredentialsClient,
    session: AuthSession,
    per_page: int,
    sort_by: str,
    order: str,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    pagination: dict[str, Any] = {}
    async for payload in client.iter_pages_async(
        token=session.auth_token,
        email=session.email,
        per_page=per_page,
        sort_by=sort_by,
        order=order,
    ):
        rows = payload.get("results", [])
        if isinstance(rows, list):
            results.extend(rows)
        pagination = payload.get("pagination", pagination)
    return {"results": results, "pagination": pagination}


def handle_token(settings: Settings, force: bool) -> int:
    session = get_or_create_session(settings, force_new=force)
    token_preview = (
        f"{session.auth_token[:6]}...{session.auth_token[-4:]}"
        if len(session.auth_token) > 10
        else session.auth_token
    )
    print("Token disponible y persistido.")
    print(f"email: {session.email}")
    print(f"id: {session.user_id}")
    print(f"token: {token_preview}")
    print(f"token_file: {settings.token_file.resolve()}")
    return 0


def handle_credentials(
    settings: Settings,
    page: int,
    per_page: int,
    all_pages: bool,
    sort_by: str,
    order: str,
    force_new_token: bool,
    output: str,
    async_fetch: bool,
) -> int:
    output_path = resolve_output_path(output, prefix="credentials")
    session = get_or_create_session(settings, force_new=force_new_token)
    client = CredentialsClient(settings)

    def run_export(current_session: AuthSession) -> tuple[Path, int]:
        if output_path.suffix.lower() == ".json":
            return export_json(
                client=client,
                session=current_session,
                output_path=output_path,
                per_page=per_page,
                sort_by=sort_by,
                order=order,
                all_pages=all_pages,
                page=page,
                async_fetch=async_fetch,
            )
        return export_tabular_incremental(
            client=client,
            session=current_session,
            output_path=output_path,
            per_page=per_page,
            sort_by=sort_by,
            order=order,
            all_pages=all_pages,
            page=page,
            async_fetch=async_fetch,
            sheet_name="credentials",
        )

    try:
        out_path, total = run_export(session)
    except RuntimeError as err:
        if force_new_token:
            raise
        session = get_or_create_session(settings, force_new=True)
        out_path, total = run_export(session)
        print(f"Token expirado/invalido, se regenero automaticamente ({err}).")

    print(f"Credenciales extraidas: {total}")
    print(f"Archivo generado: {out_path}")
    return 0


def _extract_case_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "cases", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _export_untitled_cases_sync(
    client: UntitledCasesClient,
    session: AuthSession,
    per_page: int,
    output_path: Path,
) -> tuple[Path, int]:
    if output_path.suffix.lower() == ".json":
        all_rows: list[dict[str, Any]] = []
        pages: list[dict[str, Any]] = []
        for payload in client.iter_pages(
            token=session.auth_token, email=session.email, per_page=per_page
        ):
            pages.append(payload)
            all_rows.extend(_extract_case_rows(payload))
        return save_json({"results": all_rows, "pages": pages}, output_path), len(all_rows)

    writer = IncrementalTableWriter(output_path, sheet_name="causas_sin_titulo")
    total = 0
    try:
        for payload in client.iter_pages(
            token=session.auth_token, email=session.email, per_page=per_page
        ):
            rows = _extract_case_rows(payload)
            writer.write_records(rows)
            total += len(rows)
    finally:
        writer.close()
    return output_path.resolve(), total


async def _export_untitled_cases_async(
    client: UntitledCasesClient,
    session: AuthSession,
    per_page: int,
    output_path: Path,
) -> tuple[Path, int]:
    if output_path.suffix.lower() == ".json":
        all_rows: list[dict[str, Any]] = []
        pages: list[dict[str, Any]] = []
        async for payload in client.iter_pages_async(
            token=session.auth_token, email=session.email, per_page=per_page
        ):
            pages.append(payload)
            all_rows.extend(_extract_case_rows(payload))
        return save_json({"results": all_rows, "pages": pages}, output_path), len(all_rows)

    writer = IncrementalTableWriter(output_path, sheet_name="causas_sin_titulo")
    total = 0
    try:
        async for payload in client.iter_pages_async(
            token=session.auth_token, email=session.email, per_page=per_page
        ):
            rows = _extract_case_rows(payload)
            writer.write_records(rows)
            total += len(rows)
    finally:
        writer.close()
    return output_path.resolve(), total


def handle_untitled_cases(
    settings: Settings,
    per_page: int,
    force_new_token: bool,
    output: str,
    async_fetch: bool,
) -> int:
    output_path = resolve_output_path(output, prefix="causas_sin_titulo")
    session = get_or_create_session(settings, force_new=force_new_token)
    client = UntitledCasesClient(settings)

    def run_export(current_session: AuthSession) -> tuple[Path, int]:
        if async_fetch:
            return asyncio.run(
                _export_untitled_cases_async(
                    client=client,
                    session=current_session,
                    per_page=per_page,
                    output_path=output_path,
                )
            )
        return _export_untitled_cases_sync(
            client=client,
            session=current_session,
            per_page=per_page,
            output_path=output_path,
        )

    try:
        out_path, total = run_export(session)
    except RuntimeError as err:
        if force_new_token:
            raise
        session = get_or_create_session(settings, force_new=True)
        out_path, total = run_export(session)
        print(f"Token expirado/invalido, se regenero automaticamente ({err}).")

    print(f"Causas sin titulo extraidas: {total}")
    print(f"Archivo generado: {out_path}")
    return 0


def main() -> int:
    load_dotenv()
    args = parse_args()
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(f"Error de configuracion: {exc}")
        return 1

    if args.command == "token":
        return handle_token(settings, force=args.force)

    if args.command == "credentials":
        if args.page <= 0 or args.per_page <= 0:
            print("Error: --page y --per-page deben ser mayores a 0.")
            return 1
        return handle_credentials(
            settings=settings,
            page=args.page,
            per_page=args.per_page,
            all_pages=args.all,
            sort_by=args.sort_by,
            order=args.order,
            force_new_token=args.force_new_token,
            output=args.output,
            async_fetch=args.async_fetch,
        )

    if args.command == "untitled-cases":
        if args.per_page <= 0:
            print("Error: --per-page debe ser mayor a 0.")
            return 1
        return handle_untitled_cases(
            settings=settings,
            per_page=args.per_page,
            force_new_token=args.force_new_token,
            output=args.output,
            async_fetch=args.async_fetch,
        )

    raise ValueError(f"Comando no soportado: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
