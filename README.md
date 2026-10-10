#  Japan–Kenya Car Import & Arbitrage Advisory Platform

An end-to-end **data engineering and machine learning capstone project** designed to help prospective car importers evaluate whether importing a vehicle from Japan offers a financial advantage over purchasing a comparable vehicle from the Kenyan local market.

The platform combines web-scraped vehicle listings, PostgreSQL data cleaning pipelines, machine learning price prediction, and an interactive Streamlit dashboard to estimate Japanese export prices, compare Kenyan market prices, and assess potential import savings.

By integrating vehicle pricing data from both markets with an estimated import-cost calculation, the project demonstrates how data engineering and predictive analytics can support more informed vehicle-import decisions.

##  Key Features

###  1. Dual-Market Price Prediction

* Develops separate machine learning models for Japanese export listings and Kenyan local-market listings.
* Predicts Japanese vehicle prices in USD and Kenyan market prices in KES.
* Accounts for differences in market conditions, currencies, and vehicle characteristics.
* Benchmarks multiple regression algorithms to identify the best-performing model for each market.

###  2. PostgreSQL Data Engineering

* Stores and processes scraped vehicle listings using PostgreSQL.
* Implements SQL cleaning scripts to standardize raw data, address data-quality issues, and prepare analytical datasets.
* Applies vehicle eligibility filters and validates key attributes before model training.
* Maintains separate analytical datasets for the Japanese and Kenyan markets.

###  3. Machine Learning Model Benchmarking

Four regression algorithms are evaluated independently for each market:

* Linear Regression
* Ridge Regression
* Random Forest Regressor
* XGBoost Regressor

Models are assessed using the coefficient of determination (R²) and Mean Absolute Percentage Error (MAPE). The selected models are serialized for subsequent use in the advisory application.

###  4. Import Cost and Arbitrage Analysis

The platform is designed to compare the estimated cost of importing a vehicle against its predicted Kenyan market price.

The intended cost calculation incorporates:

* Japanese vehicle purchase price (FOB).
* Estimated freight and insurance.
* Cost, Insurance and Freight (CIF).
* Applicable import duties and statutory levies.
* Excise duty and Value Added Tax (VAT).
* Other applicable clearing, port, registration, and import-related charges.

The comparison helps estimate whether importing a vehicle may be financially attractive. Actual costs depend on vehicle specifications, the applicable valuation method, current tax rules, exchange rates, shipping charges, and other transaction-specific expenses.

###  5. Interactive Streamlit Dashboard

The Streamlit application brings the analytical components together in an interactive interface intended to support:

* Japanese vehicle price prediction.
* Kenyan market price estimation.
* Import-cost estimation.
* Local-market versus import-cost comparison.
* Potential savings assessment.
* 
<img width="934" height="295" alt="Japan_Car_Advisory_Landing_Page" src="https://github.com/user-attachments/assets/80eb2f86-0824-455b-900c-361889e97e11" />
Dashboard outputs are estimates and should not be interpreted as guaranteed market prices, official customs assessments, or confirmed savings.

##  Technology Stack

| Category             | Technologies          |
| -------------------- | --------------------- |
| Programming Language | Python                |
| Web Scraping         | Selenium              |
| Database             | PostgreSQL            |
| Data Manipulation    | Pandas, NumPy         |
| Machine Learning     | Scikit-learn, XGBoost |
| Model Evaluation     | R², MAPE              |
| Model Persistence    | Pickle                |
| Dashboard            | Streamlit             |
| Data Analysis        | Jupyter Notebook      |
| Version Control      | Git, GitHub           |

##  Model Performance

The models were evaluated on held-out test datasets using R² and MAPE.

### Japanese Export Market — FOB Price (USD)

**Dataset:** 599 cleaned records

| Algorithm         |    Test R² |  Test MAPE |
| ----------------- | ---------: | ---------: |
| Linear Regression |     0.4747 |     44.04% |
| Ridge Regression  |     0.6045 |     38.82% |
| Random Forest     | **0.7061** | **24.12%** |
| XGBoost           |     0.6753 |     25.89% |

**Best-performing model: Random Forest Regressor**

The Random Forest model achieved an R² of **0.7061** and a MAPE of **24.12%**, outperforming the other evaluated algorithms on both reported metrics.

### Kenyan Local Market — Yard Price (KES)

**Dataset:** 487 cleaned records

| Algorithm         |    Test R² |  Test MAPE |
| ----------------- | ---------: | ---------: |
| Linear Regression |     0.7001 |     45.23% |
| Ridge Regression  |     0.7650 |     37.18% |
| Random Forest     |     0.7986 | **23.37%** |
| XGBoost           | **0.8321** |     25.02% |

**Selected model: Random Forest Regressor**

Random Forest achieved the lowest MAPE at **23.37%**, while XGBoost achieved the highest R² at **0.8321**.

Random Forest was selected by the training pipeline based on MAPE. This distinction matters because R² measures how well the model explains variation in prices, while MAPE measures average absolute percentage error.

### Interpreting the Results

The results suggest that nonlinear ensemble models capture useful patterns in vehicle prices across both markets.

However, the models still have meaningful prediction errors. Their practical reliability should be assessed using additional validation, error analysis across vehicle categories and price ranges, and comparison against simple baseline models.

MAPE can also be misleading when actual prices are zero or very close to zero, so additional metrics such as MAE and RMSE would strengthen future evaluations.

*Note: These are the reported test-set results from the current training run. They describe performance on the particular test splits used and do not guarantee equivalent accuracy on future listings.*

##  Project Workflow

The project follows an end-to-end data and machine learning workflow:

1. **Data collection:** Extract vehicle listing information from Japanese export and Kenyan local-market sources.
2. **Raw data storage:** Preserve the collected records for traceability and further processing.
3. **Data cleaning:** Use PostgreSQL and SQL scripts to standardize fields, handle data-quality issues, and prepare analytical datasets.
4. **Exploratory data analysis:** Examine price distributions, vehicle characteristics, missing values, and relationships between features and prices.
5. **Feature preparation:** Prepare relevant vehicle attributes for model training.
6. **Model training:** Benchmark four regression algorithms independently for each market.
7. **Model evaluation:** Compare test-set R² and MAPE to select models according to the chosen evaluation criterion.
8. **Model persistence:** Save the selected models for reuse in the application.
9. **Cost estimation:** Estimate the expenses associated with importing a vehicle into Kenya.
10. **Decision support:** Compare estimated import costs against predicted Kenyan market prices through the Streamlit dashboard.

##  Project Structure

The following is the current documented structure of the project:

```text
japan_car_advisory_platform/
│
├── config/
│   └── settings.py
│
├── models/
│   ├── best_japan_model.pkl
│   └── best_kenya_model.pkl
│
├── notebooks/
│   ├── 03_japan_eda_and_model.ipynb
│   └── 04_kenya_eda_and_model.ipynb
│
├── 01_clean_Kenya.sql
├── 02_clean_japan.sql
├── trainModels.py
├── app.py
├── requirements.txt
└── README.md
```

**Note:** This structure reflects the files documented for the current version. Update it as additional modules, tests, documentation, and pipeline components are added.

##  Installation and Setup

### Prerequisites

Ensure the following are installed:

* Python 3.10 or a compatible version supported by the project's dependencies.
* PostgreSQL.
* Git.
* Access to the project's configured database.
* The Python dependencies listed in `requirements.txt`.

### 1. Clone the Repository

Replace the placeholder with the actual GitHub repository URL.

```bash
git clone https://github.com/your-username/japan_car_advisory_platform.git
cd japan_car_advisory_platform
```

### 2. Create and Activate a Virtual Environment

**Windows — PowerShell**

```powershell
python -m venv capstone
.\capstone\Scripts\Activate.ps1
```

If PowerShell blocks script execution, use the activation method permitted by your system's execution policy or activate the environment through the VS Code terminal.

**macOS/Linux**

```bash
python3 -m venv capstone
source capstone/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Ensure your PostgreSQL server is running and that the required raw vehicle tables have been created and populated.

Configure the database connection using the project's settings.

For example, a SQLAlchemy-compatible PostgreSQL connection string has the following format:

```text
postgresql+psycopg://username:password@localhost:5432/database_name
```

Replace the placeholders with your actual database credentials and database name.

**Security recommendation:** Avoid committing database passwords, API keys, or other credentials to GitHub. Store sensitive configuration in environment variables or an untracked `.env` file.

The precise configuration method must match the implementation in `config/settings.py`.

##  Running the Project

Run the following commands from the project root directory, with the virtual environment activated.

### Step 1: Prepare the Analytical Datasets

The SQL cleaning scripts are:

* `02_clean_japan.sql` — Japanese export listings.
* `01_clean_Kenya.sql` — Kenyan local-market listings.

Execute these scripts against the configured PostgreSQL database using your preferred SQL client or a Python database connection.

The scripts must be compatible with the existing raw table names, column types, and database schema.

Before running them, confirm whether they create tables, replace existing tables, or modify existing data. Back up important data before executing destructive operations.

### Step 2: Train and Evaluate the Models

Run:

```bash
python trainModels.py
```

The training pipeline loads the cleaned datasets from PostgreSQL, benchmarks the four regression algorithms for each market, and saves the selected models to the `models/` directory.

The current run reported:

* **Japan:** 599 records; Random Forest selected with an R² of 0.7061 and a MAPE of 24.12%.
* **Kenya:** 487 records; Random Forest selected with an R² of 0.7986 and a MAPE of 23.37%.

The model files generated by the training process are:

```text
models/best_japan_model.pkl
models/best_kenya_model.pkl
```

### Step 3: Launch the Dashboard

Run:

```bash
streamlit run app.py
```

Streamlit should start the local application and display a URL in the terminal. Open that address in your browser to interact with the dashboard.

The application requires the database configuration, dependencies, and trained model artifacts expected by `app.py` to be available.

##  Regulatory Considerations

### Kenya's Vehicle Age Eligibility Rule

The project incorporates Kenya's vehicle-age eligibility requirement as part of its import-advisory logic.

The current cleaning approach references a model-year filter of `year >= 2018`. This is a dataset-specific cutoff, not a permanent definition of the legal rule.

**Important:** The eligible model year depends on the date of import and the applicable regulatory requirements. Confirm the current rules and calculate eligibility relative to the relevant import date rather than treating 2018 as a universal cutoff.

Vehicle eligibility should be validated independently of price prediction.

### Import Taxes and Landed Cost

The import-cost component is intended to account for the Cost, Insurance and Freight (CIF) value and the applicable Kenyan import charges.

A general representation of CIF is:

**CIF = Vehicle FOB Price + Freight + Insurance**

The final import estimate may include:

* Import duty.
* Import Declaration Fee (IDF).
* Railway Development Levy (RDL).
* Excise duty, where applicable.
* Value Added Tax (VAT).
* Port, shipping, clearing, registration, and other applicable charges.

Actual assessment depends on the relevant customs valuation, vehicle classification, engine capacity, fuel type, applicable statutory rates, and current regulations.

**Regulatory disclaimer:** The project is an analytical estimation tool, not an official tax calculator. The rates and formulas used by the implementation should be independently checked against current Kenya Revenue Authority guidance and applicable legislation before being presented as authoritative. A simplified tax formula may not capture every statutory interaction or charge.

##  Limitations and Future Improvements

Potential next steps include:

* **Improve data coverage:** Expand the number of listings and monitor coverage across vehicle makes, models, years, and price categories.
* **Strengthen data quality:** Add automated validation for missing values, duplicate listings, invalid prices, inconsistent units, and currency normalization.
* **Improve model evaluation:** Add MAE, RMSE, cross-validation, baseline comparisons, residual analysis, and evaluation by vehicle segment.
* **Validate real-world performance:** Test predictions on newer listings that were not available during model development.
* **Refine import-cost calculations:** Verify statutory rates, tax bases, valuation rules, exchange rates, and other charges against current authoritative sources.
* **Improve model explainability:** Examine feature importance and use appropriate interpretation techniques to understand the factors driving predictions.
* **Automate data updates:** Schedule repeatable extraction, validation, and database-loading jobs where permitted by source websites.
* **Expand testing:** Add automated tests for data pipelines, database operations, prediction inputs, and import-cost calculations.
* **Improve deployment:** Add clear setup instructions, configuration validation, error handling, and reproducible deployment procedures.

##  Author
Stacy Moraa 

Developed as a data engineering and machine learning capstone project exploring the use of predictive analytics and market comparison to support Japanese vehicle import decisions in Kenya.

The project demonstrates practical application of web scraping, PostgreSQL data processing, exploratory data analysis, regression model benchmarking, and interactive dashboard development.

---

**Disclaimer:** This project is intended for educational and analytical purposes. Predicted prices and estimated import costs are not guarantees of market value, profitability, or official customs assessments. Verify vehicle condition, eligibility, taxes, shipping costs, and other expenses before making an import decision.
