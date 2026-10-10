# scripts/build_unified_dataset.py
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy import create_engine

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from config.settings import DATABASE_URL, DEFAULT_USD_TO_KES

def calculate_comprehensive_import_cost(fob_usd, engine_cc, fuel_type, year, fx_rate=DEFAULT_USD_TO_KES):
    """
    Comprehensive KRA and Logistical Import Cost Calculator 
    matching all project outline specifications (Purchase, Shipping, KRA Taxes, Port, Clearing, NTSA).
    """
    if pd.isna(fob_usd) or pd.isna(engine_cc) or pd.isna(year):
        return np.nan
        
    # 1. Shipping & Insurance (CIF components)
    freight_insurance_usd = 1350.0  # Average RoRo freight + marine insurance from Japan to Mombasa
    cif_usd = fob_usd + freight_insurance_usd
    cif_kes = cif_usd * fx_rate
    
    fuel = str(fuel_type).upper()
    
    # 2. KRA Taxes
    import_duty = cif_kes * 0.35  # 35% standard passenger car import duty
    
    if "ELECTRIC" in fuel or "EV" in fuel:
        excise_rate = 0.10
    elif "DIESEL" in fuel:
        excise_rate = 0.35 if engine_cc > 2500 else 0.25
    else:
        excise_rate = 0.20 if engine_cc <= 1500 else (0.25 if engine_cc <= 3000 else 0.35)
    
    excise_duty = (cif_kes + import_duty) * excise_rate
    vat = (cif_kes + import_duty + excise_duty) * 0.16
    idf = cif_kes * 0.025
    rdl = cif_kes * 0.020
    total_kra_taxes = import_duty + excise_duty + vat + idf + rdl

    # 3. Port & Terminal Charges (Mombasa CFS & Handling)
    port_charges_kes = 95000.0  

    # 4. Clearing & Forwarding Agency Fees
    clearing_fees_kes = 35000.0  

    # 5. NTSA Registration & Compliance Costs (Nairobi / Local delivery)
    ntsa_registration_kes = 12500.0  

    # Total Landed Cost
    total_landed_cost = cif_kes + total_kra_taxes + port_charges_kes + clearing_fees_kes + ntsa_registration_kes

    return total_landed_cost

def get_matching_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None

def build_unified_enriched_dataset():
    engine = create_engine(DATABASE_URL)
    print("Extracting enriched listings from PostgreSQL...")

    df_japan = pd.read_sql("SELECT * FROM raw_japan_listings_enriched;", engine)
    df_kenya = pd.read_sql("SELECT * FROM raw_kenya_listings_enriched;", engine)

    # Safe Vectorized String Normalization
    for df in [df_japan, df_kenya]:
        if 'make' in df.columns:
            df['make'] = df['make'].fillna('').astype(str).str.strip().str.upper()
        if 'model' in df.columns:
            df['model'] = df['model'].fillna('').astype(str).str.strip().str.upper().str.split().str[0]

    price_col = get_matching_column(df_japan, ['fob_price_usd', 'price_usd', 'fob_usd', 'price'])
    cc_col_jp = get_matching_column(df_japan, ['engine_cc', 'cc', 'engine_displacement'])
    year_col_jp = get_matching_column(df_japan, ['year', 'manufacture_year', 'reg_year'])
    fuel_col_jp = get_matching_column(df_japan, ['fuel_type', 'fuel'])

    yard_price_col = get_matching_column(df_kenya, ['yard_price_kes', 'price_kes', 'price', 'yard_price'])
    year_col_ke = get_matching_column(df_kenya, ['year', 'manufacture_year', 'reg_year'])

    # Standardize column references
    df_japan['clean_price'] = df_japan[price_col].fillna(df_japan[price_col].median() if not df_japan[price_col].dropna().empty else 10000)
    df_japan['clean_cc'] = df_japan[cc_col_jp].fillna(2000)
    df_japan['clean_year'] = df_japan[year_col_jp].fillna(2019)
    df_japan['clean_fuel'] = df_japan[fuel_col_jp] if fuel_col_jp else 'PETROL'

    df_kenya['clean_yard_price'] = df_kenya[yard_price_col].fillna(df_kenya[yard_price_col].median() if not df_kenya[yard_price_col].dropna().empty else 3000000)
    df_kenya['clean_year'] = df_kenya[year_col_ke].fillna(2019)

    # Calculate Comprehensive Landed Costs
    print("Computing comprehensive import landed costs...")
    df_japan['calculated_landed_cost_kes'] = df_japan.apply(
        lambda row: calculate_comprehensive_import_cost(
            fob_usd=row['clean_price'],
            engine_cc=row['clean_cc'],
            fuel_type=row['clean_fuel'],
            year=row['clean_year']
        ), axis=1
    )

    # Aggregate Kenyan Yard Prices
    print("Aggregating local Kenyan yard resale prices...")
    df_kenya_grouped = df_kenya.groupby(['make', 'model', 'clean_year'], as_index=False).agg(
        median_local_yard_price_kes=('clean_yard_price', 'median'),
        local_listing_count=('clean_yard_price', 'count')
    ).rename(columns={'clean_year': 'year'})

    df_japan['year'] = df_japan['clean_year']

    # Merge Datasets
    print("Merging datasets...")
    unified_df = pd.merge(
        df_japan,
        df_kenya_grouped,
        on=['make', 'model', 'year'],
        how='inner'
    )

    # Compute Profit & ROI
    unified_df['predicted_profit_kes'] = unified_df['median_local_yard_price_kes'] - unified_df['calculated_landed_cost_kes']
    unified_df['roi_percent'] = (unified_df['predicted_profit_kes'] / unified_df['calculated_landed_cost_kes']) * 100.0

    print(f"✅ Generated enriched unified dataset with {len(unified_df)} comparable rows.")

    if len(unified_df) > 0:
        unified_df.to_sql('unified_arbitrage_enriched', engine, if_exists='replace', index=False)
        print("Successfully saved updated table 'unified_arbitrage_enriched' to PostgreSQL!")

if __name__ == "__main__":
    build_unified_enriched_dataset()