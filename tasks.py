from __future__ import annotations

import subprocess
import sys
from typing import Iterable

from invoke import task
from invoke.exceptions import Exit


def _run_main(args: Iterable[str]) -> None:
    command = [sys.executable, "main.py", *args]
    printable = " ".join(command)
    print(f"> {printable}")
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise Exit(f"Comando fallido con codigo {completed.returncode}.", code=completed.returncode)


@task(help={"force": "Regenera token aunque exista uno persistido."})
def token(c, force: bool = False) -> None:
    args = ["token"]
    if force:
        args.append("--force")
    _run_main(args)


@task(
    help={
        "page": "Pagina a consultar.",
        "per_page": "Registros por pagina.",
        "all_pages": "Obtiene todas las paginas.",
        "sort_by": "Campo de ordenamiento.",
        "order": "Orden asc o desc.",
        "force_new_token": "Fuerza autenticacion previa.",
        "async_fetch": "Obtiene paginas usando cliente async.",
        "output": "Ruta de salida (.xlsx, .csv o .json).",
    }
)
def credentials(
    c,
    page: int = 1,
    per_page: int = 100,
    all_pages: bool = False,
    sort_by: str = "created_at",
    order: str = "desc",
    force_new_token: bool = False,
    async_fetch: bool = False,
    output: str = "",
) -> None:
    args = [
        "credentials",
        "--page",
        str(page),
        "--per-page",
        str(per_page),
        "--sort-by",
        sort_by,
        "--order",
        order,
    ]
    if all_pages:
        args.append("--all")
    if force_new_token:
        args.append("--force-new-token")
    if async_fetch:
        args.append("--async-fetch")
    if output:
        args.extend(["--output", output])
    _run_main(args)


@task(
    help={
        "per_page": "Registros por pagina.",
        "force_new_token": "Fuerza autenticacion previa.",
        "async_fetch": "Obtiene paginas usando cliente async.",
        "output": "Ruta de salida (.xlsx, .csv o .json).",
    }
)
def untitled_cases(
    c,
    per_page: int = 100,
    force_new_token: bool = False,
    async_fetch: bool = False,
    output: str = "",
) -> None:
    args = ["untitled-cases", "--per-page", str(per_page)]
    if force_new_token:
        args.append("--force-new-token")
    if async_fetch:
        args.append("--async-fetch")
    if output:
        args.extend(["--output", output])
    _run_main(args)


@task(
    help={
        "mode": "Preset de columnas/filtros: filtered o full-ct.",
        "wait_seconds": "Espera maxima para /attachments/:id/download. 0 = solo ID.",
        "poll_seconds": "Intervalo entre reintentos de descarga.",
        "force_new_token": "Fuerza autenticacion previa.",
        "output": "Ruta de salida .xlsx.",
    }
)
def cases_report(
    c,
    mode: str = "filtered",
    wait_seconds: int = 0,
    poll_seconds: int = 10,
    force_new_token: bool = False,
    output: str = "",
) -> None:
    args = [
        "cases-report",
        "--mode",
        mode,
        "--wait-seconds",
        str(wait_seconds),
        "--poll-seconds",
        str(poll_seconds),
    ]
    if force_new_token:
        args.append("--force-new-token")
    if output:
        args.extend(["--output", output])
    _run_main(args)


@task(
    help={
        "attachment_id": "ID de export/attachment.",
        "force_new_token": "Fuerza autenticacion previa.",
        "output": "Ruta de salida .xlsx.",
    }
)
def cases_download(
    c,
    attachment_id: str = "",
    force_new_token: bool = False,
    output: str = "",
) -> None:
    if not attachment_id:
        raise Exit("Debes indicar --attachment-id <ID>.", code=2)

    args = ["cases-download", "--id", attachment_id]
    if force_new_token:
        args.append("--force-new-token")
    if output:
        args.extend(["--output", output])
    _run_main(args)
