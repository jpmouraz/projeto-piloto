"""Offline tests for loading and the pipeline command."""

from datetime import date
from pathlib import Path

import pandas as pd

from bcb_pipeline import cli
from bcb_pipeline.config import SERIES
from bcb_pipeline.load import load_data


def sample_raw() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"series_code": code, "date": date(2024, 1, 2), "value": 1.0}
            for code in SERIES.values()
        ]
    )


def sample_tables() -> dict[str, pd.DataFrame]:
    return {
        "selic": pd.DataFrame(
            {"date": [date(2024, 1, 2)], "selic_pct_annual": [11.75]}
        ),
        "ipca": pd.DataFrame(
            {
                "date": [date(2024, 1, 2)],
                "ipca_pct_monthly": [0.4],
                "ipca_12m_pct": [4.5],
            }
        ),
        "usd_brl_sell": pd.DataFrame(
            {
                "date": [date(2024, 1, 2)],
                "usd_brl_sell": [4.9],
                "usd_brl_sell_ma_30": [4.8],
            }
        ),
        "monthly": pd.DataFrame(
            {"month": [date(2024, 1, 1)], "selic_pct_annual": [11.75]}
        ),
    }


def test_load_data_writes_raw_csv_and_processed_csv_parquet(tmp_path: Path) -> None:
    paths = load_data(
        sample_raw(),
        sample_tables(),
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )

    assert len(paths) == 9
    assert paths[0].name == "sgs_observations.csv"
    assert pd.read_csv(paths[0]).shape[0] == 3
    for csv_path, parquet_path in zip(paths[1::2], paths[2::2], strict=True):
        assert csv_path.exists()
        assert parquet_path.exists()
        assert len(pd.read_parquet(parquet_path)) == 1


def test_run_pipeline_orchestrates_stages_without_network(
    monkeypatch, tmp_path: Path
) -> None:
    fetched_codes = []
    written = {}

    def fake_fetch(code, start_date, end_date):
        fetched_codes.append(code)
        return pd.DataFrame([{"series_code": code, "date": start_date, "value": 1.0}])

    monkeypatch.setattr(cli, "fetch_series", fake_fetch)
    monkeypatch.setattr(cli, "transform_data", lambda raw: sample_tables())
    monkeypatch.setattr(cli, "validate_data", lambda tables, as_of: ["stale sample"])

    def fake_load(raw, tables, *, raw_dir, processed_dir):
        written["codes"] = raw["series_code"].tolist()
        written["directories"] = (raw_dir, processed_dir)
        return [tmp_path / "monthly.csv"]

    monkeypatch.setattr(cli, "load_data", fake_load)
    output_paths, warnings = cli.run_pipeline(
        date(2024, 1, 1),
        date(2024, 1, 31),
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )

    assert fetched_codes == list(SERIES.values())
    assert written["codes"] == list(SERIES.values())
    assert output_paths == [tmp_path / "monthly.csv"]
    assert warnings == ["stale sample"]


def test_cli_run_reports_generated_files(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda start, end: ([tmp_path / "monthly.csv"], []),
    )

    status = cli.main(["run", "--start-date", "2024-01-01", "--end-date", "2024-01-31"])

    assert status == 0
    assert "Pipeline concluído" in capsys.readouterr().out
