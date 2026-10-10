"""
scrapers/kenya/jiji_scraper.py
───────────────────────────────
Scrapes vehicle listings from Jiji Kenya.

The scraper:
1. Collects vehicle detail URLs from Jiji's /cars pages.
2. Visits each detail page.
3. Extracts structured vehicle specifications.
4. Applies the configured MIN_YEAR filter.
5. Saves eligible records to raw_kenya_listings.
"""

import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from bs4 import BeautifulSoup

from config.settings import MAX_PAGES, MIN_YEAR
from utils.driver_factory import build_driver
from utils.scraping_helpers import safe_get, polite_sleep
from utils.logger import get_logger
from database.db_manager import DBManager


log = get_logger(__name__)

SITE_NAME = "jiji_kenya"
BASE_URL = "https://jiji.co.ke"
LISTING_URL = f"{BASE_URL}/cars"

BATCH_SIZE = 25


# ─────────────────────────────────────────────
# Generic helpers
# ─────────────────────────────────────────────

def clean_text(value: Optional[str]) -> Optional[str]:
    """Normalize whitespace and return None for empty values."""
    if value is None:
        return None

    value = re.sub(r"\s+", " ", value).strip()

    return value if value else None


def normalize_url(href: str) -> Optional[str]:
    """
    Convert a Jiji href into a canonical absolute listing URL.

    Current Jiji vehicle URLs look like:
        /kilimani/cars/toyota-...html
    """
    if not href:
        return None

    href = href.strip()

    if href.startswith("/"):
        url = f"{BASE_URL}{href}"
    elif href.startswith("http://") or href.startswith("https://"):
        url = href
    else:
        return None

    url = url.split("?", 1)[0]
    url = url.split("#", 1)[0]

    if not url.endswith(".html"):
        return None

    if "/cars/" not in url:
        return None

    return url


def extract_number(value: Optional[str]) -> Optional[float]:
    """
    Extract the first numeric value from a string.

    Examples:
        '2800 cc' -> 2800
        '61,000 km' -> 61000
        'KSh 6,900,000' -> 6900000
    """
    if not value:
        return None

    match = re.search(r"\d[\d,]*(?:\.\d+)?", value)

    if not match:
        return None

    try:
        return float(match.group(0).replace(",", ""))
    except (TypeError, ValueError):
        return None


def extract_year_from_text(value: Optional[str]) -> Optional[int]:
    """Extract a plausible vehicle manufacture year."""
    if not value:
        return None

    matches = re.findall(r"\b(19\d{2}|20\d{2})\b", value)

    for match in matches:
        year = int(match)

        if 1950 <= year <= datetime.now().year + 1:
            return year

    return None


def extract_price(text: str) -> Optional[float]:
    """Extract a KSh vehicle price from page text."""
    if not text:
        return None

    patterns = [
        r"KSh\s*([\d,\s]+)",
        r"KES\s*([\d,\s]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            raw_value = match.group(1).replace(",", "").replace(" ", "")

            try:
                return float(raw_value)
            except ValueError:
                continue

    return None


# ─────────────────────────────────────────────
# Structured specification extraction
# ─────────────────────────────────────────────

SPEC_LABELS = {
    "make": "make",
    "model": "model",
    "year of manufacture": "year",
    "condition": "condition",
    "location": "location",
    "fuel": "fuel_type",
    "body": "body_type",
    "mileage": "mileage_km",
    "engine": "engine_cc",
    "engine size": "engine_cc",
    "gearbox": "transmission",
    "transmission": "transmission",
    "drivetrain": "drive_type",
    "color": "color",
}


def extract_structured_specs(
    soup: BeautifulSoup,
) -> Dict[str, str]:
    """
    Extract Jiji specification values.

    Strategy:
    1. Look for current Jiji attribute containers.
    2. Fall back to label/value relationships in the DOM.
    3. Preserve raw text rather than guessing values.
    """
    specs: Dict[str, str] = {}

    # ── Strategy 1: current Jiji attribute structure ──
    for attribute in soup.select("div.b-advert-attribute"):
        key_el = attribute.select_one(".b-advert-attribute__key")
        value_el = attribute.select_one(".b-advert-attribute__value")

        if not key_el or not value_el:
            continue

        key = clean_text(
            key_el.get_text(" ", strip=True)
        )

        value = clean_text(
            value_el.get_text(" ", strip=True)
        )

        if not key or not value:
            continue

        normalized_key = key.lower()

        if normalized_key in SPEC_LABELS:
            field_name = SPEC_LABELS[normalized_key]
            specs[field_name] = value

    # ── Strategy 2: generic label/value DOM fallback ──
    if not specs:
        all_elements = soup.find_all(
            string=re.compile(
                r"^(Make|Model|Year of Manufacture|Body|"
                r"Engine Size|Drivetrain|Color|Fuel|"
                r"Transmission|Gearbox|Mileage)$",
                re.IGNORECASE,
            )
        )

        for label_node in all_elements:
            label = clean_text(str(label_node))

            if not label:
                continue

            normalized_key = label.lower()

            if normalized_key not in SPEC_LABELS:
                continue

            field_name = SPEC_LABELS[normalized_key]

            parent = label_node.parent

            if not parent:
                continue

            candidates = []

            for candidate in parent.find_all_next(
                limit=4
            ):
                candidate_text = clean_text(
                    candidate.get_text(
                        " ",
                        strip=True,
                    )
                )

                if candidate_text:
                    candidates.append(candidate_text)

            for candidate in candidates:
                if candidate.lower() == normalized_key:
                    continue

                specs[field_name] = candidate
                break

    return specs


# ─────────────────────────────────────────────
# Specific field extraction
# ─────────────────────────────────────────────

def extract_description(
    soup: BeautifulSoup,
) -> Optional[str]:
    """
    Extract the seller description from the detail page.
    """
    selectors = [
        ".qa-description-text",
        "[class*='description']",
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if not element:
            continue

        description = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if description:
            return description[:5000]

    # Current Jiji detail pages place the seller description
    # after the store/location information. Look for a likely
    # long text block as a final fallback.
    for element in soup.find_all(
        ["p", "div"],
    ):
        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if len(text) < 80:
            continue

        lowered = text.lower()

        if any(
            marker in lowered
            for marker in [
                "buy and drive",
                "financing",
                "price negotiable",
                "well maintained",
                "good condition",
                "foreign used",
                "locally used",
                "brand new",
            ]
        ):
            return text[:5000]

    return None


def extract_location(
    soup: BeautifulSoup,
    specs: Dict[str, str],
) -> Optional[str]:
    """Extract seller/listing location."""
    location = specs.get("location")

    if location:
        return clean_text(location)

    # Current Jiji pages often expose a location line such as:
    # Nairobi • Kilimani
    for element in soup.find_all(
        string=re.compile(r"•")
    ):
        text = clean_text(str(element))

        if not text:
            continue

        if len(text) > 100:
            continue

        if re.search(
            r"\b(Nairobi|Mombasa|Kisumu|Nakuru|Kiambu|"
            r"Machakos|Nyeri|Meru|Eldoret|Thika|"
            r"Naivasha|Kajiado)\b",
            text,
            re.IGNORECASE,
        ):
            return text

    return None


def extract_mileage(
    specs: Dict[str, str],
    page_text: str,
    description: Optional[str],
) -> Optional[float]:
    """Extract mileage from structured data first, then page text."""
    if specs.get("mileage_km"):
        mileage = extract_number(
            specs["mileage_km"]
        )

        if mileage is not None:
            return mileage

    patterns = [
        r"([\d,]+)\s*km\b",
        r"([\d,]+)\s*kms\b",
        r"mileage\s*[:\-]?\s*([\d,]+)",
    ]

    combined_text = " ".join(
        value
        for value in [
            page_text,
            description,
        ]
        if value
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            combined_text,
            re.IGNORECASE,
        )

        if match:
            try:
                return float(
                    match.group(1).replace(",", "")
                )
            except ValueError:
                continue

    return None


def extract_engine_cc(
    specs: Dict[str, str],
    page_text: str,
    description: Optional[str],
) -> Optional[float]:
    """Extract engine displacement in CC."""
    if specs.get("engine_cc"):
        engine = extract_number(
            specs["engine_cc"]
        )

        if engine is not None:
            return engine

    combined_text = " ".join(
        value
        for value in [
            description,
            page_text,
        ]
        if value
    )

    patterns = [
        r"\b(\d{3,5})\s*cc\b",
        r"\b(\d(?:\.\d)?)\s*(?:l|litre|liter)\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            combined_text,
            re.IGNORECASE,
        )

        if not match:
            continue

        try:
            value = float(match.group(1))

            if "cc" in pattern:
                return value

            return value * 1000

        except ValueError:
            continue

    return None


def extract_fuel(
    specs: Dict[str, str],
    page_text: str,
    description: Optional[str],
) -> Optional[str]:
    """Extract fuel type from structured/page information."""
    fuel = specs.get("fuel_type")

    if fuel:
        return clean_text(fuel)

    combined_text = " ".join(
        value
        for value in [
            page_text,
            description,
        ]
        if value
    ).lower()

    if re.search(r"\bdiesel\b", combined_text):
        return "Diesel"

    if re.search(r"\bpetrol\b|\bgasoline\b", combined_text):
        return "Petrol"

    if re.search(r"\bhybrid\b", combined_text):
        return "Hybrid"

    if re.search(r"\belectric\b|\bev\b", combined_text):
        return "Electric"

    if re.search(r"\bcng\b", combined_text):
        return "CNG"

    return None


def extract_transmission(
    specs: Dict[str, str],
    page_text: str,
    description: Optional[str],
) -> Optional[str]:
    """Extract transmission/gearbox type."""
    transmission = specs.get("transmission")

    if transmission:
        return clean_text(transmission)

    combined_text = " ".join(
        value
        for value in [
            page_text,
            description,
        ]
        if value
    )

    known_types = [
        "Semi-Automatic",
        "Automatic",
        "Manual",
        "CVT",
        "AMT",
    ]

    for transmission_type in known_types:
        if re.search(
            rf"\b{re.escape(transmission_type)}\b",
            combined_text,
            re.IGNORECASE,
        ):
            return transmission_type

    return None


def extract_condition(
    specs: Dict[str, str],
    page_text: str,
) -> Optional[str]:
    """Extract vehicle condition."""
    condition = specs.get("condition")

    if condition:
        return clean_text(condition)

    known_conditions = [
        "Foreign Used",
        "Locally Used",
        "Local Used",
        "Brand New",
        "New",
        "Used",
    ]

    for value in known_conditions:
        if re.search(
            rf"\b{re.escape(value)}\b",
            page_text,
            re.IGNORECASE,
        ):
            return value

    return None


# ─────────────────────────────────────────────
# Detail page parser
# ─────────────────────────────────────────────

def parse_jiji_detail(
    driver,
    url: str,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Parse one Jiji detail page.

    Returns:
        (record, status)

    Status values:
        SUCCESS
        SKIPPED_MIN_YEAR
        PAGE_LOAD_FAILED
        YEAR_NOT_FOUND
        PARSE_FAILED
    """
    try:
        log.info(
            f"Opening Jiji detail page: {url}"
        )

        loaded = safe_get(
            driver,
            url,
            timeout=30,
            retries=2,
        )

        if not loaded:
            return None, "PAGE_LOAD_FAILED"

        polite_sleep(1.0, 1.5)

        soup = BeautifulSoup(
            driver.page_source,
            "lxml",
        )

        page_text = soup.get_text(
            "\n",
            strip=True,
        )

        # ── Title ──────────────────────────────
        title_el = soup.select_one("h1")

        title = (
            clean_text(
                title_el.get_text(
                    " ",
                    strip=True,
                )
            )
            if title_el
            else None
        )

        # ── Structured specifications ──────────
        specs = extract_structured_specs(soup)

        # ── Make / Model ───────────────────────
        make = clean_text(
            specs.get("make")
        )

        model = clean_text(
            specs.get("model")
        )

        # ── Year ───────────────────────────────
        year = None

        if specs.get("year"):
            year = extract_year_from_text(
                specs["year"]
            )

        if year is None:
            year = extract_year_from_text(title)

        if year is None:
            return None, "YEAR_NOT_FOUND"

        if year < MIN_YEAR:
            return None, "SKIPPED_MIN_YEAR"

        # ── Price ──────────────────────────────
        price_kes = extract_price(page_text)

        # ── Description ────────────────────────
        description = extract_description(soup)

        # ── Location ───────────────────────────
        location = extract_location(
            soup,
            specs,
        )

        # ── Mileage ────────────────────────────
        mileage_km = extract_mileage(
            specs,
            page_text,
            description,
        )

        # ── Engine ─────────────────────────────
        engine_cc = extract_engine_cc(
            specs,
            page_text,
            description,
        )

        # ── Fuel ────────────────────────────────
        fuel_type = extract_fuel(
            specs,
            page_text,
            description,
        )

        # ── Transmission ───────────────────────
        transmission = extract_transmission(
            specs,
            page_text,
            description,
        )

        # ── Condition ──────────────────────────
        condition = extract_condition(
            specs,
            page_text,
        )

        # ── Body ───────────────────────────────
        body_type = clean_text(
            specs.get("body_type")
        )

        # ── Color ──────────────────────────────
        color = clean_text(
            specs.get("color")
        )

        # ── Drivetrain ─────────────────────────
        drive_type = clean_text(
            specs.get("drive_type")
        )

        # ── Final record ───────────────────────
        vehicle = {
            "listing_url": url,
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

        return vehicle, "SUCCESS"

    except Exception as exc:
        log.error(
            f"Error parsing Jiji detail page "
            f"{url}: {type(exc).__name__}: {exc}"
        )

        return None, "PARSE_FAILED"


# ─────────────────────────────────────────────
# Listing page parser
# ─────────────────────────────────────────────

def get_jiji_vehicle_urls(
    driver,
) -> List[str]:
    """
    Extract canonical vehicle detail URLs
    from the current Jiji cars listing page.
    """
    soup = BeautifulSoup(
        driver.page_source,
        "lxml",
    )

    urls = []
    seen = set()

    for link in soup.select(
        "a[href*='/cars/']"
    ):
        href = link.get("href")

        url = normalize_url(href)

        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)
        urls.append(url)

    return urls


# ─────────────────────────────────────────────
# Main scraper
# ─────────────────────────────────────────────

def scrape_jiji(
    max_pages: int = MAX_PAGES,
) -> None:
    """
    Run the Jiji Kenya scraper.
    """
    db = DBManager()
    driver = build_driver(
        load_images=False
    )

    started_at = datetime.utcnow()

    all_urls: List[str] = []
    seen_urls = set()

    successful_records = []
    successful_count = 0
    skipped_min_year = 0
    page_load_failures = 0
    year_failures = 0
    parse_failures = 0
    database_errors = 0

    try:
        print()
        print("=" * 70)
        print("JIJI KENYA SCRAPER")
        print("=" * 70)
        print()

        # ──────────────────────────────────────
        # Phase 1: Collect listing URLs
        # ──────────────────────────────────────

        for page_num in range(
            1,
            max_pages + 1,
        ):
            page_url = (
                f"{LISTING_URL}"
                f"?page={page_num}"
            )

            print(
                f"[Jiji] Opening listing page "
                f"{page_num}: {page_url}"
            )

            loaded = safe_get(
                driver,
                page_url,
                timeout=30,
                retries=2,
            )

            if not loaded:
                page_load_failures += 1

                print(
                    f"[Jiji] Listing page "
                    f"{page_num} failed to load."
                )

                continue

            polite_sleep(
                1.0,
                2.0,
            )

            page_urls = get_jiji_vehicle_urls(
                driver
            )

            new_urls = []

            for vehicle_url in page_urls:
                if vehicle_url in seen_urls:
                    continue

                seen_urls.add(vehicle_url)
                all_urls.append(vehicle_url)
                new_urls.append(vehicle_url)

            print(
                f"[Jiji] Page {page_num}: "
                f"{len(page_urls)} URLs found | "
                f"{len(new_urls)} new"
            )

            if not page_urls:
                print(
                    "[Jiji] No vehicle URLs found. "
                    "Stopping pagination."
                )
                break

            if page_num > 1 and not new_urls:
                print(
                    "[Jiji] No new vehicle URLs found "
                    "on this page. "
                    "Stopping pagination."
                )
                break

            polite_sleep(
                0.5,
                1.0,
            )

        print()
        print("-" * 70)
        print(
            f"Total unique vehicle URLs discovered: "
            f"{len(all_urls)}"
        )
        print(
            f"Listing-page load failures: "
            f"{page_load_failures}"
        )
        print("-" * 70)
        print()

        # ──────────────────────────────────────
        # Phase 2: Scrape detail pages
        # ──────────────────────────────────────

        for index, vehicle_url in enumerate(
            all_urls,
            start=1,
        ):
            print(
                f"[{index}/{len(all_urls)}] "
                f"Scraping Jiji vehicle"
            )

            vehicle, status = parse_jiji_detail(
                driver,
                vehicle_url,
            )

            if status == "SKIPPED_MIN_YEAR":
                skipped_min_year += 1

                print(
                    "      Skipped: year is below "
                    f"MIN_YEAR ({MIN_YEAR})."
                )

                continue

            if status == "PAGE_LOAD_FAILED":
                print(
                    "      Page-load failure."
                )
                continue

            if status == "YEAR_NOT_FOUND":
                year_failures += 1

                print(
                    "      Year could not be extracted."
                )

                continue

            if status == "PARSE_FAILED":
                parse_failures += 1

                print(
                    "      Parsing failed."
                )

                continue

            if not vehicle:
                parse_failures += 1

                print(
                    "      No vehicle record returned."
                )

                continue

            successful_count += 1
            successful_records.append(vehicle)

            print(
                f"      {vehicle.get('make')} | "
                f"{vehicle.get('model')} | "
                f"{vehicle.get('year')} | "
                f"KES {vehicle.get('price_kes')}"
            )

            # ──────────────────────────────────
            # Batch database insertion
            # ──────────────────────────────────

            if len(successful_records) >= BATCH_SIZE:
                result = db.save_listings(
                    successful_records,
                    market="kenya",
                    source=SITE_NAME,
                )

                inserted = result.get(
                    "inserted",
                    0,
                )

                database_errors += (
                    len(successful_records)
                    - inserted
                )

                successful_records = []

            polite_sleep(
                0.5,
                1.0,
            )

        # ──────────────────────────────────────
        # Save remaining batch
        # ──────────────────────────────────────

        if successful_records:
            result = db.save_listings(
                successful_records,
                market="kenya",
                source=SITE_NAME,
            )

            inserted = result.get(
                "inserted",
                0,
            )

            database_errors += (
                len(successful_records)
                - inserted
            )

            successful_records = []

        # ──────────────────────────────────────
        # Final summary
        # ──────────────────────────────────────

        total_failures = (
            page_load_failures
            + year_failures
            + parse_failures
            + database_errors
        )

        outcome_count = (
            successful_count
            + skipped_min_year
            + year_failures
            + parse_failures
        )

        print()
        print("=" * 70)
        print("JIJI SCRAPE COMPLETE")
        print("=" * 70)
        print(
            f"Pages requested: {max_pages}"
        )
        print(
            f"Vehicle URLs discovered: "
            f"{len(all_urls)}"
        )
        print(
            f"Vehicles scraped successfully: "
            f"{successful_count}"
        )
        print(
            f"Vehicles skipped (MIN_YEAR): "
            f"{skipped_min_year}"
        )
        print(
            f"Page-load failures: "
            f"{page_load_failures}"
        )
        print(
            f"Year extraction failures: "
            f"{year_failures}"
        )
        print(
            f"Parsing failures: "
            f"{parse_failures}"
        )
        print(
            f"Database errors: "
            f"{database_errors}"
        )
        print(
            f"Total scraping failures: "
            f"{total_failures}"
        )
        print(
            f"Outcome count checked: "
            f"{outcome_count}"
        )

        if outcome_count != len(all_urls):
            print(
                "WARNING: Outcome count does not "
                "match discovered URL count."
            )

        print("=" * 70)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

        try:
            db.log_run(
                site=SITE_NAME,
                market="kenya",
                rows_scraped=successful_count,
                rows_saved=successful_count
                - database_errors,
                errors=(
                    page_load_failures
                    + year_failures
                    + parse_failures
                    + database_errors
                ),
                started_at=started_at,
                notes=(
                    f"Pages requested: {max_pages}; "
                    f"URLs discovered: {len(all_urls)}; "
                    f"Skipped MIN_YEAR: "
                    f"{skipped_min_year}; "
                    f"Page failures: "
                    f"{page_load_failures}; "
                    f"Year failures: "
                    f"{year_failures}; "
                    f"Parse failures: "
                    f"{parse_failures}; "
                    f"Database errors: "
                    f"{database_errors}"
                ),
            )
        except Exception as exc:
            log.error(
                f"Failed to log Jiji run: {exc}"
            )


if __name__ == "__main__":
    scrape_jiji()