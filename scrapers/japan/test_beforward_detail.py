from bs4 import BeautifulSoup

from utils.driver_factory import build_driver
from utils.scraping_helpers import safe_get


URL = "https://www.beforward.jp/bmw/mini/ce798690/id/16684031/"


driver = build_driver(load_images=False)

try:
    print("=" * 80)
    print("BE FORWARD DETAIL PAGE TEST")
    print("=" * 80)

    safe_get(driver, URL)

    print("\nPage title:")
    print(driver.title)

    print("\nCurrent URL:")
    print(driver.current_url)

    soup = BeautifulSoup(driver.page_source, "lxml")

    print("\nPage source length:")
    print(len(driver.page_source))

    print("\nH1:")
    h1 = soup.find("h1")
    print(h1.get_text(" ", strip=True) if h1 else "No H1 found")

    print("\nTables:")
    for table in soup.find_all("table"):
        print("-" * 80)
        print("TABLE CLASS:", table.get("class"))
        print(table.get_text(" ", strip=True)[:2000])

    print("\nPotential vehicle specification text:")

    page_text = soup.get_text("\n", strip=True)

    keywords = [
        "Mileage",
        "Year",
        "Engine",
        "Transmission",
        "Fuel",
        "Steering",
        "Drive",
        "Color",
        "Doors",
        "Seats",
        "Location",
        "Price",
    ]

    for keyword in keywords:
        if keyword.lower() in page_text.lower():
            print(f"✓ Found: {keyword}")
        else:
            print(f"✗ Missing: {keyword}")

finally:
    driver.quit()