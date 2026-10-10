from scrapers.kenya.jiji_scraper import parse_jiji_detail
from utils.driver_factory import build_driver

URL = (
    "https://jiji.co.ke/"
    "ridgeways/cars/"
    "volkswagen-tiguan-2019-white-"
    "1vM2BKI9KSmS4djznrN3vlYM.html"
)

driver = build_driver(load_images=False)

try:
    vehicle = parse_jiji_detail(driver, URL)

    print("\n" + "=" * 70)
    print("PARSED JIJI VEHICLE")
    print("=" * 70)

    if vehicle:
        for key, value in vehicle.items():
            print(f"{key:20}: {value}")
    else:
        print("❌ Parser returned None")

finally:
    driver.quit()