"""Offline tests for transformation and validation."""

from datetime import date, timedelta

import pandas as pd
import pytest

from bcb_pipeline.config import SERIES
from bcb_pipeline.transform import transform_data
from bcb_pipeline.validate import validate_data


def raw_observations() -> pd.DataFrame:
    rows = []
    for month_offset in range(24):
        year = 2023 + month_offset // 12
        month = month_offset % 12 + 1
        rows.append(
            {
                "series_code": SERIES["ipca"],
                "date": date(year, month, 1),
                "value": 1.0,
            }
        )
    for day_offset in range(61):
        rows.append(
            {
                "series_code": SERIES["usd_brl_sell"],
                "date": date(2023, 12, 3) + timedelta(days=day_offset),
                "value": 4.0 + day_offset / 10,
            }
        )
    rows.extend(
        [
            {"series_code": SERIES["selic"], "date": date(2024, 1, 2), "value": 11.75},
            {"series_code": SERIES["selic"], "date": date(2024, 1, 3), "value": 11.5},
            {"series_code": SERIES["selic"], "date": date(2024, 2, 1), "value": 11.25},
        ]
    )
    return pd.DataFrame(rows)


def test_transform_data_types_derivations_and_monthly_unification() -> None:
    tables = transform_data(raw_observations())

    assert set(tables) == {"selic", "ipca", "usd_brl_sell", "monthly"}
    assert pd.api.types.is_datetime64_any_dtype(tables["ipca"]["date"])
    assert tables["ipca"]["ipca_12m_pct"].iloc[0] == pytest.approx(
        ((1.01**12) - 1) * 100
    )
    assert tables["usd_brl_sell"]["usd_brl_sell_ma_30"].iloc[0] == pytest.approx(
        sum(4 + day / 10 for day in range(30)) / 30
    )
    assert tables["monthly"].columns.tolist() == [
        "month",
        "selic_pct_annual",
        "ipca_pct_monthly",
        "ipca_12m_pct",
        "usd_brl_sell_avg",
    ]
    january = tables["monthly"].iloc[0]
    assert january["selic_pct_annual"] == 11.5
    assert january["ipca_pct_monthly"] == 1.0
    assert january["usd_brl_sell_avg"] == pytest.approx(
        sum(4 + day / 10 for day in range(29, 60)) / 31
    )


def test_transform_data_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        transform_data(pd.DataFrame({"date": [], "value": []}))


def test_validate_data_accepts_valid_data_and_warns_when_stale() -> None:
    tables = transform_data(raw_observations())

    warnings = validate_data(tables, as_of=date(2025, 3, 1))
    assert len(warnings) == 3
    assert all("stale" in warning for warning in warnings)


def test_validate_data_rejects_duplicate_dates() -> None:
    tables = transform_data(raw_observations())
    tables["selic"] = pd.concat(
        [tables["selic"], tables["selic"].iloc[[0]]], ignore_index=True
    )

    with pytest.raises(ValueError, match="duplicate dates"):
        validate_data(tables, as_of=date(2025, 3, 1))


def test_validate_data_rejects_nulls_and_implausible_ranges() -> None:
    tables = transform_data(raw_observations())
    tables["ipca"].loc[tables["ipca"].index[0], "ipca_pct_monthly"] = None
    with pytest.raises(ValueError, match="null dates or values"):
        validate_data(tables, as_of=date(2025, 3, 1))

    tables = transform_data(raw_observations())
    tables["usd_brl_sell"].loc[tables["usd_brl_sell"].index[0], "usd_brl_sell"] = 1001
    with pytest.raises(ValueError, match="plausible range"):
        validate_data(tables, as_of=date(2025, 3, 1))
