
"""
utils/scraping_helpers.py

Common web scraping, parsing, and sleep helpers.
"""

import re
import time
import random
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def polite_sleep(min_s: float = 1.5, max_s: float = 3.5):
    """Sleep for a random amount of time to avoid hammering websites."""
    time.sleep(random.uniform(min_s, max_s))


def safe_get(
    driver,
    url: str,
    timeout: int = 30,
    retries: int = 2,
) -> bool:
    """
    Safely load a URL using Selenium.

    Returns:
        True if the page loaded successfully.
        False if all attempts failed.
    """

    try:
        driver.set_page_load_timeout(timeout)
    except Exception:
        pass

    for attempt in range(1, retries + 1):
        try:
            driver.get(url)

            polite_sleep(1.0, 2.0)

            return True

        except Exception as exc:
            print(
                f"[safe_get] Attempt {attempt}/{retries} failed "
                f"for {url}: {type(exc).__name__}"
            )

            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass

            if attempt < retries:
                time.sleep(2)

    return False


def wait_for_element(
    driver,
    selector: str,
    by=By.CSS_SELECTOR,
    timeout: int = 15,
) -> bool:
    """Wait until an element exists on the page."""

    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return True
    except Exception:
        return False


def safe_find_text(
    driver,
    selector: str,
    by=By.CSS_SELECTOR,
) -> str:
    """Safely retrieve text from an element."""

    try:
        return driver.find_element(by, selector).text.strip()
    except Exception:
        return ""


def scroll_to_bottom(
    driver,
    pause: float = 1.0,
):
    """Scroll to the bottom of the current page."""

    try:
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )
    except Exception:
        pass

    time.sleep(pause)


def extract_price(raw_str: str) -> Optional[float]:
    """Extract a numeric price from a string."""

    if not raw_str:
        return None

    cleaned = re.sub(r"[^\d.]", "", raw_str)

    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def extract_year(raw_str: str) -> Optional[int]:
    """Extract a four-digit vehicle year."""

    if not raw_str:
        return None

    match = re.search(
        r"\b(19\d{2}|20\d{2})\b",
        raw_str,
    )

    return int(match.group(1)) if match else None


def extract_mileage(raw_str: str) -> Optional[int]:
    """Extract mileage as an integer."""

    if not raw_str:
        return None

    match = re.search(
        r"([\d,]+)",
        raw_str,
    )

    if match:
        try:
            return int(
                match.group(1).replace(",", "")
            )
        except ValueError:
            return None

    return None


def clean_engine_cc(raw_str: str) -> Optional[int]:
    """Extract and validate engine displacement in cc."""

    if not raw_str:
        return None

    match = re.search(
        r"([\d,]+)\s*(cc|CC)?",
        raw_str,
    )

    if match:
        try:
            val = int(
                match.group(1).replace(",", "")
            )

            return val if 500 <= val <= 10000 else None

        except ValueError:
            return None

    return None
