# trainModels.py
import os
import joblib
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
import xgboost as xgb
from sklearn.metrics import mean_absolute_percentage_error, r2_score
from config.settings import DATABASE_URL

def benchmark_and_save_models():
    os.makedirs("models", exist_ok=True)
    engine = create_engine(DATABASE_URL)
    
    # Comprehensive framework dictionary to benchmark
    frameworks = {
        "Linear Regression": LinearRegression(),
        "Ridge Regression": Ridge(alpha=1.0),
        "Random Forest": RandomForestRegressor(n_estimators=150, max_depth=12, random_state=42),
        "XGBoost": xgb.XGBRegressor(n_estimators=150, learning_rate=0.05, max_depth=5, random_state=42)
    }

    print("==================================================")
    print("🚗 STARTING MULTI-FRAMEWORK MODEL TRAINING & TESTING")
    print("==================================================")

    # ==========================================
    # PART 1: JAPAN EXPORT MARKET MODEL
    # ==========================================
    print("\n📥 Loading clean Japan listings from PostgreSQL...")
    try:
        df_japan = pd.read_sql("SELECT * FROM clean_japan_listings;", engine)
    except Exception as e:
        print(f"⚠️ Error loading clean_japan_listings: {e}. Ensure SQL cleaning is complete.")
        return

    print(f"📊 Japan dataset loaded: {len(df_japan)} records.")

    jp_features = ['engine_cc', 'year', 'mileage_km']
    jp_cats = ['make', 'model', 'fuel_type', 'transmission', 'source_site']
    
    for col in jp_features:
        df_japan[col] = pd.to_numeric(df_japan[col], errors='coerce').fillna(df_japan[col].median() if not df_japan[col].dropna().empty else 0)

    X_jp_raw = df_japan[jp_cats + jp_features].fillna('UNKNOWN')
    X_jp = pd.get_dummies(X_jp_raw, drop_first=True)
    y_jp = pd.to_numeric(df_japan['fob_price_usd'], errors='coerce').fillna(df_japan['fob_price_usd'].median())

    # Strict Train/Test Split (80% Training, 20% Testing)
    X_train_jp, X_test_jp, y_train_jp, y_test_jp = train_test_split(X_jp, y_jp, test_size=0.2, random_state=42)

    print("\n🚀 Benchmarking Frameworks for Japan FOB Price (USD):")
    best_jp_score = float('inf')
    best_jp_model = None
    best_jp_name = ""

    for name, model in frameworks.items():
        model.fit(X_train_jp, y_train_jp)
        y_pred = model.predict(X_test_jp)
        
        # Evaluate on Testing Data
        mape = mean_absolute_percentage_error(y_test_jp, y_pred) * 100
        r2 = r2_score(y_test_jp, y_pred)
        print(f"   [{name}] ➔ Test MAPE: {mape:.2f}% | Test R²: {r2:.4f}")
        
        if mape < best_jp_score:
            best_jp_score = mape
            best_jp_model = model
            best_jp_name = name

    joblib.dump(best_jp_model, "models/best_japan_model.pkl")
    print(f"🏆 Best Japan Model: {best_jp_name} (MAPE: {best_jp_score:.2f}%) saved to models/best_japan_model.pkl")

    # ==========================================
    # PART 2: KENYA LOCAL YARD MARKET MODEL
    # ==========================================
    print("\n📥 Loading clean Kenya listings from PostgreSQL...")
    try:
        df_kenya = pd.read_sql("SELECT * FROM clean_kenya_listings;", engine)
    except Exception as e:
        print(f"⚠️ Error loading clean_kenya_listings: {e}. Ensure SQL cleaning is complete.")
        return

    print(f"📊 Kenya dataset loaded: {len(df_kenya)} records.")

    ke_features = ['engine_cc', 'year', 'mileage_km']
    ke_cats = ['make', 'model', 'fuel_type', 'transmission', 'source_site']
    
    for col in ke_features:
        df_kenya[col] = pd.to_numeric(df_kenya[col], errors='coerce').fillna(df_kenya[col].median() if not df_kenya[col].dropna().empty else 0)

    X_ke_raw = df_kenya[ke_cats + ke_features].fillna('UNKNOWN')
    X_ke = pd.get_dummies(X_ke_raw, drop_first=True)
    y_ke = pd.to_numeric(df_kenya['yard_price_kes'], errors='coerce').fillna(df_kenya['yard_price_kes'].median())

    # Strict Train/Test Split (80% Training, 20% Testing)
    X_train_ke, X_test_ke, y_train_ke, y_test_ke = train_test_split(X_ke, y_ke, test_size=0.2, random_state=42)

    print("\n🚀 Benchmarking Frameworks for Kenya Local Yard Price (KES):")
    best_ke_score = float('inf')
    best_ke_model = None
    best_ke_name = ""

    for name, model in frameworks.items():
        model.fit(X_train_ke, y_train_ke)
        y_pred = model.predict(X_test_ke)
        
        # Evaluate on Testing Data
        mape = mean_absolute_percentage_error(y_test_ke, y_pred) * 100
        r2 = r2_score(y_test_ke, y_pred)
        print(f"   [{name}] ➔ Test MAPE: {mape:.2f}% | Test R²: {r2:.4f}")
        
        if mape < best_ke_score:
            best_ke_score = mape
            best_ke_model = model
            best_ke_name = name

    joblib.dump(best_ke_model, "models/best_kenya_model.pkl")
    print(f"🏆 Best Kenya Model: {best_ke_name} (MAPE: {best_ke_score:.2f}%) saved to models/best_kenya_model.pkl")
    print("\n==================================================")
    print("✅ Multi-Framework Training & Testing Complete!")
    print("==================================================")

if __name__ == "__main__":
    benchmark_and_save_models()