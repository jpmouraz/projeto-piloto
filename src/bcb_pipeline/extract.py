"""Extract time series from the Banco Central do Brasil SGS API."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd

from bcb_pipeline.config import (
    BACKOFF_BASE_SECONDS,
    BASE_URL,
    QUERY_WINDOW_DAYS,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_ATTEMPTS,
    SERIES,
)


def _date_windows(start_date: date, end_date: date) -> list[tuple[date, date]]:
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    windows = []
    window_start = start_date
    while window_start <= end_date:
        window_end = min(window_start + timedelta(days=QUERY_WINDOW_DAYS - 1), end_date)
        windows.append((window_start, window_end))
        window_start = window_end + timedelta(days=1)
    return windows


def _request_json(
    client: httpx.Client,
    series_code: int,
    window_start: date,
    window_end: date,
    sleep: Callable[[float], None],
) -> list[dict[str, Any]]:
    url = BASE_URL.format(series_code=series_code)
    params = {
        "formato": "json",
        "dataInicial": window_start.strftime("%d/%m/%Y"),
        "dataFinal": window_end.strftime("%d/%m/%Y"),
    }
    last_error: httpx.HTTPError | None = None

    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("SGS response must be a JSON list")
            return payload
        except httpx.HTTPError as error:
            last_error = error
            if attempt + 1 == RETRY_ATTEMPTS:
                break
            sleep(BACKOFF_BASE_SECONDS * (2**attempt))
        except ValueError as error:
            raise ValueError(
                f"Invalid JSON response for SGS series {series_code}: {error}"
            ) from error

    raise RuntimeError(
        f"Could not fetch SGS series {series_code} for "
        f"{window_start:%d/%m/%Y} to {window_end:%d/%m/%Y} after "
        f"{RETRY_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def fetch_series(
    series_code: int,
    start_date: date,
    end_date: date,
    *,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> pd.DataFrame:
    """Fetch one configured SGS series in bounded inclusive date windows.

    Returns columns ``series_code``, ``date`` and ``value``. Dates are Python
    dates and values are floating-point numbers.
    """
    if series_code not in SERIES.values():
        supported = ", ".join(str(code) for code in SERIES.values())
        raise ValueError(f"Unsupported SGS series code {series_code}; use {supported}")

    owns_client = client is None
    http_client = client or httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)
    rows: list[dict[str, Any]] = []
    try:
        for window_start, window_end in _date_windows(start_date, end_date):
            payload = _request_json(
                http_client, series_code, window_start, window_end, sleep
            )
            for item in payload:
                if (
                    not isinstance(item, dict)
                    or "data" not in item
                    or "valor" not in item
                ):
                    raise ValueError(
                        f"Malformed row in SGS series {series_code}: expected data and valor"
                    )
                try:
                    observation_date = date.fromisoformat(
                        "-".join(reversed(item["data"].split("/")))
                    )
                    value = float(item["valor"].replace(",", "."))
                except (AttributeError, TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid observation in SGS series {series_code}: {item!r}"
                    ) from error
                rows.append(
                    {
                        "series_code": series_code,
                        "date": observation_date,
                        "value": value,
                    }
                )
    finally:
        if owns_client:
            http_client.close()

    return pd.DataFrame(rows, columns=["series_code", "date", "value"])
