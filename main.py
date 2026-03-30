from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ct_extractor.auth import AuthClient, TokenStore
from ct_extractor.config import Settings
from ct_extractor.credentials import CredentialsClient


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
        "--output",
        default="",
        help="Ruta de salida (.xlsx recomendado, .json opcional).",
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


def save_json(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path.resolve()


def save_results_excel(results: list[dict[str, Any]], output_path: Path) -> Path:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "Falta dependencia para Excel. Ejecuta: pip install -r requirements.txt"
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.json_normalize(results, sep=".")
    for column in df.columns:
        df[column] = df[column].apply(
            lambda value: ", ".join(str(item) for item in value)
            if isinstance(value, list)
            else value
        )
    df.to_excel(output_path, index=False)
    return output_path.resolve()


def save_output(payload: dict[str, Any], output: str) -> Path:
    if output:
        output_path = Path(output)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path("output") / f"credentials_{stamp}.xlsx"

    if output_path.suffix.lower() == ".json":
        return save_json(payload, output_path)

    results = payload.get("results", [])
    if not isinstance(results, list):
        raise RuntimeError("La respuesta no contiene un arreglo valido en 'results'.")
    return save_results_excel(results, output_path)


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
) -> int:
    session = get_or_create_session(settings, force_new=force_new_token)
    client = CredentialsClient(settings)

    try:
        if all_pages:
            payload = client.get_all(
                token=session.auth_token,
                email=session.email,
                per_page=per_page,
                sort_by=sort_by,
                order=order,
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
    except RuntimeError as err:
        if force_new_token:
            raise
        session = get_or_create_session(settings, force_new=True)
        if all_pages:
            payload = client.get_all(
                token=session.auth_token,
                email=session.email,
                per_page=per_page,
                sort_by=sort_by,
                order=order,
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
        print(f"Token expirado/invalido, se regenero automaticamente ({err}).")

    out_path = save_output(payload, output=output)
    total = len(payload.get("results", []))
    print(f"Credenciales extraidas: {total}")
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
        )

    raise ValueError(f"Comando no soportado: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

