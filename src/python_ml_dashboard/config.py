# src/python_ml_dashboard/config.py
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- API Keys ---
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# --- Location Settings ---
# For Mannheim, Germany
LATITUDE = 49.4875
LONGITUDE = 8.4660

# --- User Preferences (Initial Hardcoded Values) ---
WORKING_HOURS_START = 8  # 8 AM
WORKING_HOURS_END = 18 # 6 PM

EV_CHARGE_TARGET_SOC = 80 # % State of Charge (not used in current basic model, for future)
EV_BATTERY_CAPACITY_KWH = 70 # Example: Tesla Model 3 Long Range (not used in current basic model, for future)
EV_CHARGING_POWER_KW = float(os.getenv("EV_CHARGING_POWER_KW", "11.0")) # Example: AC charging power

DISHWASHER_POWER_KW = 2.0 # Example average power
WASHING_MACHINE_POWER_KW = 2.5 # Example average power

# --- Data Paths ---
# Use absolute path to ensure consistency regardless of where script is run
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')

# --- SMARD API Endpoints (Public data) ---
SMARD_BASE_URL = "https://www.smard.de/app/chart_data"
SMARD_PRICE_FILTER = "1001" # Day-ahead auction price
SMARD_REGION = "DE" # Germany
SMARD_RESOLUTION = "hour" # Hourly data