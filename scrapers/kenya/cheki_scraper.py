"""
scrapers/kenya/cheki_scraper.py
────────────────────────────────
Cheki Kenya vehicle scraper.

Primary extraction strategy:
    1. Discover vehicle URLs from Cheki catalogue pages.
    2. Open each vehicle detail page.
    3. Extract the structured "Car" JSON-LD object.
    4. Use visible DOM labels only as fallbacks for fields missing
       from JSON-LD.
    5. Filter vehicles below MIN_YEAR.
    6. Validate records before database insertion.
    7. Save records in batches.
    8. Report scraping and database outcomes accurately.

Run:
    python -m scrapers.kenya.cheki_scraper
"""

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from config.settings import MAX_PAGES, MIN_YEAR
from database.db_manager import DBManager
from utils.driver_factory import build_driver
from utils.logger import get_logger
from utils.scraping_helpers import safe_get, polite_sleep


log = get_logger(__name__)


SITE_NAME = "cheki_kenya"
BASE_URL = "https://cheki.co.ke"
LISTING_URL = f"{BASE_URL}/vehicles"

BATCH_SIZE = 25


# ══════════════════════════════════════════════════════════════════════════════
# GENERAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _clean_text(value: Any) -> str:
    """Convert a value to clean single-line text."""

    if value is None:
        return ""

    text = str(value)

    text = re.sub(r"\s+", " ", text)
    text = text.replace("\xa0", " ")

    return text.strip()


def _normalize_url(url: str) -> str:
    """Remove fragments and trailing slash from a URL."""

    if not url:
        return ""

    url = url.split("#", 1)[0].strip()
    url = url.rstrip("/")

    return url


def _extract_number(value: Any) -> Optional[float]:
    """Extract the first numeric value from text."""

    if value is None:
        return None

    text = str(value)

    text = text.replace(",", "")
    text = text.replace(" ", "")

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    """Convert a numeric value to int."""

    number = _extract_number(value)

    if number is None:
        return None

    try:
        return int(number)
    except (TypeError, ValueError):
        return None


def _extract_year(value: Any) -> Optional[int]:
    """Extract a four-digit vehicle year."""

    if value is None:
        return None

    match = re.search(r"\b(19|20)\d{2}\b", str(value))

    if not match:
        return None

    try:
        return int(match.group())
    except (TypeError, ValueError):
        return None


# ══════════════════════════════════════════════════════════════════════════════
# LISTING URL DISCOVERY
# ══════════════════════════════════════════════════════════════════════════════

def _get_listing_urls(driver) -> List[str]:
    """
    Extract vehicle detail URLs from the current catalogue page.

    Current Cheki detail URLs follow:

        /vehicle/<slug>
    """

    urls: List[str] = []

    try:
        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href*='/vehicle/']"
        )

        for link in links:
            try:
                href = link.get_attribute("href")
            except Exception:
                continue

            if not href:
                continue

            href = _normalize_url(href)

            parsed = urlparse(href)

            if parsed.netloc and parsed.netloc != "cheki.co.ke":
                continue

            if "/vehicle/" not in parsed.path:
                continue

            urls.append(href)

    except Exception as exc:
        log.error(
            f"[{SITE_NAME}] Error discovering listing URLs: {exc}"
        )

    return list(dict.fromkeys(urls))


def _get_result_indicator(driver) -> str:
    """
    Find the catalogue result indicator.

    Example:

        253-261 of 261
    """

    try:
        body_text = _clean_text(driver.find_element(By.TAG_NAME, "body").text)

        match = re.search(
            r"\b(\d+)\s*-\s*(\d+)\s+of\s+(\d+)\b",
            body_text,
            flags=re.IGNORECASE
        )

        if match:
            return (
                f"{match.group(1)}-"
                f"{match.group(2)} of "
                f"{match.group(3)}"
            )

    except Exception:
        pass

    return ""


def _result_reaches_end(indicator: str) -> bool:
    """Return True when a result indicator reaches the final result."""

    if not indicator:
        return False

    match = re.match(
        r"(\d+)-(\d+)\s+of\s+(\d+)",
        indicator
    )

    if not match:
        return False

    end = int(match.group(2))
    total = int(match.group(3))

    return end >= total


# ══════════════════════════════════════════════════════════════════════════════
# JSON-LD EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def _find_car_json_ld(driver) -> Dict[str, Any]:
    """
    Extract the structured JSON-LD object whose @type contains "Car".

    This is the primary Cheki extraction method.

    Example fields exposed by Cheki:

        brand.name
        model
        vehicleModelDate
        fuelType
        vehicleTransmission
        color
        bodyType
        offers.price
        offers.priceCurrency
        vehicleEngine.engineDisplacement.value
        mileageFromOdometer.value
        driveWheelConfiguration
    """

    result: Dict[str, Any] = {}

    try:
        scripts = driver.find_elements(
            By.CSS_SELECTOR,
            "script[type='application/ld+json']"
        )

        for script in scripts:

            try:
                raw = script.get_attribute("textContent")

                if not raw:
                    raw = script.get_attribute("innerHTML")

                if not raw:
                    continue

                data = json.loads(raw)

            except Exception:
                continue

            candidates: List[Any]

            if isinstance(data, list):
                candidates = data

            elif isinstance(data, dict):
                candidates = [data]

                graph = data.get("@graph")

                if isinstance(graph, list):
                    candidates.extend(graph)

            else:
                continue

            for item in candidates:

                if not isinstance(item, dict):
                    continue

                item_type = item.get("@type", "")

                if isinstance(item_type, list):
                    is_car = "Car" in item_type

                else:
                    is_car = str(item_type).lower() == "car"

                if not is_car:
                    continue

                result = item

                return result

    except Exception as exc:
        log.warning(
            f"[{SITE_NAME}] JSON-LD extraction failed: {exc}"
        )

    return result


def _json_ld_brand(json_ld: Dict[str, Any]) -> str:
    """Extract vehicle make from JSON-LD."""

    brand = json_ld.get("brand")

    if isinstance(brand, dict):
        return _clean_text(brand.get("name"))

    return _clean_text(brand)


def _json_ld_model(json_ld: Dict[str, Any]) -> str:
    """Extract vehicle model from JSON-LD."""

    return _clean_text(json_ld.get("model"))


def _json_ld_year(json_ld: Dict[str, Any]) -> Optional[int]:
    """Extract vehicle year from JSON-LD."""

    return _extract_year(
        json_ld.get("vehicleModelDate")
    )


def _json_ld_price(json_ld: Dict[str, Any]) -> Optional[float]:
    """Extract price from JSON-LD offers."""

    offers = json_ld.get("offers")

    if isinstance(offers, list):
        offers = offers[0] if offers else None

    if not isinstance(offers, dict):
        return None

    return _extract_number(
        offers.get("price")
    )


def _json_ld_currency(json_ld: Dict[str, Any]) -> str:
    """Extract price currency from JSON-LD."""

    offers = json_ld.get("offers")

    if isinstance(offers, list):
        offers = offers[0] if offers else None

    if not isinstance(offers, dict):
        return ""

    return _clean_text(
        offers.get("priceCurrency")
    )


def _json_ld_engine_cc(json_ld: Dict[str, Any]) -> Optional[float]:
    """Extract engine displacement from JSON-LD."""

    engine = json_ld.get("vehicleEngine")

    if not isinstance(engine, dict):
        return None

    displacement = engine.get("engineDisplacement")

    if isinstance(displacement, dict):
        return _extract_number(
            displacement.get("value")
        )

    return _extract_number(displacement)


def _json_ld_mileage(json_ld: Dict[str, Any]) -> Optional[float]:
    """Extract mileage from JSON-LD."""

    mileage = json_ld.get("mileageFromOdometer")

    if isinstance(mileage, dict):
        return _extract_number(
            mileage.get("value")
        )

    return _extract_number(mileage)


def _json_ld_offer_url(json_ld: Dict[str, Any]) -> str:
    """Extract listing URL from JSON-LD."""

    offers = json_ld.get("offers")

    if isinstance(offers, list):
        offers = offers[0] if offers else None

    if not isinstance(offers, dict):
        return ""

    return _clean_text(
        offers.get("url")
    )


# ══════════════════════════════════════════════════════════════════════════════
# DOM FALLBACK HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _extract_label_value(
    soup: BeautifulSoup,
    label: str
) -> str:
    """
    Extract a value associated with a visible specification label.

    This deliberately searches around the exact label instead of
    using the entire page text, preventing the Offer modal from
    contaminating vehicle fields.
    """

    label_normalized = _clean_text(label).lower()

    # Strategy 1: exact element text.
    for element in soup.find_all(
        string=lambda value: (
            value and
            _clean_text(value).lower() == label_normalized
        )
    ):

        parent = element.parent

        if parent is None:
            continue

        # Check direct sibling.
        for sibling in parent.find_next_siblings():
            value = _clean_text(sibling.get_text(" ", strip=True))

            if value and value.lower() != label_normalized:
                return value

        # Check parent text.
        parent_text = _clean_text(
            parent.get_text(" ", strip=True)
        )

        if parent_text:
            cleaned = re.sub(
                rf"^{re.escape(label)}\s*[:\-]?\s*",
                "",
                parent_text,
                flags=re.IGNORECASE
            ).strip()

            if cleaned and cleaned.lower() != label_normalized:
                return cleaned

        # Check grandparent text.
        grandparent = parent.parent

        if grandparent is not None:

            text = _clean_text(
                grandparent.get_text(" ", strip=True)
            )

            cleaned = re.sub(
                rf"^{re.escape(label)}\s*[:\-]?\s*",
                "",
                text,
                flags=re.IGNORECASE
            ).strip()

            if cleaned and cleaned.lower() != label_normalized:
                return cleaned

    return ""


def _extract_description(
    soup: BeautifulSoup,
    json_ld: Dict[str, Any]
) -> str:
    """
    Extract seller description.

    JSON-LD description is preferred because it is structured.
    """

    description = _clean_text(
        json_ld.get("description")
    )

    if description:
        return description

    labels = [
        "Seller's Description",
        "Seller Description",
        "Description",
    ]

    for label in labels:

        value = _extract_label_value(
            soup,
            label
        )

        if value:
            return value

    return ""


def _extract_page_title(soup: BeautifulSoup) -> str:
    """Extract H1/title text as a fallback."""

    h1 = soup.find("h1")

    if h1:
        text = _clean_text(h1.get_text(" ", strip=True))

        if text:
            return text

    title = soup.find("title")

    if title:
        return _clean_text(
            title.get_text(" ", strip=True)
        )

    return ""


def _extract_make_from_model_link(
    soup: BeautifulSoup
) -> str:
    """
    Fallback make extraction from Cheki's canonical make/model link.

    Example:

        /vehicles?make=toyota&model=rav4
    """

    for link in soup.find_all("a", href=True):

        href = str(link.get("href"))

        if "/vehicles?" not in href:
            continue

        match = re.search(
            r"[?&]make=([^&]+)",
            href,
            flags=re.IGNORECASE
        )

        if not match:
            continue

        value = match.group(1)

        value = value.replace("+", " ")
        value = value.replace("-", " ")

        return value.strip().title()

    return ""


# ══════════════════════════════════════════════════════════════════════════════
# CONTAMINATION VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

CONTAMINATION_MARKERS = [
    "your offer",
    "message / notes",
    "message / notes (optional)",
    "your contact details",
    "full name",
    "submit offer",
    "cancel",
    "email",
    "phone",
    "offer your offer",
]


def _looks_contaminated(value: Any) -> bool:
    """Detect obvious UI/modal contamination."""

    text = _clean_text(value).lower()

    if not text:
        return False

    for marker in CONTAMINATION_MARKERS:

        if marker in text:
            return True

    return False


def _safe_field(
    value: Any,
    fallback: str = ""
) -> str:
    """
    Return a cleaned value unless it contains obvious UI contamination.
    """

    cleaned = _clean_text(value)

    if not cleaned:
        return fallback

    if _looks_contaminated(cleaned):
        return fallback

    return cleaned


# ══════════════════════════════════════════════════════════════════════════════
# VEHICLE RECORD EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def _extract_detail(
    driver,
    url: str
) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    Extract one vehicle.

    Returns:

        ("SUCCESS", record)
        ("SKIPPED_MIN_YEAR", None)
        ("PAGE_LOAD_FAILED", None)
        ("YEAR_NOT_FOUND", None)
        ("PARSE_FAILED", None)
    """

    if not safe_get(driver, url):
        return "PAGE_LOAD_FAILED", None

    try:
        html = driver.page_source

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        json_ld = _find_car_json_ld(driver)

        if not json_ld:
            log.warning(
                f"[{SITE_NAME}] No Car JSON-LD found: {url}"
            )

        # ------------------------------------------------------------------
        # PRIMARY STRUCTURED FIELDS
        # ------------------------------------------------------------------

        make = _safe_field(
            _json_ld_brand(json_ld)
        )

        model = _safe_field(
            _json_ld_model(json_ld)
        )

        year = _json_ld_year(json_ld)

        fuel_type = _safe_field(
            json_ld.get("fuelType")
        )

        transmission = _safe_field(
            json_ld.get("vehicleTransmission")
        )

        color = _safe_field(
            json_ld.get("color")
        )

        body_type = _safe_field(
            json_ld.get("bodyType")
        )

        engine_cc = _json_ld_engine_cc(
            json_ld
        )

        mileage_km = _json_ld_mileage(
            json_ld
        )

        drive_type = _safe_field(
            json_ld.get("driveWheelConfiguration")
        )

        price_kes = _json_ld_price(
            json_ld
        )

        currency = _json_ld_currency(
            json_ld
        )

        # ------------------------------------------------------------------
        # FALLBACKS
        # ------------------------------------------------------------------

        if not make:
            make = _extract_make_from_model_link(
                soup
            )

        if not make:
            make = _safe_field(
                _extract_label_value(
                    soup,
                    "Make"
                )
            )

        if not model:
            model = _safe_field(
                _extract_label_value(
                    soup,
                    "Model"
                )
            )

        if year is None:
            year = _extract_year(
                _extract_label_value(
                    soup,
                    "Year"
                )
            )

        if fuel_type == "":
            fuel_type = _safe_field(
                _extract_label_value(
                    soup,
                    "Fuel"
                )
            )

        if transmission == "":
            transmission = _safe_field(
                _extract_label_value(
                    soup,
                    "Gearbox"
                )
            )

        if transmission == "":
            transmission = _safe_field(
                _extract_label_value(
                    soup,
                    "Transmission"
                )
            )

        if body_type == "":
            body_type = _safe_field(
                _extract_label_value(
                    soup,
                    "Body"
                )
            )

        if color == "":
            color = _safe_field(
                _extract_label_value(
                    soup,
                    "Color"
                )
            )

        if engine_cc is None:
            engine_cc = _extract_number(
                _extract_label_value(
                    soup,
                    "Engine"
                )
            )

        if mileage_km is None:
            mileage_km = _extract_number(
                _extract_label_value(
                    soup,
                    "Mileage"
                )
            )

        if drive_type == "":
            drive_type = _safe_field(
                _extract_label_value(
                    soup,
                    "Drivetrain"
                )
            )

        if price_kes is None:
            price_kes = _extract_number(
                _extract_label_value(
                    soup,
                    "Price"
                )
            )

        location = _safe_field(
            _extract_label_value(
                soup,
                "Location"
            )
        )

        condition = _safe_field(
            _extract_label_value(
                soup,
                "Condition"
            )
        )

        description = _extract_description(
            soup,
            json_ld
        )

        # ------------------------------------------------------------------
        # VALIDATION
        # ------------------------------------------------------------------

        if year is None:
            return "YEAR_NOT_FOUND", None

        if year < MIN_YEAR:
            return "SKIPPED_MIN_YEAR", None

        if not make:
            log.warning(
                f"[{SITE_NAME}] Missing make: {url}"
            )
            return "PARSE_FAILED", None

        if not model:
            log.warning(
                f"[{SITE_NAME}] Missing model: {url}"
            )
            return "PARSE_FAILED", None

        if _looks_contaminated(make):
            log.warning(
                f"[{SITE_NAME}] Contaminated make rejected: {url}"
            )
            return "PARSE_FAILED", None

        if _looks_contaminated(model):
            log.warning(
                f"[{SITE_NAME}] Contaminated model rejected: {url}"
            )
            return "PARSE_FAILED", None

        # The database expects KES for Kenyan listings.
        if currency and currency.upper() != "KES":
            log.warning(
                f"[{SITE_NAME}] Unexpected currency "
                f"{currency} for {url}"
            )

        listing_url = _normalize_url(
            _json_ld_offer_url(json_ld)
        )

        if not listing_url:
            listing_url = _normalize_url(url)

        record: Dict[str, Any] = {
            "listing_url": listing_url,
            "source_site": SITE_NAME,
            "make": make,
            "model": model,
            "year": year,
            "mileage_km": mileage_km,
            "engine_cc": engine_cc,
            "fuel_type": fuel_type,
            "transmission": transmission,
            "body_type": body_type,
            "color": color,
            "price_kes": price_kes,
            "condition": condition,
            "location": location,
            "description": description,
        }

        return "SUCCESS", record

    except Exception as exc:
        log.exception(
            f"[{SITE_NAME}] Failed to parse {url}: {exc}"
        )

        return "PARSE_FAILED", None


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════════════════════

def _save_batch(
    db: DBManager,
    batch: List[Dict[str, Any]]
) -> tuple[int, int]:
    """
    Save a batch and return:

        (rows_saved, database_errors)
    """

    if not batch:
        return 0, 0

    try:
        result = db.save_listings(
            batch,
            market="kenya",
            source=SITE_NAME
        )

        inserted = int(
            result.get("inserted", 0)
        )

        if inserted == len(batch):

            print(
                f"[Cheki] DB saved {inserted} records."
            )

            return inserted, 0

        print(
            f"[Cheki] DB SAVE FAILED: "
            f"expected {len(batch)}, got {inserted}."
        )

        return inserted, len(batch) - inserted

    except Exception as exc:

        print(
            f"[Cheki] Database exception: {exc}"
        )

        return 0, len(batch)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

def scrape_cheki(
    max_pages: int = MAX_PAGES
) -> None:
    """Run the Cheki Kenya scraper."""

    started_at = datetime.now()

    driver = None
    db = DBManager()

    seen_urls = set()

    records: List[Dict[str, Any]] = []

    rows_scraped = 0
    rows_saved = 0

    skipped_min_year = 0
    page_load_failures = 0
    year_failures = 0
    parse_failures = 0
    database_errors = 0

    try:

        driver = build_driver()

        print()
        print("=" * 72)
        print("CHEKI KENYA SCRAPER")
        print("=" * 72)
        print(f"Minimum year: {MIN_YEAR}")
        print(f"Maximum pages: {max_pages}")
        print("=" * 72)

        # ══════════════════════════════════════════════════════════════════
        # PHASE 1: DISCOVER LISTING URLs
        # ══════════════════════════════════════════════════════════════════

        print()
        print("[Cheki] Phase 1: Discovering vehicle URLs...")

        all_urls: List[str] = []

        for page in range(1, max_pages + 1):

            page_url = (
                f"{LISTING_URL}?page={page}"
            )

            print(
                f"[Cheki] Catalogue page {page}: "
                f"{page_url}"
            )

            if not safe_get(driver, page_url):
                print(
                    f"[Cheki] Could not load catalogue "
                    f"page {page}."
                )
                page_load_failures += 1
                continue

            page_urls = _get_listing_urls(
                driver
            )

            new_urls = [
                url
                for url in page_urls
                if url not in seen_urls
            ]

            for url in new_urls:
                seen_urls.add(url)

            all_urls.extend(new_urls)

            indicator = _get_result_indicator(
                driver
            )

            print(
                f"[Cheki] Page {page}: "
                f"{len(page_urls)} URLs, "
                f"{len(new_urls)} new"
                + (
                    f", results {indicator}"
                    if indicator
                    else ""
                )
            )

            if indicator and _result_reaches_end(
                indicator
            ):
                print(
                    f"[Cheki] Page {page} reaches "
                    f"the reported final result. "
                    f"Ending catalogue discovery."
                )
                break

            if not page_urls:
                print(
                    f"[Cheki] Page {page} returned "
                    f"no vehicle URLs. Ending."
                )
                break

            polite_sleep(0.8, 1.5)

        print()
        print(
            f"[Cheki] Total unique vehicle URLs: "
            f"{len(all_urls)}"
        )

        # ══════════════════════════════════════════════════════════════════
        # PHASE 2: SCRAPE VEHICLE DETAILS
        # ══════════════════════════════════════════════════════════════════

        print()
        print("[Cheki] Phase 2: Scraping vehicle details...")

        for index, url in enumerate(
            all_urls,
            start=1
        ):

            print(
                f"[Cheki] "
                f"{index}/{len(all_urls)}: "
                f"{url}"
            )

            status, record = _extract_detail(
                driver,
                url
            )

            if status == "SUCCESS":

                rows_scraped += 1

                if record:
                    records.append(record)

                print(
                    f"SUCCESS | "
                    f"{record.get('make')} | "
                    f"{record.get('model')} | "
                    f"{record.get('year')} | "
                    f"KES {record.get('price_kes')}"
                )

            elif status == "SKIPPED_MIN_YEAR":

                skipped_min_year += 1

                print(
                    "SKIPPED_MIN_YEAR"
                )

            elif status == "PAGE_LOAD_FAILED":

                page_load_failures += 1

                print(
                    "PAGE_LOAD_FAILED"
                )

            elif status == "YEAR_NOT_FOUND":

                year_failures += 1

                print(
                    "YEAR_NOT_FOUND"
                )

            else:

                parse_failures += 1

                print(
                    "PARSE_FAILED"
                )

            # Save full batches.
            if len(records) >= BATCH_SIZE:

                batch = records[:BATCH_SIZE]
                records = records[BATCH_SIZE:]

                saved, db_errors = _save_batch(
                    db,
                    batch
                )

                rows_saved += saved
                database_errors += db_errors

            polite_sleep(0.8, 1.5)

        # ══════════════════════════════════════════════════════════════════
        # FINAL BATCH
        # ══════════════════════════════════════════════════════════════════

        if records:

            saved, db_errors = _save_batch(
                db,
                records
            )

            rows_saved += saved
            database_errors += db_errors

            records = []

    except KeyboardInterrupt:

        print(
            "\n[Cheki] Scrape interrupted by user."
        )

    except Exception as exc:

        log.exception(
            f"[{SITE_NAME}] Fatal scraper error: {exc}"
        )

    finally:

        if driver is not None:

            try:
                driver.quit()
            except Exception:
                pass

        # ══════════════════════════════════════════════════════════════════
        # FINAL ACCOUNTING
        # ══════════════════════════════════════════════════════════════════

        total_outcomes = (
            rows_scraped
            + skipped_min_year
            + page_load_failures
            + year_failures
            + parse_failures
        )

        discovered = len(all_urls)

        print()
        print("=" * 72)
        print("CHEKI SCRAPER SUMMARY")
        print("=" * 72)

        print(
            f"Vehicle URLs discovered:       {discovered}"
        )

        print(
            f"Vehicles scraped successfully: {rows_scraped}"
        )

        print(
            f"Vehicles skipped (MIN_YEAR):   {skipped_min_year}"
        )

        print(
            f"Page-load failures:            {page_load_failures}"
        )

        print(
            f"Year extraction failures:      {year_failures}"
        )

        print(
            f"Parsing failures:              {parse_failures}"
        )

        print(
            f"Database rows saved:           {rows_saved}"
        )

        print(
            f"Database errors:               {database_errors}"
        )

        print(
            f"Scraping outcome count:        {total_outcomes}"
        )

        if total_outcomes == discovered:
            print(
                "Outcome accounting:            PASS"
            )
        else:
            print(
                "Outcome accounting:            WARNING"
            )
            print(
                f"Expected {discovered}, "
                f"accounted for {total_outcomes}."
            )

        print("=" * 72)

        # DBManager.log_run() expects `site`, NOT `source`.
        try:

            db.log_run(
                site=SITE_NAME,
                market="kenya",
                rows_scraped=rows_scraped,
                rows_saved=rows_saved,
                errors=(
                    page_load_failures
                    + year_failures
                    + parse_failures
                    + database_errors
                ),
                started_at=started_at,
                notes=(
                    f"Cheki catalogue URLs: {discovered}; "
                    f"skipped below MIN_YEAR: "
                    f"{skipped_min_year}; "
                    f"database errors: "
                    f"{database_errors}"
                )
            )

        except Exception as exc:

            print(
                f"[Cheki] Could not write scraper log: "
                f"{type(exc).__name__}: {exc}"
            )


if __name__ == "__main__":
    scrape_cheki()