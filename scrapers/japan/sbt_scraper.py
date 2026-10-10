
"""
scrapers/japan/sbt_scraper.py

SBT Japan vehicle scraper.

This scraper:
    1. Opens SBT Japan search-results pages directly.
    2. Discovers vehicle detail URLs using URL patterns.
    3. Scrapes vehicle details from individual listing pages.
    4. Handles pagination explicitly.
    5. Filters vehicles below MIN_YEAR.
    6. Retries failed page loads through safe_get().
    7. Classifies scraping outcomes accurately.
    8. Saves records to the existing database in batches.

Run:
    python -m scrapers.japan.sbt_scraper
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

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

SITE_NAME = "sbtjapan"
BASE_URL = "https://www.sbtjapan.com"

# Number of successfully scraped records saved to DB at a time.
BATCH_SIZE = 20


# ============================================================================
# SEARCH RESULT PAGE
# ============================================================================

def build_search_url(page: int) -> str:
    """
    Build the current SBT Japan search-results URL.

    SBT currently uses:
        /used-cars/search?page=1
        /used-cars/search?page=2
        /used-cars/search?page=3
        etc.
    """

    return f"{BASE_URL}/used-cars/search?page={page}"


def get_listing_urls(driver) -> List[str]:
    """
    Extract vehicle detail URLs from the current SBT search-results page.

    Expected vehicle URL structure:

        /used-cars/toyota/probox-van/AS4999

    Returns:
        A list of unique vehicle detail URLs.
    """

    urls: List[str] = []

    try:
        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href*='/used-cars/']"
        )

        log.debug(
            f"[{SITE_NAME}] Found {len(links)} candidate "
            f"/used-cars/ links on page."
        )

        for link in links:
            try:
                href = link.get_attribute("href")
            except Exception:
                continue

            if not href:
                continue

            # Remove query parameters and fragments.
            href = href.split("#")[0]
            href = href.split("?")[0]
            href = href.rstrip("/")

            parsed = urlparse(href)
            path = parsed.path

            parts = [part for part in path.split("/") if part]

            # Expected:
            # /used-cars/<make>/<model>/<stock_id>
            #
            # Therefore we need at least four parts.
            if len(parts) < 4:
                continue

            if parts[0].lower() != "used-cars":
                continue

            # Ignore the search page itself.
            if parts[1].lower() == "search":
                continue

            stock_id = parts[-1]

            # SBT stock IDs generally look like:
            # AR0718
            # AS4999
            if not re.fullmatch(
                r"[A-Za-z]{2,5}\d{3,7}",
                stock_id
            ):
                continue

            urls.append(href)

    except Exception as exc:
        log.exception(
            f"[{SITE_NAME}] Error discovering vehicle URLs: {exc}"
        )

    # Deduplicate while preserving order.
    unique_urls = list(dict.fromkeys(urls))

    log.info(
        f"[{SITE_NAME}] Found "
        f"{len(unique_urls)} unique listing URLs."
    )

    for url in unique_urls[:5]:
        log.debug(
            f"[{SITE_NAME}] Listing URL example: {url}"
        )

    return unique_urls


# ============================================================================
# PAGINATION
# ============================================================================

def get_next_page_url(
    driver,
    current_page: int
) -> Optional[str]:
    """
    Determine the next SBT search-results page.

    SBT uses numbered pagination, so we look for a link containing
    the target page number.

    If Selenium cannot see the pagination link, construct the URL
    directly as a fallback.
    """

    target_page = current_page + 1

    try:
        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href*='/used-cars/search']"
        )

        for link in links:
            try:
                href = link.get_attribute("href")
            except Exception:
                continue

            if not href:
                continue

            pattern = (
                rf"(?:[?&])page={target_page}(?:&|$)"
            )

            if re.search(pattern, href):
                return href

    except Exception as exc:
        log.warning(
            f"[{SITE_NAME}] Could not locate next page "
            f"{target_page}: {exc}"
        )

    # Fallback.
    return build_search_url(target_page)


# ============================================================================
# DETAIL PAGE HELPERS
# ============================================================================

def get_label_value(
    driver,
    label: str
) -> str:
    """
    Attempt to find a value associated with a visible label.

    Supports several possible HTML structures because SBT's
    frontend can change slightly between pages/locales.
    """

    # ------------------------------------------------------------------
    # Strategy 1: exact visible text + following sibling
    # ------------------------------------------------------------------

    try:
        element = driver.find_element(
            By.XPATH,
            f"//*[normalize-space(text())='{label}']"
        )

        try:
            sibling = element.find_element(
                By.XPATH,
                "following-sibling::*[1]"
            )

            value = sibling.text.strip()

            if value and value.lower() != label.lower():
                return value

        except Exception:
            pass

        # --------------------------------------------------------------
        # Strategy 2: parent/container text
        # --------------------------------------------------------------

        try:
            parent = element.find_element(
                By.XPATH,
                ".."
            )

            text = parent.text.strip()

            if text:
                cleaned = re.sub(
                    rf"^{re.escape(label)}\s*",
                    "",
                    text,
                    flags=re.IGNORECASE
                ).strip()

                if (
                    cleaned
                    and cleaned.lower() != label.lower()
                ):
                    return cleaned

        except Exception:
            pass

    except Exception:
        pass

    # ------------------------------------------------------------------
    # Strategy 3: label inside a table row
    # ------------------------------------------------------------------

    try:
        element = driver.find_element(
            By.XPATH,
            f"//*[normalize-space(text())='{label}']"
        )

        row = element.find_element(
            By.XPATH,
            "./ancestor::tr[1]"
        )

        cells = row.find_elements(
            By.XPATH,
            "./th|./td"
        )

        if len(cells) >= 2:
            for cell in cells[1:]:
                value = cell.text.strip()

                if value:
                    return value

    except Exception:
        pass

    return ""


def extract_sbt_year(
    driver
) -> Optional[int]:
    """
    Extract the vehicle year from the SBT detail page.

    We inspect:
        1. H1
        2. Page title
        3. Explicit Year label
    """

    # ------------------------------------------------------------------
    # Strategy 1: H1
    # ------------------------------------------------------------------

    try:
        h1_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "h1"
        )

        for h1 in h1_elements:
            text = h1.text.strip()

            match = re.search(
                r"\b(19|20)\d{2}\b",
                text
            )

            if match:
                return int(match.group())

    except Exception:
        pass

    # ------------------------------------------------------------------
    # Strategy 2: page title
    # ------------------------------------------------------------------

    try:
        title = driver.title or ""

        match = re.search(
            r"\b(19|20)\d{2}\b",
            title
        )

        if match:
            return int(match.group())

    except Exception:
        pass

    # ------------------------------------------------------------------
    # Strategy 3: explicit Year label
    # ------------------------------------------------------------------

    year_raw = get_label_value(
        driver,
        "Year"
    )

    if year_raw:
        year = extract_year(year_raw)

        if year:
            return year

    return None


def extract_sbt_stock_id(
    url: str
) -> Optional[str]:
    """
    Extract the stock ID from an SBT vehicle URL.

    Example:
        /used-cars/toyota/probox-van/AS4999

    Returns:
        AS4999
    """

    try:
        path = urlparse(url).path.rstrip("/")

        parts = [
            part
            for part in path.split("/")
            if part
        ]

        if parts:
            stock_id = parts[-1]

            if re.fullmatch(
                r"[A-Za-z]{2,5}\d{3,7}",
                stock_id
            ):
                return stock_id

    except Exception:
        pass

    return None


def extract_numeric_value(
    text: str
) -> Optional[int]:
    """
    Extract the first integer from a string.

    Examples:
        '138,000km' -> 138000
        '1,500cc'   -> 1500
        '5 doors'   -> 5
    """

    if not text:
        return None

    match = re.search(
        r"\d[\d,]*",
        text
    )

    if not match:
        return None

    try:
        return int(
            match.group().replace(",", "")
        )
    except ValueError:
        return None


def extract_seats_value(
    text: str
) -> Optional[int]:
    """
    Extract seat count.

    Uses the first number displayed in the field.
    """

    if not text:
        return None

    match = re.search(
        r"\d+",
        text
    )

    if not match:
        return None

    try:
        return int(match.group())
    except ValueError:
        return None


# ============================================================================
# DETAIL PAGE PARSER
# ============================================================================

def parse_detail_page(
    driver,
    url: str
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Scrape one SBT vehicle detail page.

    Returns:
        (record, status)

    Possible statuses:

        SUCCESS
        SKIPPED_MIN_YEAR
        PAGE_LOAD_FAILED
        YEAR_NOT_FOUND
        PARSE_FAILED
    """

    try:
        log.debug(
            f"[{SITE_NAME}] Opening detail page: {url}"
        )

        # --------------------------------------------------------------
        # LOAD PAGE
        # --------------------------------------------------------------

        loaded = safe_get(
            driver,
            url
        )

        if not loaded:
            log.warning(
                f"[{SITE_NAME}] "
                f"Vehicle page failed to load: {url}"
            )

            return None, "PAGE_LOAD_FAILED"

        # --------------------------------------------------------------
        # WAIT FOR VEHICLE CONTENT
        # --------------------------------------------------------------

        page_ready = wait_for_element(
            driver,
            "h1, .car-title, .car-name",
            timeout=20
        )

        if not page_ready:
            log.warning(
                f"[{SITE_NAME}] "
                f"Vehicle content not found: {url}"
            )

            return None, "PAGE_LOAD_FAILED"

        # --------------------------------------------------------------
        # YEAR
        # --------------------------------------------------------------

        year = extract_sbt_year(driver)

        if year is None:
            log.warning(
                f"[{SITE_NAME}] "
                f"Could not determine vehicle year: {url}"
            )

            return None, "YEAR_NOT_FOUND"

        if year < MIN_YEAR:
            log.debug(
                f"[{SITE_NAME}] "
                f"Skipping {url}: "
                f"year {year} < MIN_YEAR {MIN_YEAR}"
            )

            return None, "SKIPPED_MIN_YEAR"

        # --------------------------------------------------------------
        # BASIC VEHICLE DETAILS
        # --------------------------------------------------------------

        make = get_label_value(
            driver,
            "Make"
        )

        model = get_label_value(
            driver,
            "Model"
        )

        body_type = get_label_value(
            driver,
            "Body Type"
        )

        color = get_label_value(
            driver,
            "Body color"
        )

        if not color:
            color = get_label_value(
                driver,
                "Body Color"
            )

        # --------------------------------------------------------------
        # VEHICLE SPECIFICATIONS
        # --------------------------------------------------------------

        mileage_raw = get_label_value(
            driver,
            "Mileage"
        )

        engine_raw = get_label_value(
            driver,
            "Engine"
        )

        fuel = get_label_value(
            driver,
            "Fuel"
        )

        transmission = get_label_value(
            driver,
            "Transmission"
        )

        steering = get_label_value(
            driver,
            "Steering"
        )

        drive = get_label_value(
            driver,
            "Drive"
        )

        doors_raw = get_label_value(
            driver,
            "Door"
        )

        seats_raw = get_label_value(
            driver,
            "Seats"
        )

        # --------------------------------------------------------------
        # PRICE
        # --------------------------------------------------------------

        price_raw = ""

        price_selectors = [
            ".price",
            ".car-price",
            "span.priceUSD",
            "[class*='price']",
        ]

        for selector in price_selectors:
            text = safe_find_text(
                driver,
                selector
            )

            if text:
                price_raw = text
                break

        price_usd = extract_price(
            price_raw
        )

        # --------------------------------------------------------------
        # CLEAN VALUES
        # --------------------------------------------------------------

        mileage = extract_mileage(
            mileage_raw
        )

        if mileage is None:
            mileage = extract_numeric_value(
                mileage_raw
            )

        engine_cc = clean_engine_cc(
            engine_raw
        )

        if engine_cc is None:
            engine_cc = extract_numeric_value(
                engine_raw
            )

        doors = extract_numeric_value(
            doors_raw
        )

        seats = extract_seats_value(
            seats_raw
        )

        stock_id = extract_sbt_stock_id(
            url
        )

        # --------------------------------------------------------------
        # DESCRIPTION
        # --------------------------------------------------------------

        description = ""

        description_selectors = [
            ".car-description",
            ".description",
            "[class*='description']",
        ]

        for selector in description_selectors:
            text = safe_find_text(
                driver,
                selector
            )

            if text:
                description = text
                break

        # --------------------------------------------------------------
        # FALLBACK: H1 FOR MAKE/MODEL
        # --------------------------------------------------------------

        if not make or not model:
            h1 = safe_find_text(
                driver,
                "h1"
            )

            if h1 and not make:
                make = h1

        # --------------------------------------------------------------
        # BUILD RECORD
        # --------------------------------------------------------------

        record = {
            "listing_url": url,
            "make": make.title() if make else "",
            "model": model.title() if model else "",
            "year": year,
            "mileage_km": mileage,
            "engine_cc": engine_cc,
            "fuel_type": (
                fuel.title()
                if fuel
                else ""
            ),
            "transmission": (
                transmission.title()
                if transmission
                else ""
            ),
            "body_type": (
                body_type.title()
                if body_type
                else ""
            ),
            "color": (
                color.title()
                if color
                else ""
            ),
            "price_usd": price_usd,
            "price_jpy": None,
            "steering": (
                steering
                if steering
                else "RHD"
            ),
            "drive_type": drive,
            "doors": doors,
            "seats": seats,
            "condition": "Used",
            "location": "Japan",
            "description": description,
        }

        log.debug(
            f"[{SITE_NAME}] Parsed vehicle: "
            f"{record['make']} "
            f"{record['model']} "
            f"{record['year']} "
            f"| {stock_id}"
        )

        return record, "SUCCESS"

    except Exception as exc:
        log.exception(
            f"[{SITE_NAME}] Error parsing "
            f"SBT detail page {url}: {exc}"
        )

        return None, "PARSE_FAILED"


# ============================================================================
# MAIN SCRAPER
# ============================================================================

def scrape_sbt(
    max_pages: int = MAX_PAGES
) -> None:
    """
    Run the SBT Japan scraper.
    """

    log.info(
        f"[{SITE_NAME}] Starting scraper..."
    )

    db = DBManager()
    driver = build_driver()

    started_at = datetime.utcnow()

    total_discovered = 0
    total_scraped = 0
    total_saved = 0

    total_skipped_year = 0
    total_page_load_failures = 0
    total_year_failures = 0
    total_parse_failures = 0
    total_db_errors = 0

    batch: List[Dict[str, Any]] = []

    try:
        # ==============================================================
        # PAGE LOOP
        # ==============================================================

        for page_num in range(
            1,
            max_pages + 1
        ):
            current_url = build_search_url(
                page_num
            )

            log.info(
                f"[{SITE_NAME}] "
                f"Page {page_num}/{max_pages} "
                f"→ {current_url}"
            )

            # ----------------------------------------------------------
            # OPEN SEARCH RESULTS
            # ----------------------------------------------------------

            search_loaded = safe_get(
                driver,
                current_url
            )

            if not search_loaded:
                log.error(
                    f"[{SITE_NAME}] "
                    f"Search page failed to load: "
                    f"{current_url}"
                )

                break

            # ----------------------------------------------------------
            # WAIT FOR VEHICLE LINKS
            # ----------------------------------------------------------

            if not wait_for_element(
                driver,
                "a[href*='/used-cars/']",
                timeout=20
            ):
                log.warning(
                    f"[{SITE_NAME}] "
                    f"No vehicle links found "
                    f"on page {page_num}."
                )

                try:
                    log.warning(
                        f"[{SITE_NAME}] "
                        f"Page title: {driver.title}"
                    )

                    log.warning(
                        f"[{SITE_NAME}] "
                        f"Current URL: {driver.current_url}"
                    )

                except Exception:
                    pass

                break

            # ----------------------------------------------------------
            # DISCOVER VEHICLE URLS
            # ----------------------------------------------------------

            detail_urls = get_listing_urls(
                driver
            )

            discovered_count = len(
                detail_urls
            )

            total_discovered += discovered_count

            log.info(
                f"[{SITE_NAME}] "
                f"Page {page_num}: "
                f"{discovered_count} vehicle URLs discovered."
            )

            if not detail_urls:
                log.warning(
                    f"[{SITE_NAME}] "
                    f"No vehicle URLs discovered "
                    f"on page {page_num}."
                )

                break

            # ----------------------------------------------------------
            # CAPTURE NEXT PAGE BEFORE DETAIL SCRAPING
            # ----------------------------------------------------------

            next_url = get_next_page_url(
                driver,
                page_num
            )

            # ----------------------------------------------------------
            # SCRAPE DETAIL PAGES
            # ----------------------------------------------------------

            for index, url in enumerate(
                detail_urls,
                start=1
            ):
                log.info(
                    f"[{SITE_NAME}] "
                    f"Page {page_num} | "
                    f"Vehicle {index}/{discovered_count}"
                )

                record, status = parse_detail_page(
                    driver,
                    url
                )

                # ------------------------------------------------------
                # SUCCESS
                # ------------------------------------------------------

                if status == "SUCCESS" and record:
                    batch.append(record)

                    total_scraped += 1

                # ------------------------------------------------------
                # BELOW MINIMUM YEAR
                # ------------------------------------------------------

                elif status == "SKIPPED_MIN_YEAR":
                    total_skipped_year += 1

                # ------------------------------------------------------
                # PAGE LOAD FAILURE
                # ------------------------------------------------------

                elif status == "PAGE_LOAD_FAILED":
                    total_page_load_failures += 1

                # ------------------------------------------------------
                # YEAR COULD NOT BE FOUND
                # ------------------------------------------------------

                elif status == "YEAR_NOT_FOUND":
                    total_year_failures += 1

                # ------------------------------------------------------
                # OTHER PARSING FAILURE
                # ------------------------------------------------------

                elif status == "PARSE_FAILED":
                    total_parse_failures += 1

                else:
                    total_parse_failures += 1

                # ------------------------------------------------------
                # SAVE BATCH
                # ------------------------------------------------------

                if len(batch) >= BATCH_SIZE:
                    try:
                        result = db.save_listings(
                            batch,
                            market="japan",
                            source=SITE_NAME
                        )

                        if isinstance(result, dict):
                            inserted = result.get(
                                "inserted",
                                len(batch)
                            )
                        else:
                            inserted = len(batch)

                        total_saved += inserted

                        log.info(
                            f"[{SITE_NAME}] "
                            f"Batch saved. "
                            f"Inserted: {inserted}"
                        )

                    except Exception as exc:
                        log.exception(
                            f"[{SITE_NAME}] "
                            f"Database batch save failed: {exc}"
                        )

                        total_db_errors += len(batch)

                    finally:
                        batch.clear()

                # ------------------------------------------------------
                # POLITE DELAY
                # ------------------------------------------------------

                polite_sleep()

            # ----------------------------------------------------------
            # PAGE SUMMARY
            # ----------------------------------------------------------

            total_failures = (
                total_page_load_failures
                + total_year_failures
                + total_parse_failures
            )

            log.info(
                f"[{SITE_NAME}] "
                f"Page {page_num} complete. "
                f"Discovered so far: {total_discovered} | "
                f"Scraped so far: {total_scraped} | "
                f"Saved so far: {total_saved} | "
                f"Skipped MIN_YEAR: {total_skipped_year} | "
                f"Load failures: {total_page_load_failures} | "
                f"Year failures: {total_year_failures} | "
                f"Parse failures: {total_parse_failures} | "
                f"Failures: {total_failures}"
            )

            # ----------------------------------------------------------
            # MAX PAGE CHECK
            # ----------------------------------------------------------

            if page_num >= max_pages:
                log.info(
                    f"[{SITE_NAME}] "
                    f"Reached MAX_PAGES={max_pages}."
                )

                break

            # ----------------------------------------------------------
            # NEXT PAGE
            # ----------------------------------------------------------

            if not next_url:
                log.info(
                    f"[{SITE_NAME}] "
                    f"No next page found. "
                    f"Last page reached."
                )

                break

            log.info(
                f"[{SITE_NAME}] "
                f"Next page → {next_url}"
            )

            polite_sleep()

    except KeyboardInterrupt:
        log.warning(
            f"[{SITE_NAME}] "
            f"Scraper interrupted by user."
        )

    except Exception as exc:
        log.exception(
            f"[{SITE_NAME}] "
            f"Fatal scraper error: {exc}"
        )

    finally:
        # ==============================================================
        # SAVE REMAINING BATCH
        # ==============================================================

        if batch:
            try:
                result = db.save_listings(
                    batch,
                    market="japan",
                    source=SITE_NAME
                )

                if isinstance(result, dict):
                    inserted = result.get(
                        "inserted",
                        len(batch)
                    )
                else:
                    inserted = len(batch)

                total_saved += inserted

                log.info(
                    f"[{SITE_NAME}] "
                    f"Final batch saved. "
                    f"Inserted: {inserted}"
                )

            except Exception as exc:
                log.exception(
                    f"[{SITE_NAME}] "
                    f"Final database save failed: {exc}"
                )

                total_db_errors += len(batch)

            finally:
                batch.clear()

        # ==============================================================
        # CLOSE DRIVER
        # ==============================================================

        try:
            driver.quit()
        except Exception:
            pass

        # ==============================================================
        # FINAL STATISTICS
        # ==============================================================

        total_failures = (
            total_page_load_failures
            + total_year_failures
            + total_parse_failures
        )

        total_attempted = (
            total_scraped
            + total_skipped_year
            + total_failures
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Scraping complete."
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Pages requested: {max_pages}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Vehicle URLs discovered: "
            f"{total_discovered}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Vehicles scraped successfully: "
            f"{total_scraped}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Vehicles skipped (MIN_YEAR): "
            f"{total_skipped_year}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Page-load failures: "
            f"{total_page_load_failures}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Year extraction failures: "
            f"{total_year_failures}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Parsing failures: "
            f"{total_parse_failures}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Total scraping failures: "
            f"{total_failures}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Database errors: "
            f"{total_db_errors}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Records saved: "
            f"{total_saved}"
        )

        log.info(
            f"[{SITE_NAME}] "
            f"Outcome count checked: "
            f"{total_attempted}"
        )


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    scrape_sbt()