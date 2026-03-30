from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook


def flatten_record(record: dict[str, Any], parent_key: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in record.items():
        new_key = f"{parent_key}.{key}" if parent_key else str(key)
        if isinstance(value, dict):
            flat.update(flatten_record(value, new_key))
        elif isinstance(value, list):
            flat[new_key] = ", ".join(str(item) for item in value)
        else:
            flat[new_key] = value
    return flat


class IncrementalTableWriter:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.headers: list[str] | None = None
        self.extra_column = "_extra_json"
        self.rows_written = 0

        suffix = self.output_path.suffix.lower()
        if suffix == ".csv":
            self._mode = "csv"
            self._file = self.output_path.open("w", encoding="utf-8-sig", newline="")
            self._csv_writer: csv.DictWriter | None = None
            self._wb = None
            self._ws = None
        elif suffix == ".xlsx":
            self._mode = "xlsx"
            self._wb = Workbook(write_only=True)
            self._ws = self._wb.create_sheet("credentials")
            self._file = None
            self._csv_writer = None
        else:
            raise RuntimeError("Formato no soportado. Usa .xlsx o .csv")

    def _initialize_headers_if_needed(self, rows: list[dict[str, Any]]) -> None:
        if self.headers is not None:
            return
        if not rows:
            return

        header_set: set[str] = set()
        ordered_headers: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in header_set:
                    header_set.add(key)
                    ordered_headers.append(key)

        ordered_headers.append(self.extra_column)
        self.headers = ordered_headers

        if self._mode == "csv":
            assert self._csv_writer is None
            assert self._file is not None
            self._csv_writer = csv.DictWriter(
                self._file, fieldnames=self.headers, extrasaction="ignore"
            )
            self._csv_writer.writeheader()
        else:
            assert self._ws is not None
            self._ws.append(self.headers)

    def write_records(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        flattened = [flatten_record(record) for record in records]
        self._initialize_headers_if_needed(flattened)
        if not self.headers:
            return

        for row in flattened:
            extra = {k: v for k, v in row.items() if k not in self.headers}
            normalized_row = {header: row.get(header, "") for header in self.headers}
            normalized_row[self.extra_column] = (
                json.dumps(extra, ensure_ascii=False) if extra else ""
            )

            if self._mode == "csv":
                assert self._csv_writer is not None
                self._csv_writer.writerow(normalized_row)
            else:
                assert self._ws is not None
                self._ws.append([normalized_row[h] for h in self.headers])
            self.rows_written += 1

    def close(self) -> None:
        if self._mode == "csv":
            assert self._file is not None
            self._file.close()
        else:
            assert self._wb is not None
            self._wb.save(self.output_path)

