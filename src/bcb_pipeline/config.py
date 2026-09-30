"""Settings for Banco Central do Brasil SGS data extraction."""

from datetime import date
from pathlib import Path

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_code}/dados"
SERIES = {
    "selic": 432,
    "ipca": 433,
    "usd_brl_sell": 1,
}
QUERY_WINDOW_DAYS = 365
REQUEST_TIMEOUT_SECONDS = 20.0
RETRY_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 0.5
DEFAULT_START_DATE = date(2000, 1, 1)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
