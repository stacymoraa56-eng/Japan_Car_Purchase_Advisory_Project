-- database/schema.sql
-- PostgreSQL Data Warehouse Schema for Japan-Kenya Car Import Advisory Platform

CREATE TABLE IF NOT EXISTS raw_japan_listings (
    id SERIAL PRIMARY KEY,
    listing_url TEXT UNIQUE NOT NULL,
    source_site VARCHAR(50) NOT NULL,
    make VARCHAR(100),
    model VARCHAR(100),
    year INT,
    mileage_km INT,
    engine_cc INT,
    fuel_type VARCHAR(50),
    transmission VARCHAR(50),
    body_type VARCHAR(50),
    color VARCHAR(50),
    price_usd NUMERIC(12,2),
    price_jpy NUMERIC(12,2),
    steering VARCHAR(20),
    drive_type VARCHAR(20),
    doors INT,
    seats INT,
    condition VARCHAR(50),
    location VARCHAR(100),
    description TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_kenya_listings (
    id SERIAL PRIMARY KEY,
    listing_url TEXT UNIQUE NOT NULL,
    source_site VARCHAR(50) NOT NULL,
    make VARCHAR(100),
    model VARCHAR(100),
    year INT,
    mileage_km INT,
    engine_cc INT,
    fuel_type VARCHAR(50),
    transmission VARCHAR(50),
    body_type VARCHAR(50),
    color VARCHAR(50),
    price_kes NUMERIC(14,2),
    condition VARCHAR(50),
    location VARCHAR(100),
    description TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clean_japan_vehicles (
    id SERIAL PRIMARY KEY,
    raw_id INT REFERENCES raw_japan_listings(id) ON DELETE SET NULL,
    source_site VARCHAR(50) NOT NULL,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    year INT NOT NULL,
    age_years INT NOT NULL,
    mileage_km INT NOT NULL,
    engine_cc INT NOT NULL,
    fuel_type VARCHAR(30) NOT NULL,
    transmission VARCHAR(30) NOT NULL,
    body_type VARCHAR(30) NOT NULL,
    fob_price_usd NUMERIC(12,2) NOT NULL,
    cleaned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clean_kenya_vehicles (
    id SERIAL PRIMARY KEY,
    raw_id INT REFERENCES raw_kenya_listings(id) ON DELETE SET NULL,
    source_site VARCHAR(50) NOT NULL,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    year INT NOT NULL,
    age_years INT NOT NULL,
    mileage_km INT NOT NULL,
    engine_cc INT NOT NULL,
    fuel_type VARCHAR(30) NOT NULL,
    transmission VARCHAR(30) NOT NULL,
    body_type VARCHAR(30) NOT NULL,
    yard_price_kes NUMERIC(14,2) NOT NULL,
    condition VARCHAR(30) NOT NULL,
    cleaned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kra_crsp_schedule (
    id SERIAL PRIMARY KEY,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    engine_cc INT NOT NULL,
    crsp_kes NUMERIC(14,2) NOT NULL,
    effective_year INT DEFAULT 2024
);

CREATE TABLE IF NOT EXISTS scraper_logs (
    id SERIAL PRIMARY KEY,
    site_name VARCHAR(50) NOT NULL,
    market VARCHAR(20) NOT NULL,
    rows_scraped INT DEFAULT 0,
    rows_saved INT DEFAULT 0,
    errors_count INT DEFAULT 0,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_clean_jp_mm ON clean_japan_vehicles(make, model, year);
CREATE INDEX IF NOT EXISTS idx_clean_ke_mm ON clean_kenya_vehicles(make, model, year);
CREATE INDEX IF NOT EXISTS idx_crsp_lookup ON kra_crsp_schedule(make, model, engine_cc);