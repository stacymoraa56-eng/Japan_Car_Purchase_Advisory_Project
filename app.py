import streamlit as st
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Japan-Kenya Car Import Advisory Platform",
    page_icon="🚗",
    layout="wide"
)

# --- MODERN CLEAN STYLING (No harsh dark rectangles) ---
st.markdown("""
    <style>
    .stMetric { background-color: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; color: #0f172a; }
    .advisory-box { padding: 18px; border-radius: 8px; font-weight: bold; text-align: center; font-size: 1.1rem; margin-top: 10px; }
    .profit { background-color: #ecfdf5; color: #065f46; border: 1px solid #10b981; }
    .loss { background-color: #fef2f2; color: #991b1b; border: 1px solid #ef4444; }
    </style>
""", unsafe_allow_html=True)

# --- LOAD TRAINED MODELS ---
@st.cache_resource
def load_models():
    try:
        japan_model = joblib.load("models/best_japan_model.pkl")
        kenya_model = joblib.load("models/best_kenya_model.pkl")
        return japan_model, kenya_model
    except Exception as e:
        st.error(f"Error loading models: {e}. Please ensure trainModels.py has been run successfully.")
        return None, None

japan_model, kenya_model = load_models()

# --- HEADER SECTION ---
st.title("🚗 Japan-Kenya Car Import & Arbitrage Advisory Platform")
st.markdown("Evaluating direct Japanese import economics against local Kenyan yard pricing with automated KRA tax compliance.")
st.markdown("---")

# --- SIDEBAR USER INPUTS ---
st.sidebar.header("🔧 Vehicle Specifications")

make = st.sidebar.selectbox("Make", ["TOYOTA", "NISSAN", "SUBARU", "MAZDA", "HONDA", "MERCEDES-BENZ"])
model = st.sidebar.text_input("Model (e.g., Harrier, Demio, X-Trail)", "HARRIER").upper().strip()
year = st.sidebar.slider("Manufacture Year (Enforces 8-Year Rule)", 2018, 2026, 2021)
mileage_km = st.sidebar.number_input("Mileage (km)", 0, 200000, 45000, step=5000)
engine_cc = st.sidebar.number_input("Engine Capacity (CC)", 800, 4500, 2000, step=100)
fuel_type = st.sidebar.selectbox("Fuel Type", ["PETROL", "DIESEL", "HYBRID"])
transmission = st.sidebar.selectbox("Transmission", ["AUTOMATIC", "MANUAL"])

# --- PREDICTION LOGIC ---
if st.sidebar.button("🚀 Run Arbitrage & Tax Calculation", type="primary"):
    if japan_model is None or kenya_model is None:
        st.error("Models not found. Please verify your model files in the models/ directory.")
    else:
        # Construct input dataframe
        input_data = pd.DataFrame([{
            'make': make,
            'model': model.split()[0],
            'year': year,
            'mileage_km': mileage_km,
            'engine_cc': engine_cc,
            'fuel_type': fuel_type,
            'transmission': transmission,
            'source_site': 'DIRECT_IMPORT'
        }])

        try:
            # Predict Japan FOB Price (USD)
            X_japan_input = pd.get_dummies(input_data[['make', 'model', 'fuel_type', 'transmission', 'source_site']])
            for col in japan_model.feature_names_in_:
                if col not in X_japan_input.columns:
                    X_japan_input[col] = 0
            X_japan_input = X_japan_input[japan_model.feature_names_in_]
            for col in ['engine_cc', 'year', 'mileage_km']:
                X_japan_input[col] = input_data[col].values[0]

            predicted_fob_usd = japan_model.predict(X_japan_input)[0]

            # Predict Kenya Local Yard Price (KES)
            X_kenya_input = pd.get_dummies(input_data[['make', 'model', 'fuel_type', 'transmission', 'source_site']])
            for col in kenya_model.feature_names_in_:
                if col not in X_kenya_input.columns:
                    X_kenya_input[col] = 0
            X_kenya_input = X_kenya_input[kenya_model.feature_names_in_]
            for col in ['engine_cc', 'year', 'mileage_km']:
                X_kenya_input[col] = input_data[col].values[0]

            predicted_yard_kes = kenya_model.predict(X_kenya_input)[0]

            # --- EXACT KRA STATUTORY TAX STRUCTURE & LANDED COST ---
            EXCHANGE_RATE_KES_USD = 130.0
            freight_insurance_usd = 2200.0  # Average shipping & marine insurance to Mombasa
            cif_usd = predicted_fob_usd + freight_insurance_usd
            cif_kes = cif_usd * EXCHANGE_RATE_KES_USD

            # Exact KRA Formula Components
            idf = cif_kes * 0.035          # Import Declaration Fee (3.5%)
            rdl = cif_kes * 0.02           # Railway Development Levy (2%)
            import_duty = cif_kes * 0.25   # Import Duty (25%)
            
            # Excise duty depends on engine size (> 2500cc is typically higher, e.g., 30%, else 20%)
            excise_rate = 0.30 if engine_cc > 2500 else 0.20
            excise_duty = (cif_kes + import_duty) * excise_rate
            
            vat = (cif_kes + import_duty + excise_duty + idf + rdl) * 0.16  # VAT (16%)

            total_tax_kes = idf + rdl + import_duty + excise_duty + vat
            total_landed_cost_kes = cif_kes + total_tax_kes

            predicted_yard_kes_val = max(predicted_yard_kes, 500000)
            arbitrage_diff_kes = predicted_yard_kes_val - total_landed_cost_kes

            # --- DISPLAY RESULTS ---
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("🇯🇵 Direct Import Economics")
                st.metric("Predicted Japan FOB Price", f"${predicted_fob_usd:,.2f}")
                st.metric("Estimated CIF (Mombasa)", f"KSh {cif_kes:,.0f}")
                st.metric("Total KRA Taxes (IDF, RDL, Duty, Excise, VAT)", f"KSh {total_tax_kes:,.0f}")
                st.metric("Total Landed Cost", f"KSh {total_landed_cost_kes:,.0f}")

            with col2:
                st.subheader("🇰🇪 Local Kenyan Market & Spread")
                st.metric("Predicted Local Yard Price", f"KSh {predicted_yard_kes_val:,.0f}")
                st.metric("Estimated Arbitrage Savings", f"KSh {arbitrage_diff_kes:,.0f}")
                st.info("ℹ️ **Compliance Note:** Enforces Kenya's 8-year age rule (2018+ cutoff) and statutory KRA tax brackets.")

            st.markdown("---")
            st.subheader("💡 Advisory Engine Recommendation")

            if arbitrage_diff_kes > 150000:
                st.markdown(f"""
                    <div class="advisory-box profit">
                        ✅ FAVORABLE DIRECT IMPORT ARBITRAGE<br>
                        Importing this vehicle yields an estimated savings of 
                        <b>KSh {arbitrage_diff_kes:,.0f}</b> compared to buying locally.
                    </div>
                """, unsafe_allow_html=True)
            elif arbitrage_diff_kes > 0:
                st.markdown(f"""
                    <div class="advisory-box profit">
                        ⚖️ MODERATE MARGIN<br>
                        Direct import saves approximately <b>KSh {arbitrage_diff_kes:,.0f}</b>. Account for shipping timelines.
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class="advisory-box loss">
                        ⚠️ HIGHER COST TO IMPORT<br>
                        Local yard pricing is more competitive. Buying locally saves an estimated 
                        <b>KSh {abs(arbitrage_diff_kes):,.0f}</b>.
                    </div>
                """, unsafe_allow_html=True)

        except Exception as ex:
            st.error(f"Prediction Pipeline Error: {ex}")
else:
    st.info("👈 Adjust vehicle specifications in the sidebar and click **Run Arbitrage & Tax Calculation**.")