# src/python_ml_dashboard/config.py
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- API Keys ---
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
# SMARD_CLIENT_ID = os.getenv("SMARD_CLIENT_ID")
# SMARD_CLIENT_SECRET = os.getenv("SMARD_CLIENT_SECRET")
# SOLAR_INVERTER_API_KEY = os.getenv("SOLAR_INVERTER_API_KEY")

# --- Location Settings ---
# For Mannheim, Germany
LATITUDE = 49.4875
LONGITUDE = 8.4660

# --- User Preferences (Initial Hardcoded Values) ---
WORKING_HOURS_START = 8  # 8 AM
WORKING_HOURS_END = 18 # 6 PM

EV_CHARGE_TARGET_SOC = 80 # % State of Charge
EV_BATTERY_CAPACITY_KWH = 70 # Example: Tesla Model 3 Long Range
EV_CHARGING_POWER_KW = 11 # Example: AC charging power

DISHWASHER_POWER_KW = 2.0 # Example average power
WASHING_MACHINE_POWER_KW = 2.5 # Example average power

# --- Data Paths ---
DATA_DIR = "../../data" # Relative to src/python_ml_dashboard

# --- SMARD API Endpoints (Public data, no auth needed for these) ---
# This is based on typical SMARD data structure, adjust if specific endpoint found.
# Actual data often comes from URLs like:
# https://www.smard.de/app/chart_data/1004/DE/index_hour.json
# where 1004 is 'Actual power generation: others', 1001 is 'Day-ahead auction price'.
# We will primarily target the "Day-ahead auction price" (hourly electricity price).
SMARD_BASE_URL = "https://www.smard.de/app/chart_data"
SMARD_PRICE_FILTER = "1001" # Day-ahead auction price
SMARD_REGION = "DE" # Germany
SMARD_RESOLUTION = "hour" # Hourly data