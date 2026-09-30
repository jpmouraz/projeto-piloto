"""Offline tests for SGS extraction."""

import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from bcb_pipeline.config import QUERY_WINDOW_DAYS
from bcb_pipeline.extract import fetch_series

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sgs_response.json"


def fixture_payload() -> list[dict[str, str]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fetch_series_parses_sgs_json_fixture() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["formato"] == "json"
        assert request.url.params["dataInicial"] == "01/01/2024"
        assert request.url.params["dataFinal"] == "05/01/2024"
        return httpx.Response(200, json=fixture_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_series(432, date(2024, 1, 1), date(2024, 1, 5), client=client)

    assert list(result.columns) == ["series_code", "date", "value"]
    assert result["series_code"].tolist() == [432, 432]
    assert result["date"].tolist() == [date(2024, 1, 2), date(2024, 1, 3)]
    assert result["value"].tolist() == [11.75, 11.75]


def test_fetch_series_splits_long_ranges_into_bounded_windows() -> None:
    request_ranges: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_ranges.append(
            (request.url.params["dataInicial"], request.url.params["dataFinal"])
        )
        return httpx.Response(200, json=[])

    end_date = date(2024, 1, 1) + timedelta(days=QUERY_WINDOW_DAYS)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_series(1, date(2024, 1, 1), end_date, client=client)

    assert len(request_ranges) == 2
    assert request_ranges[0] == ("01/01/2024", "30/12/2024")
    assert request_ranges[1] == ("31/12/2024", "31/12/2024")
    assert result.empty


def test_fetch_series_retries_server_error_with_backoff() -> None:
    responses = iter([httpx.Response(503), httpx.Response(200, json=fixture_payload())])
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        return next(responses)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_series(
            433,
            date(2024, 1, 1),
            date(2024, 1, 5),
            client=client,
            sleep=delays.append,
        )

    assert len(result) == 2
    assert delays == [0.5]


def test_fetch_series_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="Unsupported SGS series code"):
        fetch_series(999, date(2024, 1, 1), date(2024, 1, 2))


def test_fetch_series_rejects_reversed_dates() -> None:
    with pytest.raises(ValueError, match="start_date must be on or before end_date"):
        fetch_series(432, date(2024, 1, 2), date(2024, 1, 1))
