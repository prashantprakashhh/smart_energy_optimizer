import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import pytz
from .config import DATA_DIR

GERMAN_TIMEZONE = pytz.timezone('Europe/Berlin')

def get_combined_data():
    """
    Loads, processes, and merges weather and aWATTar price data from JSON files.
    """
    weather_file = os.path.join(DATA_DIR, "openweather_data.json")
    price_file = os.path.join(DATA_DIR, "awattar_price_data.json") # New price file

    # --- Process Weather Data ---
    with open(weather_file, 'r') as f:
        weather_data = json.load(f)
    
    hourly_weather = pd.DataFrame(weather_data.get('hourly', []))
    hourly_weather['timestamp'] = pd.to_datetime(hourly_weather['dt'], unit='s', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
    hourly_weather.set_index('timestamp', inplace=True)
    hourly_weather['weather_condition'] = hourly_weather['weather'].apply(lambda x: x[0]['main'] if x else 'N/A')
    
    max_solar_kw = 5.5
    weather_coeffs = {'Clear': 1.0, 'Clouds': 0.6, 'Rain': 0.3, 'Mist': 0.35, 'Fog': 0.2, 'Snow': 0.25, 'Drizzle': 0.4, 'Thunderstorm': 0.1}
    sunlight_factor = np.sin(np.pi * (hourly_weather.index.hour - 6) / 12).clip(0, 1)
    weather_factor = hourly_weather['weather_condition'].apply(lambda x: weather_coeffs.get(x, 0.5))
    hourly_weather['estimated_solar_generation_kw'] = max_solar_kw * sunlight_factor * weather_factor

    # --- Process aWATTar Price Data ---
    with open(price_file, 'r') as f:
        price_data = json.load(f)

    price_df = pd.DataFrame(price_data.get('data', []))
    price_df['timestamp'] = pd.to_datetime(price_df['start_timestamp'], unit='ms', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
    price_df.set_index('timestamp', inplace=True)
    # Convert price from EUR/MWh to EUR/kWh
    price_df['price_eur_kwh'] = price_df['marketprice'] / 1000.0
    
    # --- Combine DataFrames ---
    combined_df = hourly_weather.join(price_df['price_eur_kwh'], how='left').ffill()

    final_cols = ['temp', 'weather_condition', 'estimated_solar_generation_kw', 'price_eur_kwh']
    return combined_df[final_cols].dropna()