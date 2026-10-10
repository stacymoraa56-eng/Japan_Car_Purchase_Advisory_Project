"""
scrapers/japan/sbt_scraper.py
──────────────────────────────
Scrapes car listings from SBT Japan (www.sbtjapan.com).
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from config.settings import MAX_PAGES, MIN_YEAR
from utils.driver_factory import build_driver
from utils.scraping_helpers import (
    safe_get, polite_sleep, wait_for_element,
    safe_find_text, extract_price, extract_year, 
    extract_mileage, clean_engine_cc
)
from utils.logger import get_logger
from database.db_manager import DBManager

log = get_logger(__name__)
SITE_NAME = "sbtjapan"
BASE_URL = "https://www.sbtjapan.com"


def get_listing_urls(driver) -> List[str]:
    urls = []
    try:
        cards = driver.find_elements(
            By.CSS_SELECTOR,
            "div.car-list-box a.car-img, div.carlist a.mainLink, .car-item a"
        )
        for card in cards:
            href = card.get_attribute("href")
            if href and "/used-cars/" in href:
                urls.append(href)
    except NoSuchElementException:
        pass

    seen, unique = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    log.info(f"[{SITE_NAME}] Found {len(unique)} unique listing URLs.")
    return unique


def get_next_page_url(driver) -> Optional[str]:
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "a.next, li.next a, a[aria-label='Next']")
        return btn.get_attribute("href")
    except NoSuchElementException:
        return None


def _build_spec_dict(driver) -> Dict[str, str]:
    specs = {}
    rows = driver.find_elements(By.CSS_SELECTOR, "table.car-spec tr, table.spec-table tr")
    for row in rows:
        th = row.find_elements(By.TAG_NAME, "th")
        td = row.find_elements(By.TAG_NAME, "td")
        if th and td:
            key = th[0].text.strip().lower().replace(" ", "_")
            specs[key] = td[0].text.strip()

    if not specs:
        dts = driver.find_elements(By.CSS_SELECTOR, "dl.car-detail-spec dt")
        dds = driver.find_elements(By.CSS_SELECTOR, "dl.car-detail-spec dd")
        for dt, dd in zip(dts, dds):
            key = dt.text.strip().lower().replace(" ", "_")
            specs[key] = dd.text.strip()

    return specs


def parse_detail_page(driver, url: str) -> Optional[Dict[str, Any]]:
    try:
        safe_get(driver, url)

        if not wait_for_element(driver, "h1, .car-title, .car-name", timeout=15):
            log.warning(f"Page failed to load: {url}")
            return None

        specs = _build_spec_dict(driver)

        year_raw = specs.get("year", specs.get("model_year", ""))
        year = extract_year(year_raw)
        if year and year < MIN_YEAR:
            return None

        price_raw = safe_find_text(driver, ".price, .car-price, span.priceUSD")
        price_usd = extract_price(price_raw)

        mileage = extract_mileage(specs.get("mileage", specs.get("odometer", "")))
        engine_cc = clean_engine_cc(specs.get("engine", specs.get("engine_cc", "")))

        doors = int(specs.get("doors", 0)) if str(specs.get("doors", "")).isdigit() else None
        seats = int(specs.get("seats", 0)) if str(specs.get("seats", "")).isdigit() else None

        return {
            "listing_url": url,
            "make": specs.get("make", specs.get("brand", "")).title(),
            "model": specs.get("model", "").title(),
            "year": year,
            "mileage_km": mileage,
            "engine_cc": engine_cc,
            "fuel_type": specs.get("fuel", specs.get("fuel_type", "")).title(),
            "transmission": specs.get("transmission", specs.get("gear_type", "")).title(),
            "body_type": specs.get("body", specs.get("body_type", "")).title(),
            "color": specs.get("color", specs.get("exterior_color", "")).title(),
            "price_usd": price_usd,
            "price_jpy": None,
            "steering": specs.get("steering", "RHD"),
            "drive_type": specs.get("drive", specs.get("drive_type", "")),
            "doors": doors,
            "seats": seats,
            "condition": "Used",
            "location": "Japan",
            "description": safe_find_text(driver, ".car-description, .description"),
        }

    except Exception as e:
        log.error(f"Error parsing SBT detail page {url}: {e}")
        return None


def scrape_sbt(max_pages: int = MAX_PAGES) -> None:
    db = DBManager()
    driver = build_driver()
    started_at = datetime.utcnow()

    search_url = f"{BASE_URL}/used-cars/?minyear={MIN_YEAR}&sort=price_asc"

    total_scraped = total_saved = total_errors = 0
    batch: List[Dict[str, Any]] = []
    BATCH_SIZE = 20

    try:
        current_url = search_url
        for page_num in range(1, max_pages + 1):
            log.info(f"[{SITE_NAME}] Page {page_num} → {current_url}")
            safe_get(driver, current_url)

            if not wait_for_element(driver, "div.car-list-box, .car-item, .carlist"):
                log.warning("No listings found.")
                break

            detail_urls = get_listing_urls(driver)
            if not detail_urls:
                break

            for url in detail_urls:
                record = parse_detail_page(driver, url)
                if record:
                    batch.append(record)
                    total_scraped += 1
                else:
                    total_errors += 1

                if len(batch) >= BATCH_SIZE:
                    res = db.save_listings(batch, market="japan", source=SITE_NAME)
                    total_saved += res.get("inserted", 0)
                    batch.clear()

            next_url = get_next_page_url(driver)
            if not next_url:
                log.info(f"[{SITE_NAME}] Last page reached.")
                break
            current_url = next_url
            polite_sleep()

        if batch:
            res = db.save_listings(batch, market="japan", source=SITE_NAME)
            total_saved += res.get("inserted", 0)

    finally:
        driver.quit()
        db.log_run(
            site=SITE_NAME, market="japan",
            rows_scraped=total_scraped, rows_saved=total_saved,
            errors=total_errors, started_at=started_at
        )
        log.info(f"[{SITE_NAME}] Finished. Scraped: {total_scraped}, Saved: {total_saved}, Errors: {total_errors}")


if __name__ == "__main__":
    scrape_sbt()