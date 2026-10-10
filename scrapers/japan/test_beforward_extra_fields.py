from bs4 import BeautifulSoup

from utils.driver_factory import build_driver
from utils.scraping_helpers import safe_get


URL = "https://www.beforward.jp/bmw/mini/ce798690/id/16684031/"


driver = build_driver(load_images=False)

try:
    print("=" * 80)
    print("BE FORWARD EXTRA FIELDS TEST")
    print("=" * 80)

    safe_get(driver, URL)

    soup = BeautifulSoup(driver.page_source, "lxml")

    # ========================================================
    # YEAR
    # ========================================================

    print("\n" + "=" * 80)
    print("YEAR")
    print("=" * 80)

    year_matches = soup.find_all(
        string=lambda text:
        text and "2020/11" in text
    )

    for item in year_matches[:10]:
        parent = item.parent

        print("\nTEXT:", repr(item.strip()))
        print("PARENT:", parent.name)
        print("PARENT CLASS:", parent.get("class"))
        print(
            "PARENT HTML:",
            str(parent)[:1000]
        )

    # ========================================================
    # PRICE
    # ========================================================

    print("\n" + "=" * 80)
    print("PRICE")
    print("=" * 80)

    price_elements = soup.select(
        "table.price-view-table"
    )

    print(
        f"Found {len(price_elements)} "
        f"price-view-table elements."
    )

    for i, element in enumerate(
        price_elements,
        start=1
    ):
        print("\n" + "-" * 80)
        print(f"PRICE TABLE {i}")

        print(
            "TEXT:",
            element.get_text(
                " ",
                strip=True
            )
        )

        print(
            "HTML:",
            str(element)[:3000]
        )

    # ========================================================
    # BODY TYPE / TYPE
    # ========================================================

    print("\n" + "=" * 80)
    print("BODY TYPE / VEHICLE TYPE")
    print("=" * 80)

    body_keywords = [
        "Body Type",
        "Body type",
        "Type",
        "Category",
        "Wagon",
        "Hatchback",
        "Sedan",
        "SUV",
        "Mini",
    ]

    page_text = soup.get_text(
        " ",
        strip=True
    )

    for keyword in body_keywords:

        if keyword.lower() in page_text.lower():

            print(
                f"✓ Found keyword: {keyword}"
            )

            matches = soup.find_all(
                string=lambda text:
                text and keyword.lower()
                in text.lower()
            )

            for match in matches[:5]:

                print(
                    "  TEXT:",
                    repr(match.strip())
                )

                print(
                    "  PARENT:",
                    match.parent.name
                )

                print(
                    "  PARENT CLASS:",
                    match.parent.get("class")
                )

                print(
                    "  HTML:",
                    str(match.parent)[:1000]
                )

finally:
    driver.quit()