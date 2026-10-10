
"""
scrapers/japan/beforward_scraper.py
───────────────────────────────────
Scrapes vehicle export listings from BE FORWARD Japan.

Current BE FORWARD vehicle URLs look like:
https://www.beforward.jp/bmw/mini/ce798690/id/16684031/
"""

import json
import re 
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from config.settings import MAX_PAGES, MIN_YEAR
from utils.driver_factory import build_driver
from utils.scraping_helpers import (
    safe_get,
    polite_sleep,
    wait_for_element,
    safe_find_text,
    extract_price,
    extract_year,
    extract_mileage,
    clean_engine_cc,
)
from utils.logger import get_logger
from database.db_manager import DBManager


log = get_logger(__name__)

SITE_NAME = "beforward"
BASE_URL = "https://www.beforward.jp"


# ============================================================
# BE FORWARD VEHICLE TYPE MAPPING
# ============================================================

VEHICLE_TYPE_MAP = {
    "1": "Coupe",
    "2": "Convertible",
    "3": "Hatchback",
    "4": "Sedan",
    "5": "Wagon",
    "6": "SUV",
    "7": "Pick up",
    "8": "Van",
    "9": "Truck",
    "10": "Mini Bus",
    "15": "Mini Van",
    "16": "Machinery",
    "17": "Bus",
    "26": "Motorcycle",
    "27": "Tractor",
    "28": "Forklift",
}


# ============================================================
# LISTING PAGE
# ============================================================

def get_listing_urls(driver) -> List[str]:
    """
    Extract current BE FORWARD vehicle detail URLs.

    Current URLs look like:

        /bmw/mini/ce798690/id/16684031/
        /toyota/crown-hybrid/ce130870/id/16012297/
    """

    urls = []

    try:
        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href*='/id/']"
        )

        for link in links:

            try:
                href = link.get_attribute("href")

                if not href:
                    continue

                if "beforward.jp/" not in href:
                    continue

                if "/id/" not in href:
                    continue

                href = href.split("?", 1)[0]
                href = href.split("#", 1)[0]

                if href not in urls:
                    urls.append(href)

            except Exception:
                continue

    except Exception as e:

        log.warning(
            f"[{SITE_NAME}] Could not locate vehicle links: {e}"
        )

    log.info(
        f"[{SITE_NAME}] Found {len(urls)} unique vehicle URLs."
    )

    return urls


def get_next_page_url(driver) -> Optional[str]:
    """
    Find BE FORWARD's current 'Next Page' pagination link.

    Current BE FORWARD pagination uses anchors such as:
    https://www.beforward.jp/stocklist/page=2/sar=steering/steering=Right/tp_country_id=27

    The link text is 'Next Page'.
    """

    try:
        links = driver.find_elements(By.CSS_SELECTOR, "a[href]")

        for link in links:
            try:
                text = link.text.strip().lower()
                href = link.get_attribute("href") or ""

                if text == "next page" and "/stocklist/page=" in href:
                    href = href.split("#", 1)[0]
                    return href

            except Exception:
                continue

    except Exception as e:
        log.warning(
            f"[{SITE_NAME}] Could not inspect pagination links: {e}"
        )

    return None


# ============================================================
# SPECIFICATION HELPERS
# ============================================================

def _clean_spec_key(key: str) -> str:
    """
    Convert BE FORWARD specification labels into
    dictionary-friendly keys.

    Example:

        Engine Size             -> engine_size
        Ext. Color              -> ext_color
        Registration Year/month -> registration_year_month
    """

    key = key.strip().lower()

    key = key.replace(".", "")
    key = key.replace("/", "_")
    key = key.replace(" ", "_")

    return key


def _build_spec_dict(driver) -> Dict[str, str]:
    """
    Extract specifications from BE FORWARD's specification table.

    Most rows contain:

        label | value | label | value
    """

    specs: Dict[str, str] = {}

    try:

        rows = driver.find_elements(
            By.CSS_SELECTOR,
            "table.specification tr"
        )

        for row in rows:

            cells = row.find_elements(
                By.CSS_SELECTOR,
                "th, td"
            )

            if len(cells) >= 4:

                for i in range(
                    0,
                    len(cells) - 1,
                    2
                ):

                    key = cells[i].text.strip()
                    value = cells[i + 1].text.strip()

                    if not key:
                        continue

                    key = _clean_spec_key(key)

                    specs[key] = value

            elif len(cells) == 2:

                key = cells[0].text.strip()
                value = cells[1].text.strip()

                if not key:
                    continue

                key = _clean_spec_key(key)

                specs[key] = value

    except Exception as e:

        log.warning(
            f"[{SITE_NAME}] Could not extract specifications: {e}"
        )

    return specs


# ============================================================
# MAKE / MODEL
# ============================================================

def _extract_make_model_from_url(
    url: str
) -> tuple[str, str]:

    make = ""
    model = ""

    try:

        parsed = urlparse(url)

        path_parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        if (
            len(path_parts) >= 5
            and path_parts[-2] == "id"
        ):

            make = (
                path_parts[0]
                .replace("-", " ")
                .title()
            )

            model = (
                path_parts[1]
                .replace("-", " ")
                .title()
            )

    except Exception as e:

        log.warning(
            f"[{SITE_NAME}] Could not extract make/model "
            f"from URL {url}: {e}"
        )

    return make, model


# ============================================================
# JSON-LD EXTRACTION
# ============================================================

def _extract_json_ld(driver) -> Dict[str, Any]:
    """
    Extract useful information from JSON-LD structured data.

    BE FORWARD exposes Product/Car structured data containing
    information such as:

        brand
        name
        description
        offers.price
        offers.priceCurrency
    """

    result: Dict[str, Any] = {}

    try:

        scripts = driver.find_elements(
            By.CSS_SELECTOR,
            "script[type='application/ld+json']"
        )

        for script in scripts:

            try:

                raw = script.get_attribute("innerHTML")

                if not raw:
                    continue

                data = json.loads(raw)

                # Sometimes JSON-LD is a list.
                if isinstance(data, list):

                    candidates = data

                else:

                    candidates = [data]

                for item in candidates:

                    if not isinstance(item, dict):
                        continue

                    item_type = item.get("@type", "")

                    if isinstance(item_type, list):

                        is_vehicle_data = (
                            "Product" in item_type
                            or "Car" in item_type
                        )

                    else:

                        is_vehicle_data = (
                            item_type in (
                                "Product",
                                "Car"
                            )
                        )

                    if not is_vehicle_data:
                        continue

                    result.update(item)

                    return result

            except Exception:
                continue

    except Exception as e:

        log.warning(
            f"[{SITE_NAME}] JSON-LD extraction failed: {e}"
        )

    return result


def _extract_json_ld_price(
    json_ld: Dict[str, Any]
) -> Optional[float]:

    try:

        offers = json_ld.get("offers")

        if not offers:
            return None

        if isinstance(offers, list):

            offers = offers[0]

        if not isinstance(offers, dict):
            return None

        price = offers.get("price")

        if price is None:
            return None

        return float(
            str(price).replace(",", "").strip()
        )

    except Exception:
        return None


# ============================================================
# BODY TYPE
# ============================================================

def _extract_body_type(driver) -> Optional[str]:
    """
    Extract the vehicle-specific body type from
    BE FORWARD's "THE KEYWORDS OF THIS VEHICLE" section.

    The important distinction is that BE FORWARD also has
    site-wide navigation containing SUV, Wagon, Sedan, etc.

    We therefore ONLY inspect the vehicle keyword section.

    Example:

        BMW
        SUV
        MINI
        2020
        Green
        Automatic
        Diesel

    where the SUV link contains:

        veh_type=6

    """

    try:

        containers = driver.find_elements(
            By.CSS_SELECTOR,
            "div.same-genre-item-box"
        )

        for container in containers:

            try:

                text = container.text.strip().lower()

                if "the keywords of this vehicle" not in text:
                    continue

                links = container.find_elements(
                    By.CSS_SELECTOR,
                    "a[href*='veh_type=']"
                )

                for link in links:

                    try:

                        href = link.get_attribute("href") or ""

                        match = re.search(
                            r"veh_type=(\d+)",
                            href
                        )

                        if not match:
                            continue

                        type_id = match.group(1)

                        body_type = VEHICLE_TYPE_MAP.get(
                            type_id
                        )

                        if body_type:
                            return body_type

                    except Exception:
                        continue

            except Exception:
                continue

    except Exception as e:

        log.warning(
            f"[{SITE_NAME}] Could not extract body type: {e}"
        )

    return None


# ============================================================
# YEAR
# ============================================================

def _extract_vehicle_year(
    specs: Dict[str, str],
    driver,
    json_ld: Dict[str, Any]
) -> Optional[int]:
    """
    Extract the vehicle year.

    Priority:

        1. Registration Year/month
        2. Manufacture Year/month
        3. H1/title
        4. JSON-LD name/description
    """

    candidates = [
        specs.get("registration_year_month"),
        specs.get("manufacture_year_month"),
    ]

    # Add page heading/title as fallback.
    try:

        h1 = safe_find_text(
            driver,
            "h1"
        )

        if h1:
            candidates.append(h1)

    except Exception:
        pass

    try:

        title = driver.title

        if title:
            candidates.append(title)

    except Exception:
        pass

    # JSON-LD fields.
    candidates.extend([
        json_ld.get("name"),
        json_ld.get("description"),
    ])

    for candidate in candidates:

        if not candidate:
            continue

        match = re.search(
            r"\b(19\d{2}|20\d{2})\b",
            str(candidate)
        )

        if not match:
            continue

        try:

            year = int(
                match.group(1)
            )

            if MIN_YEAR <= year <= datetime.now().year + 1:
                return year

        except Exception:
            continue

    return None


# ============================================================
# DETAIL PAGE PARSER
# ============================================================

def parse_detail_page(
    driver,
    url: str
) -> Optional[Dict[str, Any]]:
    """
    Parse one BE FORWARD vehicle detail page.

    Returns a dictionary compatible with
    DBManager.save_listings().
    """

    try:

        # ----------------------------------------------------
        # LOAD PAGE
        # ----------------------------------------------------

        safe_get(
            driver,
            url
        )

        if not wait_for_element(
            driver,
            "table.specification",
            timeout=15
        ):

            log.warning(
                f"[{SITE_NAME}] Specification table "
                f"not found: {url}"
            )

            return None

        # ----------------------------------------------------
        # EXTRACT SPECIFICATIONS
        # ----------------------------------------------------

        specs = _build_spec_dict(
            driver
        )

        # ----------------------------------------------------
        # JSON-LD
        # ----------------------------------------------------

        json_ld = _extract_json_ld(
            driver
        )

        # ----------------------------------------------------
        # MAKE / MODEL
        # ----------------------------------------------------

        make, model = _extract_make_model_from_url(
            driver.current_url
        )

        # Prefer JSON-LD brand/name where available.
        try:

            brand = json_ld.get("brand")

            if isinstance(brand, dict):

                json_make = brand.get("name")

                if json_make:
                    make = str(json_make).strip()

            elif isinstance(brand, str) and brand.strip():

                make = brand.strip()

        except Exception:
            pass

        # ----------------------------------------------------
        # YEAR
        # ----------------------------------------------------

        year = _extract_vehicle_year(
            specs,
            driver,
            json_ld
        )

        if year and year < MIN_YEAR:
            return None

        # ----------------------------------------------------
        # MILEAGE
        # ----------------------------------------------------

        mileage_raw = (
            specs.get("mileage")
            or specs.get("odometer")
            or ""
        )

        mileage = extract_mileage(
            mileage_raw
        )

        # ----------------------------------------------------
        # ENGINE
        # ----------------------------------------------------

        engine_raw = (
            specs.get("engine_size")
            or specs.get("engine")
            or ""
        )

        engine_cc = clean_engine_cc(
            engine_raw
        )

        # ----------------------------------------------------
        # FUEL
        # ----------------------------------------------------

        fuel_type = (
            specs.get("fuel")
            or specs.get("fuel_type")
            or ""
        ).strip().title()

        # ----------------------------------------------------
        # TRANSMISSION
        # ----------------------------------------------------

        transmission = (
            specs.get("transmission")
            or specs.get("trans")
            or ""
        ).strip().title()

        # ----------------------------------------------------
        # BODY TYPE
        # ----------------------------------------------------

        body_type = _extract_body_type(
            driver
        )

        # ----------------------------------------------------
        # COLOR
        # ----------------------------------------------------

        color = (
            specs.get("ext_color")
            or specs.get("color")
            or ""
        ).strip().title()

        # ----------------------------------------------------
        # STEERING
        # ----------------------------------------------------

        steering = (
            specs.get("steering")
            or ""
        ).strip().title()

        # ----------------------------------------------------
        # DRIVE TYPE
        # ----------------------------------------------------

        drive_type = (
            specs.get("drive")
            or specs.get("drivetrain")
            or ""
        ).strip().title()

        # ----------------------------------------------------
        # DOORS
        # ----------------------------------------------------

        doors = None

        doors_raw = specs.get(
            "doors",
            ""
        )

        if doors_raw:

            match = re.search(
                r"\d+",
                doors_raw
            )

            if match:
                doors = int(
                    match.group()
                )

        # ----------------------------------------------------
        # SEATS
        # ----------------------------------------------------

        seats = None

        seats_raw = specs.get(
            "seats",
            ""
        )

        if seats_raw:

            match = re.search(
                r"\d+",
                seats_raw
            )

            if match:
                seats = int(
                    match.group()
                )

        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        location = (
            specs.get("location")
            or "Japan"
        ).strip()

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        description = safe_find_text(
            driver,
            ".car-description, #remarks, .remarks"
        )

        # Fall back to JSON-LD description.
        if not description:

            description = (
                json_ld.get("description")
                or ""
            )

        # ----------------------------------------------------
        # PRICE USD
        # ----------------------------------------------------

        # JSON-LD is preferred because it represents the
        # vehicle offer itself rather than a destination/
        # shipping total.
        price_usd = _extract_json_ld_price(
            json_ld
        )

        # Fall back to the price table.
        if price_usd is None:

            price_raw = safe_find_text(
                driver,
                "table.price-view-table"
            )

            price_usd = extract_price(
                price_raw
            )

        # ----------------------------------------------------
        # PRICE JPY
        # ----------------------------------------------------

        # BE FORWARD's current page exposes the offer price
        # in USD. We do NOT invent a JPY conversion.
        price_jpy = None

        # ----------------------------------------------------
        # FINAL RECORD
        # ----------------------------------------------------

        record = {
            "listing_url": url,
            "make": make,
            "model": model,
            "year": year,
            "mileage_km": mileage,
            "engine_cc": engine_cc,
            "fuel_type": fuel_type,
            "transmission": transmission,
            "body_type": body_type,
            "color": color,
            "price_usd": price_usd,
            "price_jpy": price_jpy,
            "steering": steering,
            "drive_type": drive_type,
            "doors": doors,
            "seats": seats,
            "condition": "Used",
            "location": location,
            "description": description,
        }

        return record

    except Exception as e:

        log.error(
            f"[{SITE_NAME}] Error parsing detail page "
            f"{url}: {e}"
        )

        return None


# ============================================================
# MAIN SCRAPER
# ============================================================
def scrape_beforward(max_pages: int = MAX_PAGES) -> None:
    db = DBManager()
    driver = build_driver(load_images=False)
    started_at = datetime.utcnow()

    search_url = f"{BASE_URL}/stocklist/sar=steering/steering=Right/tp_country_id=27"

    total_scraped = 0
    total_saved = 0
    total_errors = 0

    batch = []
    BATCH_SIZE = 20

    try:
        current_url = search_url

        for page_num in range(1, max_pages + 1):
            log.info(
                f"[{SITE_NAME}] Processing page {page_num}/{max_pages}: "
                f"{current_url}"
            )

            # Open the current listing page.
            safe_get(driver, current_url)

            if not wait_for_element(
                driver,
                "a[href*='/id/']",
                timeout=15
            ):
                log.warning(
                    f"[{SITE_NAME}] No vehicle links found on listing page."
                )
                break

            detail_urls = get_listing_urls(driver)

            if not detail_urls:
                log.warning(
                    f"[{SITE_NAME}] No vehicle URLs found on listing page."
                )
                break

            log.info(
                f"[{SITE_NAME}] Processing {len(detail_urls)} vehicles "
                f"from page {page_num}."
            )

            # Scrape every vehicle on the current listing page.
            for index, vehicle_url in enumerate(detail_urls, start=1):
                log.info(
                    f"[{SITE_NAME}] Vehicle {index}/{len(detail_urls)}: "
                    f"{vehicle_url}"
                )

                record = parse_detail_page(driver, vehicle_url)

                if record:
                    batch.append(record)
                    total_scraped += 1
                else:
                    total_errors += 1

                # Save records in batches.
                if len(batch) >= BATCH_SIZE:
                    result = db.save_listings(
                        batch,
                        market="japan",
                        source=SITE_NAME
                    )
                    total_saved += result.get("inserted", 0)
                    batch.clear()

                polite_sleep()

            # IMPORTANT:
            # parse_detail_page() leaves Selenium on the vehicle detail page.
            # Return to the listing page before checking pagination.
            safe_get(driver, current_url)

            if not wait_for_element(
                driver,
                "a[href*='/id/']",
                timeout=15
            ):
                log.warning(
                    f"[{SITE_NAME}] Could not return to listing page "
                    f"before pagination."
                )
                break

            next_url = get_next_page_url(driver)

            if not next_url:
                log.info(f"[{SITE_NAME}] Reached last page.")
                break

            current_url = next_url

            log.info(
                f"[{SITE_NAME}] Next page: {current_url}"
            )

            polite_sleep()

    finally:
        # Save anything left in the final batch.
        if batch:
            result = db.save_listings(
                batch,
                market="japan",
                source=SITE_NAME
            )
            total_saved += result.get("inserted", 0)
            batch.clear()

        driver.quit()

        db.log_run(
            site=SITE_NAME,
            market="japan",
            rows_scraped=total_scraped,
            rows_saved=total_saved,
            errors=total_errors,
            started_at=started_at
        )

        log.info(
            f"[{SITE_NAME}] Scrape finished. "
            f"Scraped: {total_scraped}, "
            f"Saved: {total_saved}, "
            f"Errors: {total_errors}"
        )


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":
    scrape_beforward()
