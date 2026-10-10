from scrapers.japan.beforward_scraper import parse_detail_page
from utils.driver_factory import build_driver


URL = "https://www.beforward.jp/bmw/mini/ce798690/id/16684031/"


driver = build_driver(load_images=False)

try:
    print("=" * 80)
    print("BE FORWARD PARSER TEST")
    print("=" * 80)

    record = parse_detail_page(driver, URL)

    if record is None:
        print("\n❌ Parser returned None.")
    else:
        print("\n✅ Parser returned a record!\n")

        for key, value in record.items():
            print(f"{key:15}: {value}")

finally:
    driver.quit()