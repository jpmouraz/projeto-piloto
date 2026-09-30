"""Command-line entry point for the Banco Central indicators pipeline."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pandas as pd

from bcb_pipeline.config import (
    DEFAULT_START_DATE,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    SERIES,
)
from bcb_pipeline.extract import fetch_series
from bcb_pipeline.load import load_data
from bcb_pipeline.transform import transform_data
from bcb_pipeline.validate import validate_data


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'; use YYYY-MM-DD"
        ) from error


def run_pipeline(
    start_date: date = DEFAULT_START_DATE,
    end_date: date | None = None,
    *,
    raw_dir: Path = RAW_DATA_DIR,
    processed_dir: Path = PROCESSED_DATA_DIR,
) -> tuple[list[Path], list[str]]:
    """Run extraction, transformation, validation and loading."""
    final_date = end_date or date.today()
    if start_date > final_date:
        raise ValueError("Start date must be on or before end date")

    extracted = [
        fetch_series(series_code, start_date, final_date)
        for series_code in SERIES.values()
    ]
    raw = pd.concat(extracted, ignore_index=True)
    tables = transform_data(raw)
    warnings = validate_data(tables, as_of=final_date)
    saved_paths = load_data(raw, tables, raw_dir=raw_dir, processed_dir=processed_dir)
    return saved_paths, warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Baixa e processa indicadores do Banco Central do Brasil."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="Executa o pipeline completo")
    run_parser.add_argument(
        "--start-date",
        type=_parse_date,
        default=DEFAULT_START_DATE,
        help="Data inicial inclusiva (YYYY-MM-DD; padrão: 2000-01-01)",
    )
    run_parser.add_argument(
        "--end-date",
        type=_parse_date,
        default=date.today(),
        help="Data final inclusiva (YYYY-MM-DD; padrão: hoje)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        saved_paths, warnings = run_pipeline(args.start_date, args.end_date)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"Aviso: {warning}")
    print(f"Pipeline concluído. Arquivos gerados: {len(saved_paths)}")
    for path in saved_paths:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
