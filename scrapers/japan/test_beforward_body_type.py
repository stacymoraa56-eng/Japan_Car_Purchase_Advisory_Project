from selenium.webdriver.common.by import By

from utils.driver_factory import build_driver
from utils.scraping_helpers import safe_get, wait_for_element


URL = "https://www.beforward.jp/bmw/mini/ce798690/id/16684031/"


def main():
    driver = build_driver(load_images=False)

    try:
        print("=" * 80)
        print("BE FORWARD BODY TYPE DIAGNOSTIC")
        print("=" * 80)

        safe_get(driver, URL)

        wait_for_element(
            driver,
            "body",
            timeout=15
        )

        print("\nSearching for vehicle-type/body-type information...\n")

        # --------------------------------------------------
        # 1. Look for elements containing body-type labels
        # --------------------------------------------------

        keywords = [
            "body type",
            "vehicle type",
            "wagon",
            "hatchback",
            "sedan",
            "suv",
            "mini van",
            "minivan",
            "van",
            "coupe",
            "convertible",
        ]

        elements = driver.find_elements(
            By.XPATH,
            "//*[self::a or self::span or self::td or self::th or self::div or self::li]"
        )

        seen = set()

        for element in elements:

            try:
                text = element.text.strip()

                if not text:
                    continue

                text_lower = text.lower()

                matched_keyword = None

                for keyword in keywords:
                    if keyword in text_lower:
                        matched_keyword = keyword
                        break

                if not matched_keyword:
                    continue

                # Avoid printing enormous repeated page sections.
                if len(text) > 300:
                    continue

                key = (matched_keyword, text)

                if key in seen:
                    continue

                seen.add(key)

                print("-" * 80)
                print(f"KEYWORD : {matched_keyword}")
                print(f"TEXT    : {text}")

                try:
                    print(f"TAG     : {element.tag_name}")
                except Exception:
                    pass

                try:
                    print(f"CLASS   : {element.get_attribute('class')}")
                except Exception:
                    pass

                try:
                    print(f"ID      : {element.get_attribute('id')}")
                except Exception:
                    pass

                try:
                    print(f"HREF    : {element.get_attribute('href')}")
                except Exception:
                    pass

                try:
                    print(f"HTML    : {element.get_attribute('outerHTML')[:1000]}")
                except Exception:
                    pass

            except Exception:
                continue

        # --------------------------------------------------
        # 2. Search links for vehicle-type parameters
        # --------------------------------------------------

        print("\n")
        print("=" * 80)
        print("VEHICLE-TYPE LINKS")
        print("=" * 80)

        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href]"
        )

        seen_links = set()

        for link in links:

            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()

                if not href:
                    continue

                href_lower = href.lower()

                if (
                    "veh_type" in href_lower
                    or "body" in href_lower
                    or "type=" in href_lower
                ):

                    key = (text, href)

                    if key in seen_links:
                        continue

                    seen_links.add(key)

                    print("-" * 80)
                    print(f"TEXT : {text}")
                    print(f"HREF : {href}")

            except Exception:
                continue

        # --------------------------------------------------
        # 3. Search page source for likely vehicle metadata
        # --------------------------------------------------

        print("\n")
        print("=" * 80)
        print("STRUCTURED VEHICLE METADATA")
        print("=" * 80)

        source = driver.page_source

        search_terms = [
            '"bodyType"',
            '"vehicleType"',
            '"category"',
            '"vehicle_type"',
            'veh_type',
            'body_type',
        ]

        for term in search_terms:

            print(f"\nSearching for: {term}")

            position = 0
            found = 0

            while True:

                position = source.find(
                    term,
                    position
                )

                if position == -1:
                    break

                found += 1

                start = max(
                    0,
                    position - 500
                )

                end = min(
                    len(source),
                    position + 1000
                )

                print("-" * 80)
                print(
                    source[start:end]
                    .replace("\n", " ")
                )

                position += len(term)

                # Don't dump the entire page.
                if found >= 5:
                    break

            print(f"Occurrences shown: {found}")

        print("\n")
        print("=" * 80)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 80)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()