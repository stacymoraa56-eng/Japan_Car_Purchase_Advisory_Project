from scrapers.kenya.jiji_scraper import parse_jiji_detail
from utils.driver_factory import build_driver
from database.db_manager import DBManager


URL = (
    "https://jiji.co.ke/"
    "ridgeways/cars/"
    "volkswagen-tiguan-2019-white-"
    "1vM2BKI9KSmS4djznrN3vlYM.html"
)


driver = build_driver(load_images=False)
db = DBManager()

try:
    print("=" * 70)
    print("JIJI → POSTGRESQL TEST")
    print("=" * 70)

    vehicle = parse_jiji_detail(driver, URL)

    if not vehicle:
        print("❌ Parser returned no vehicle.")
        raise SystemExit(1)

    print("\nParsed vehicle:")
    for key, value in vehicle.items():
        print(f"{key:20}: {value}")

    print("\nSaving to PostgreSQL...")

    result = db.save_listings(
        [vehicle],
        market="kenya",
        source="jiji_kenya",
    )

    print("\nDatabase result:")
    print(result)

    if result.get("inserted", 0) == 1:
        print("\n✅ Jiji vehicle successfully saved to PostgreSQL!")
    else:
        print("\n⚠️ Vehicle was not inserted.")

finally:
    driver.quit()