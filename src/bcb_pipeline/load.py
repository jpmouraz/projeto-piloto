"""Write raw and transformed indicator data to disk."""

from pathlib import Path

import pandas as pd

from bcb_pipeline.config import PROCESSED_DATA_DIR, RAW_DATA_DIR


def load_data(
    raw: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    *,
    raw_dir: Path = RAW_DATA_DIR,
    processed_dir: Path = PROCESSED_DATA_DIR,
) -> list[Path]:
    """Save raw CSV plus each processed dataset as CSV and Parquet."""
    if raw.empty:
        raise ValueError("Cannot save raw data: no observations were collected")
    if not tables:
        raise ValueError("Cannot save processed data: no tables were provided")

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "sgs_observations.csv"
    raw.to_csv(raw_path, index=False, encoding="utf-8")
    saved_paths = [raw_path]

    for name, frame in tables.items():
        if frame.empty:
            raise ValueError(f"Cannot save processed dataset '{name}': it is empty")
        csv_path = processed_dir / f"{name}.csv"
        parquet_path = processed_dir / f"{name}.parquet"
        frame.to_csv(csv_path, index=False, encoding="utf-8")
        frame.to_parquet(parquet_path, index=False)
        saved_paths.extend((csv_path, parquet_path))

    return saved_paths
