"""Transform raw SGS observations into indicator datasets."""

from __future__ import annotations

import math

import pandas as pd

from bcb_pipeline.config import SERIES

RAW_COLUMNS = {"series_code", "date", "value"}


def _prepare_raw(raw: pd.DataFrame) -> pd.DataFrame:
    missing = RAW_COLUMNS - set(raw.columns)
    if missing:
        raise ValueError(f"Raw observations are missing columns: {sorted(missing)}")
    prepared = raw.loc[:, ["series_code", "date", "value"]].copy()
    prepared["series_code"] = pd.to_numeric(
        prepared["series_code"], errors="coerce"
    ).astype("Int64")
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce").dt.normalize()
    prepared["value"] = pd.to_numeric(prepared["value"], errors="coerce").astype(
        "float64"
    )
    unknown = set(prepared["series_code"].dropna().astype(int)) - set(SERIES.values())
    if unknown:
        raise ValueError(f"Unsupported SGS series codes in raw data: {sorted(unknown)}")
    return prepared


def _ipca_12m(ipca: pd.DataFrame) -> pd.Series:
    monthly = ipca.assign(month=ipca["date"].dt.to_period("M"))
    monthly = monthly.drop_duplicates("month", keep="last").set_index("month")
    rates = monthly["value"] / 100 + 1
    result: dict[pd.Period, float] = {}
    for month in rates.index:
        expected_months = pd.period_range(end=month, periods=12, freq="M")
        if all(period in rates.index for period in expected_months):
            result[month] = (math.prod(rates.loc[expected_months]) - 1) * 100
    month_keys = ipca["date"].dt.to_period("M")
    return month_keys.map(result).astype("float64")


def transform_data(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build typed daily indicator tables and a unified monthly table.

    The result keys are ``selic``, ``ipca``, ``usd_brl_sell`` and ``monthly``.
    Rolling indicators omit their initial incomplete windows.
    """
    prepared = _prepare_raw(raw)
    tables: dict[str, pd.DataFrame] = {}

    for name, code in SERIES.items():
        series = prepared.loc[prepared["series_code"] == code, ["date", "value"]]
        series = series.sort_values("date", kind="stable").reset_index(drop=True)
        if name == "ipca":
            series = series.assign(ipca_12m_pct=_ipca_12m(series))
            series = series.dropna(subset=["ipca_12m_pct"])
            series = series.rename(columns={"value": "ipca_pct_monthly"})
        elif name == "usd_brl_sell":
            series = series.assign(
                usd_brl_sell_ma_30=series["value"].rolling(30, min_periods=30).mean()
            )
            series = series.dropna(subset=["usd_brl_sell_ma_30"])
            series = series.rename(columns={"value": "usd_brl_sell"})
        else:
            series = series.rename(columns={"value": "selic_pct_annual"})
        tables[name] = series.reset_index(drop=True)

    monthly_parts = []
    for name, value_column in (
        ("selic", "selic_pct_annual"),
        ("ipca", "ipca_pct_monthly"),
        ("ipca", "ipca_12m_pct"),
        ("usd_brl_sell", "usd_brl_sell"),
    ):
        series = tables[name].loc[:, ["date", value_column]].copy()
        series["month"] = series["date"].dt.to_period("M")
        if name == "usd_brl_sell":
            monthly = series.groupby("month", as_index=False)[value_column].mean()
            monthly = monthly.rename(columns={value_column: "usd_brl_sell_avg"})
        else:
            monthly = series.sort_values("date").groupby("month", as_index=False).last()
            monthly = monthly.loc[:, ["month", value_column]]
        monthly_parts.append(monthly)

    monthly_table = monthly_parts[0]
    for part in monthly_parts[1:]:
        monthly_table = monthly_table.merge(part, on="month", how="inner")
    monthly_table["month"] = monthly_table["month"].dt.to_timestamp()
    monthly_table = monthly_table.sort_values("month").reset_index(drop=True)
    tables["monthly"] = monthly_table
    return tables
