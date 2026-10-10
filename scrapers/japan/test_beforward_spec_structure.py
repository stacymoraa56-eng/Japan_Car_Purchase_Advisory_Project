from bs4 import BeautifulSoup

from utils.driver_factory import build_driver
from utils.scraping_helpers import safe_get


URL = "https://www.beforward.jp/bmw/mini/ce798690/id/16684031/"


driver = build_driver(load_images=False)

try:
    print("=" * 80)
    print("BE FORWARD SPECIFICATION HTML TEST")
    print("=" * 80)

    safe_get(driver, URL)

    soup = BeautifulSoup(driver.page_source, "lxml")

    table = soup.select_one("table.specification")

    if not table:
        print("\n❌ Specification table not found.")
    else:
        print("\n✅ Specification table found.\n")

        rows = table.find_all("tr")

        print(f"Number of rows: {len(rows)}\n")

        for row_number, row in enumerate(rows, start=1):
            print("-" * 80)
            print(f"ROW {row_number}")

            cells = row.find_all(["th", "td"])

            print(f"Number of cells: {len(cells)}")

            for cell_number, cell in enumerate(cells, start=1):
                print(
                    f"CELL {cell_number}: "
                    f"{cell.get_text(' ', strip=True)!r}"
                )

finally:
    driver.quit()