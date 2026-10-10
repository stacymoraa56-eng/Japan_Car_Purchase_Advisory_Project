DROP TABLE IF EXISTS clean_kenya_listings;

CREATE TABLE clean_kenya_listings AS
SELECT 
    id,
    listing_url,
    UPPER(TRIM(source_site)) AS source_site,
    UPPER(TRIM(make)) AS make,
    UPPER(TRIM(SPLIT_PART(model, ' ', 1))) AS model,
    CAST(year AS INTEGER) AS year,
    -- Safely handle mileage
    CAST(COALESCE(NULLIF(REGEXP_REPLACE(mileage_km::text, '[^0-9]', '', 'g'), ''), '0') AS INTEGER) AS mileage_km,
    -- Safely handle engine_cc
    CAST(COALESCE(NULLIF(REGEXP_REPLACE(engine_cc::text, '[^0-9]', '', 'g'), ''), '0') AS INTEGER) AS engine_cc,
    UPPER(TRIM(fuel_type)) AS fuel_type,
    UPPER(TRIM(transmission)) AS transmission,
    -- Map raw price_kes to clean yard_price_kes safely
    CAST(COALESCE(NULLIF(REGEXP_REPLACE(price_kes::text, '[^0-9.]', '', 'g'), ''), '0') AS NUMERIC) AS yard_price_kes
FROM raw_kenya_listings_enriched
WHERE year >= 2018 
  AND price_kes IS NOT NULL;