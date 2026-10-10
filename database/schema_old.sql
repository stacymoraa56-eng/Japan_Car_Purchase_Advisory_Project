-- PostgreSQL Schema for Japan-Kenya Vehicle Advisory Platform

-- Scraper Audit Log Table
CREATE TABLE IF NOT EXISTS scraper_logs (
    id SERIAL PRIMARY KEY,
    site_name VARCHAR(50),
    market VARCHAR(20),
    rows_scraped INT DEFAULT 0,
    rows_saved INT DEFAULT 0,
    errors INT DEFAULT 0,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cleaned Japan Vehicles Target Table
CREATE TABLE IF NOT EXISTS clean_japan_vehicles (
    id SERIAL PRIMARY KEY,
    source_site VARCHAR(50),
    vin VARCHAR(50),
    make VARCHAR(50),
    model VARCHAR(50),
    year INT,
    engine_cc INT,
    mileage_km INT,
    fob_price_usd NUMERIC(10, 2),
    total_estimated_kes NUMERIC(12, 2),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scraped_kenya_cars (
    id SERIAL PRIMARY KEY,
    source_website VARCHAR(50) DEFAULT 'Cheki/Jiji',
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    year INT NOT NULL,
    engine_cc INT,
    location VARCHAR(50),
    local_resale_price_kes NUMERIC(12, 2),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kra_duty_logs (
    id SERIAL PRIMARY KEY,
    make VARCHAR(50),
    year INT,
    engine_cc INT,
    cif_cost_kes NUMERIC(12, 2),
    calculated_duty_kes NUMERIC(12, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);