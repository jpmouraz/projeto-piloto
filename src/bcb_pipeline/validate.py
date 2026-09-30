"""Quality checks for transformed Banco Central indicators."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pandas as pd

from bcb_pipeline.config import SERIES

VALUE_COLUMNS = {
    "selic": "selic_pct_annual",
    "ipca": "ipca_pct_monthly",
    "usd_brl_sell": "usd_brl_sell",
}
VALUE_RANGES = {
    "selic": (0.0, 100.0),
    "ipca": (-20.0, 30.0),
    "usd_brl_sell": (0.0, 1000.0),
}
STALE_AFTER_DAYS = {"selic": 14, "ipca": 62, "usd_brl_sell": 14}


def validate_data(
    tables: Mapping[str, pd.DataFrame], *, as_of: date | None = None
) -> list[str]:
    """Raise on invalid outputs and return warnings for stale observations."""
    required_tables = {*SERIES, "monthly"}
    missing_tables = required_tables - set(tables)
    if missing_tables:
        raise ValueError(f"Missing transformed tables: {sorted(missing_tables)}")

    warnings = []
    today = pd.Timestamp(as_of or date.today())
    for name, value_column in VALUE_COLUMNS.items():
        frame = tables[name]
        if frame.empty:
            raise ValueError(f"Required dataset '{name}' is empty")
        if "date" not in frame.columns or value_column not in frame.columns:
            raise ValueError(
                f"Dataset '{name}' must include date and {value_column} columns"
            )
        if frame["date"].isna().any() or frame[value_column].isna().any():
            raise ValueError(f"Dataset '{name}' contains null dates or values")
        if frame["date"].duplicated().any():
            raise ValueError(f"Dataset '{name}' contains duplicate dates")
        lower, upper = VALUE_RANGES[name]
        if not frame[value_column].between(lower, upper, inclusive="both").all():
            raise ValueError(
                f"Dataset '{name}' has values outside the plausible range "
                f"[{lower}, {upper}]"
            )
        latest = pd.to_datetime(frame["date"]).max()
        age_days = (today - latest).days
        if age_days > STALE_AFTER_DAYS[name]:
            warnings.append(
                f"Data for '{name}' is stale: latest observation is "
                f"{latest:%Y-%m-%d} ({age_days} days old)."
            )

    monthly = tables["monthly"]
    if monthly.empty:
        raise ValueError("Required dataset 'monthly' is empty")
    if "month" not in monthly.columns:
        raise ValueError("Dataset 'monthly' must include a month column")
    if monthly.isna().any().any():
        raise ValueError("Dataset 'monthly' contains null values")
    if monthly["month"].duplicated().any():
        raise ValueError("Dataset 'monthly' contains duplicate months")
    return warnings
