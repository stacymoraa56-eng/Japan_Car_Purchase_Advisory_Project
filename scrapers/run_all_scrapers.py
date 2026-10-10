"""
scrapers/run_all_scrapers.py
────────────────────────────
Master Scraper Orchestrator. Runs all Japanese and Kenyan scrapers sequentially, then triggers ELT SQL cleaning.
"""

from scrapers.japan.beforward_scraper import scrape_beforward
from scrapers.japan.sbt_scraper import scrape_sbt
from scrapers.kenya.jiji_scraper import scrape_jiji
from scrapers.kenya.cheki_scraper import ChekiScraper 
from database.db_connector import DBConnector
from utils.logger import get_logger

log = get_logger(__name__)

def run_pipeline():
    log.info("Starting Master Ingestion & Cleaning Pipeline...")

    # Initialize Schema if missing
    connector = DBConnector()
    connector.initialize_schema()

    # Run Japanese Scrapers
    log.info("=== Phase 1: Japanese Export Market Ingestion ===")
    try:
        scrape_beforward(max_pages=10)
    except Exception as e:
        log.error(f"BE FORWARD scraper failed: {e}")

    try:
        scrape_sbt(max_pages=10)
    except Exception as e:
        log.error(f"SBT Japan scraper failed: {e}")

    # Run Kenyan Domestic Scrapers
    log.info("=== Phase 2: Kenyan Domestic Market Ingestion ===")
    try:
        scrape_jiji(max_pages=10)
    except Exception as e:
        log.error(f"Jiji Kenya scraper failed: {e}")

    try:
        ChekiScraper(max_pages=10)
    except Exception as e:
        log.error(f"Cheki Kenya scraper failed: {e}")

    # Trigger Database Transformation & ELT Cleaning
    log.info("=== Phase 3: Executing SQL Cleaning Pipeline ===")
    connector.run_cleaning_pipeline()

    log.info("All scrapers and cleaning tasks completed successfully.")

if __name__ == "__main__":
    run_pipeline()