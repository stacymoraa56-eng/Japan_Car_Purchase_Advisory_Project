-- database/cleaning.sql
-- ELT SQL Pipeline: Cleans raw landing tables and populates production-ready analytics tables

TRUNCATE TABLE clean_japan_vehicles RESTART IDENTITY;

INSERT INTO clean_japan_vehicles (
    raw_id, source_site, make, model, year, age_years,
    mileage_km, engine_cc, fuel_type, transmission, body_type, fob_price_usd
)
SELECT 
    id AS raw_id,
    source_site,
    UPPER(TRIM(make)) AS make,
    UPPER(TRIM(model)) AS model,
    year,
    (EXTRACT(YEAR FROM CURRENT_DATE) - year) AS age_years,
    mileage_km,
    engine_cc,
    CASE 
        WHEN LOWER(fuel_type) LIKE '%petrol%' OR LOWER(fuel_type) LIKE '%gasoline%' THEN 'Petrol'
        WHEN LOWER(fuel_type) LIKE '%diesel%' THEN 'Diesel'
        WHEN LOWER(fuel_type) LIKE '%hybrid%' THEN 'Hybrid'
        WHEN LOWER(fuel_type) LIKE '%electric%' OR LOWER(fuel_type) LIKE '%ev%' THEN 'Electric'
        ELSE 'Petrol'
    END AS fuel_type,
    CASE 
        WHEN LOWER(transmission) LIKE '%auto%' OR LOWER(transmission) LIKE '%cvt%' THEN 'Automatic'
        WHEN LOWER(transmission) LIKE '%manual%' THEN 'Manual'
        ELSE 'Automatic'
    END AS transmission,
    COALESCE(NULLIF(INITCAP(TRIM(body_type)), ''), 'SUV') AS body_type,
    price_usd AS fob_price_usd
FROM raw_japan_listings
WHERE price_usd IS NOT NULL AND price_usd > 500 AND price_usd < 150000
  AND year IS NOT NULL AND year >= (EXTRACT(YEAR FROM CURRENT_DATE) - 8)
  AND engine_cc IS NOT NULL AND engine_cc BETWEEN 600 AND 7000
  AND mileage_km IS NOT NULL AND mileage_km BETWEEN 100 AND 500000;

TRUNCATE TABLE clean_kenya_vehicles RESTART IDENTITY;

INSERT INTO clean_kenya_vehicles (
    raw_id, source_site, make, model, year, age_years,
    mileage_km, engine_cc, fuel_type, transmission, body_type, yard_price_kes, condition
)
SELECT 
    id AS raw_id,
    source_site,
    UPPER(TRIM(make)) AS make,
    UPPER(TRIM(model)) AS model,
    year,
    (EXTRACT(YEAR FROM CURRENT_DATE) - year) AS age_years,
    mileage_km,
    engine_cc,
    CASE 
        WHEN LOWER(fuel_type) LIKE '%petrol%' OR LOWER(fuel_type) LIKE '%gasoline%' THEN 'Petrol'
        WHEN LOWER(fuel_type) LIKE '%diesel%' THEN 'Diesel'
        WHEN LOWER(fuel_type) LIKE '%hybrid%' THEN 'Hybrid'
        WHEN LOWER(fuel_type) LIKE '%electric%' THEN 'Electric'
        ELSE 'Petrol'
    END AS fuel_type,
    CASE 
        WHEN LOWER(transmission) LIKE '%auto%' OR LOWER(transmission) LIKE '%cvt%' THEN 'Automatic'
        WHEN LOWER(transmission) LIKE '%manual%' THEN 'Manual'
        ELSE 'Automatic'
    END AS transmission,
    COALESCE(NULLIF(INITCAP(TRIM(body_type)), ''), 'SUV') AS body_type,
    price_kes AS yard_price_kes,
    CASE 
        WHEN LOWER(condition) LIKE '%foreign%' THEN 'Foreign Used'
        WHEN LOWER(condition) LIKE '%local%' THEN 'Locally Used'
        WHEN LOWER(condition) LIKE '%brand%' OR LOWER(condition) LIKE '%new%' THEN 'Brand New'
        ELSE 'Foreign Used'
    END AS condition
FROM raw_kenya_listings
WHERE price_kes IS NOT NULL AND price_kes > 300000 AND price_kes < 50000000
  AND year IS NOT NULL AND year >= (EXTRACT(YEAR FROM CURRENT_DATE) - 8)
  AND engine_cc IS NOT NULL AND engine_cc BETWEEN 600 AND 7000
  AND mileage_km IS NOT NULL AND mileage_km BETWEEN 100 AND 500000;