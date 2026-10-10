"""
config/settings.py
──────────────────
Central application configuration using Environment Variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Database Config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "japan_car_advisory"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS", "postgres")
}
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

# Scraper Settings
MAX_PAGES = int(os.getenv("MAX_PAGES", "30"))
MIN_YEAR = int(os.getenv("MIN_YEAR", "2018"))  # 8-year age rule compliance for Kenya
HEADLESS_DRIVER = os.getenv("HEADLESS_DRIVER", "True").lower() in ("true", "1", "yes")

# Foreign Exchange Defaults (KES)
DEFAULT_USD_TO_KES = float(os.getenv("USD_TO_KES", "130.0"))
DEFAULT_JPY_TO_KES = float(os.getenv("JPY_TO_KES", "0.85"))