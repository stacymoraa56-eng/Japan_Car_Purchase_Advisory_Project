#  Japan Car Import Advisory Platform — Web Scraping Module

## Project Structure
```
japan_car_advisory/
├── config/
│   └── settings.py          # All configuration (DB credentials, URLs, delays)
├── utils/
│   ├── browser.py           # Selenium browser setup (shared by all scrapers)
│   └── db.py                # PostgreSQL connection and insert helpers
├── scrapers/
│   ├── beforward.py         # BE FORWARD scraper (Japan + Kenya listings)
│   ├── sbtjapan.py          # SBT Japan scraper
│   ├── cheki_kenya.py       # Cheki Kenya scraper
│   └── jiji_kenya.py        # Jiji Kenya scraper
├── database/
│   └── schema.sql           # PostgreSQL table definitions
├── data/raw/                # Raw JSON dumps (backup before DB insert)
├── logs/                    # Scrape logs
├── main.py                  # Master runner — runs all scrapers in sequence
└── requirements.txt         # All Python dependencies
```

## Setup Instructions (Step by Step)

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Install ChromeDriver
- Download Chrome browser if you don't have it
- ChromeDriver is auto-managed by `webdriver-manager` (no manual install needed)

### 3. Set up PostgreSQL
- Install PostgreSQL: https://www.postgresql.org/download/
- Create a database called `japan_car_advisory`
- Run `database/schema.sql` to create tables

### 4. Configure your settings
- Open `config/settings.py`
- Fill in your PostgreSQL username and password

### 5. Run the scrapers
```bash
python main.py
```

## What Gets Scraped
| Source         | Market | Data Points |
|----------------|--------|-------------|
| BE FORWARD     | Japan  | Make, Model, Year, Mileage, Engine, Fuel, Transmission, Price (USD), Body Type |
| SBT Japan      | Japan  | Make, Model, Year, Mileage, Engine, Fuel, Transmission, Price (USD), Body Type |
| Cheki Kenya    | Kenya  | Make, Model, Year, Mileage, Fuel, Transmission, Price (KES), Body Type |
| Jiji Kenya     | Kenya  | Make, Model, Year, Mileage, Fuel, Price (KES), Body Type |

## Year Filter
All scrapers filter for **2018 and newer** vehicles only.
