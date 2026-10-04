# BRFSS Interactive Dashboard (2011–Present)

This project is an interactive analytical dashboard built using **Python, Pandas, Plotly Dash**, and **BRFSS (Behavioral Risk Factor Surveillance System)** prevalence data.  

The dashboard allows a user to explore national and state-level health indicators across multiple demographic groups with dynamically generated visualizations.

---

## 🚀 Project Overview

This dashboard was developed collaboratively to recreate a fully functional, multi-panel, CDC-style analytics interface using raw BRFSS prevalence data (2011–present).

The app supports dynamic filtering, question hierarchy navigation, and auto-calculated prevalence estimates with confidence intervals.

Key features include:

### ✔️ Multi-tier Question Selection  
Users can select:
- **Class** (e.g., Demographics, Chronic Health Indicators, Risk Behaviors)  
- **Topic**  
- **Specific Question**

### ✔️ Dynamic Panel Rendering  
Only relevant demographic panels appear based on availability of data:
- Overall  
- Gender  
- Age Group  
- Race  
- Education  
- Income  
- Temporal (Year-by-Year Trend)  
- State/Territory  

Panels without valid BRFSS records **auto-hide** using dynamic tab logic.

### ✔️ Interactive Visualizations  
Each panel includes:
- Bar charts with **confidence intervals (CI)**  
- Yearly trend line plots  
- Top/Bottom-3 filtering options  
- Clean dark theme styling  
- Fully reactive callbacks

### ✔️ Full Preprocessing Pipeline  
The data processing engine performs:
- Type conversions (`Data_value`, `Sample_Size`)  
- Response/Binary category merging  
- Breakout ID harmonization across years  
- Removal of national-level rollup rows  
- Grouped weighted prevalence calculations  
- Confidence interval estimation  

### ✔️ Clean Architecture  
The application code is modular and production-friendly:

## Run locally

1. Download the [BRFSS prevalence CSV from CDC](https://data.cdc.gov/api/views/dttw-5yxu/rows.csv?accessType=DOWNLOAD).
2. Place the file at this location inside the repository, keeping the CDC download filename:

   ```text
   data/raw/Behavioral_Risk_Factor_Surveillance_System__BRFSS__Prevalence_Data__2011_to_present_.csv
   ```

3. From the repository root, install the dependencies and start the dashboard:

   ```powershell
   python -m pip install pandas numpy dash plotly
   python app.py
   ```

4. Open [http://127.0.0.1:8050](http://127.0.0.1:8050) in your browser. Loading the full CSV at startup may take some time.

The app resolves the CSV path relative to `app.py`, so it works without a machine-specific absolute path or a particular terminal working directory. If the file is missing, startup reports the expected location. Raw CSV files are excluded from Git.

See the [official CDC dataset page](https://data.cdc.gov/Behavioral-Risk-Factors/Behavioral-Risk-Factor-Surveillance-System-BRFSS-P/dttw-5yxu) for the data description and column definitions.
