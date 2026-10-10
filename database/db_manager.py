"""
database/db_manager.py
──────────────────────
Handles DB insertions and pipeline tracking.
"""

from datetime import datetime
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import execute_values
from config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
from utils.logger import get_logger

log = get_logger(__name__)

class DBManager:
    def __init__(self):
        self.conn_params = {
            "host": DB_HOST,
            "port": DB_PORT,
            "dbname": DB_NAME,
            "user": DB_USER,
            "password": DB_PASS,
        }

    def get_connection(self):
        return psycopg2.connect(**self.conn_params)

    def save_listings(self, records: List[Dict[str, Any]], market: str, source: str) -> Dict[str, int]:
        if not records:
            return {"inserted": 0}

        table = "raw_japan_listings" if market == "japan" else "raw_kenya_listings"
        
        if market == "japan":
            query = f"""
            INSERT INTO {table} (
                listing_url, source_site, make, model, year, mileage_km, engine_cc,
                fuel_type, transmission, body_type, color, price_usd, price_jpy,
                steering, drive_type, doors, seats, condition, location, description
            ) VALUES %s
            ON CONFLICT (listing_url) DO UPDATE SET
                price_usd = EXCLUDED.price_usd,
                mileage_km = EXCLUDED.mileage_km,
                scraped_at = CURRENT_TIMESTAMP;
            """
            template = """(
                %(listing_url)s, '{source}', %(make)s, %(model)s, %(year)s, %(mileage_km)s, %(engine_cc)s,
                %(fuel_type)s, %(transmission)s, %(body_type)s, %(color)s, %(price_usd)s, %(price_jpy)s,
                %(steering)s, %(drive_type)s, %(doors)s, %(seats)s, %(condition)s, %(location)s, %(description)s
            )""".format(source=source)
        else:
            query = f"""
            INSERT INTO {table} (
                listing_url, source_site, make, model, year, mileage_km, engine_cc,
                fuel_type, transmission, body_type, color, price_kes, condition, location, description
            ) VALUES %s
            ON CONFLICT (listing_url) DO UPDATE SET
                price_kes = EXCLUDED.price_kes,
                mileage_km = EXCLUDED.mileage_km,
                scraped_at = CURRENT_TIMESTAMP;
            """
            template = """(
                %(listing_url)s, '{source}', %(make)s, %(model)s, %(year)s, %(mileage_km)s, %(engine_cc)s,
                %(fuel_type)s, %(transmission)s, %(body_type)s, %(color)s, %(price_kes)s, %(condition)s,
                %(location)s, %(description)s
            )""".format(source=source)

        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                execute_values(cur, query, records, template=template)
            conn.commit()
            log.info(f"Successfully saved {len(records)} records into {table}.")
            return {"inserted": len(records)}
        except Exception as e:
            conn.rollback()
            log.error(f"Error saving records to {table}: {e}")
            return {"inserted": 0}
        finally:
            conn.close()

    def log_run(self, site: str, market: str, rows_scraped: int, rows_saved: int, errors: int, started_at: datetime, notes: str = ""):
        query = """
        INSERT INTO scraper_logs (site_name, market, rows_scraped, rows_saved, errors_count, started_at, finished_at, notes)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s);
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (site, market, rows_scraped, rows_saved, errors, started_at, notes))
            conn.commit()
        except Exception as e:
            conn.rollback()
            log.error(f"Failed to write execution log: {e}")
        finally:
            conn.close()