import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# Attempt to import API keys and location from your config file
# This makes the script portable and keeps secrets out of the code.
try:
    from config import OPENWEATHER_API_KEY, LATITUDE, LONGITUDE
except ImportError:
    print("CRITICAL: Could not import from config.py.")
    print("Please create a 'config.py' file in 'src/python_ml_dashboard/' with:")
    print("OPENWEATHER_API_KEY = 'your_key'")
    print("LATITUDE = your_latitude (e.g., 49.4875)")
    print("LONGITUDE = your_longitude (e.g., 8.4660)")
    exit()


# --- Configuration ---
AWATTAR_URL = "https://api.awattar.de/v1/marketdata"
OPENWEATHER_URL = f"https://api.openweathermap.org/data/2.5/forecast?lat={LATITUDE}&lon={LONGITUDE}&appid={OPENWEATHER_API_KEY}&units=metric"
# OUTPUT_CSV_FILE = 'src/python_ml_dashboard/generated_training_data.csv'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV_FILE = os.path.join(SCRIPT_DIR, 'generated_training_data.csv')


def fetch_data():
    """Fetches price data from aWATTar and weather data from OpenWeather."""
    print("Fetching data from APIs...")
    try:
        price_response = requests.get(AWATTAR_URL)
        price_response.raise_for_status()  # Will raise an HTTPError for bad responses
        price_data = price_response.json().get('data')

        weather_response = requests.get(OPENWEATHER_URL)
        weather_response.raise_for_status()
        weather_data = weather_response.json().get('list')

        if not price_data or not weather_data:
            print("Error: API returned empty data.")
            return None, None

        print("✅ Successfully fetched data.")
        return price_data, weather_data
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP error occurred: {http_err}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
    return None, None


def process_data(price_data, weather_data):
    """Processes and merges raw API data into a clean DataFrame."""
    print("Processing raw data...")
    # Process price data (EUR/MWh -> EUR/kWh)
    price_df = pd.DataFrame(price_data)
    price_df['timestamp'] = pd.to_datetime(price_df['start_timestamp'], unit='ms')
    price_df = price_df.set_index('timestamp')
    price_df['price'] = price_df['marketprice'] / 1000.0

    # Process weather data
    weather_list = [{'timestamp': pd.to_datetime(entry['dt'], unit='s'), 'clouds': entry['clouds']['all']} for entry in weather_data]
    weather_df = pd.DataFrame(weather_list).set_index('timestamp')
    # Resample weather to hourly to match price data
    weather_df = weather_df.resample('h').interpolate(method='linear')

    # Combine into a single DataFrame
    df = price_df.join(weather_df, how='inner')

    # Calculate Solar Potential
    df['hour'] = df.index.hour
    # A simple model: potential is 0 at night, max at noon, reduced by clouds
    daylight_factor = np.sin(np.maximum(0, (df['hour'] - 6) * np.pi / 12))
    cloud_factor = (100 - df['clouds']) / 100.0
    df['solar_potential'] = (daylight_factor * cloud_factor).clip(0, 1)

    print("✅ Data processed successfully.")
    return df[['hour', 'price', 'solar_potential']]


# (This is inside generate_dataset.py)

def apply_oracle_logic(df):
    """
    Applies a 'perfect foresight' logic to the full day's data to determine
    the optimal action for each hour. This creates the ground truth for training.
    """
    print("Applying oracle logic to label data...")
    df['action'] = 'Do Nothing'

    # --- 1. SELLING LOGIC: Find the best 2 hours to sell excess solar ---
    # We will lower the required solar potential from 0.6 to 0.4
    sell_candidates = df.sort_values(by='price', ascending=False)
    sell_hours_found = 0
    for index, row in sell_candidates.iterrows():
        # Condition changed from > 0.6 to > 0.4
        if sell_hours_found < 2 and row['solar_potential'] > 0.4:
            df.loc[index, 'action'] = 'Sell to Grid'
            sell_hours_found += 1

    # --- 2. SOLAR USAGE LOGIC: Use "free" solar power first ---
    # We will lower the required solar potential from 0.5 to 0.3
    solar_candidates = df[df['action'] == 'Do Nothing'].sort_values(by='solar_potential', ascending=False)
    if not solar_candidates.empty:
        # Run dishwasher during the best available solar hour
        dishwasher_hour = solar_candidates.index[0]
        # Condition changed from > 0.5 to > 0.3
        if df.loc[dishwasher_hour, 'solar_potential'] > 0.3:
            df.loc[dishwasher_hour, 'action'] = 'Run Dishwasher'

    # --- 3. BUYING LOGIC: Find the cheapest times to run remaining appliances ---
    # (This part remains the same)
    buy_candidates = df[df['action'] == 'Do Nothing'].sort_values(by='price', ascending=True)

    # Assign EV charging to the 4 cheapest available hours
    ev_hours = buy_candidates.head(4).index
    df.loc[ev_hours, 'action'] = 'Charge EV'

    # Update candidates and assign Washing Machine to the next 2 cheapest hours
    buy_candidates = df[df['action'] == 'Do Nothing'].sort_values(by='price', ascending=True)
    washing_hours = buy_candidates.head(2).index
    df.loc[washing_hours, 'action'] = 'Run Washing Machine'

    print("✅ Oracle logic updated and applied.")
    return df


if __name__ == "__main__":
    price_data, weather_data = fetch_data()

    if price_data and weather_data:
        processed_df = process_data(price_data, weather_data)
        final_df = apply_oracle_logic(processed_df.copy())

        # Save to CSV
        print(f"Saving data to {OUTPUT_CSV_FILE}...")
        if os.path.exists(OUTPUT_CSV_FILE):
            # Append to existing file without the header
            final_df.to_csv(OUTPUT_CSV_FILE, mode='a', header=False, index=False)
            print("✅ Appended new data to existing CSV.")
        else:
            # Create a new file with the header
            final_df.to_csv(OUTPUT_CSV_FILE, index=False)
            print("✅ Created new CSV file.")

        print("\n--- 🚀 DATA GENERATION COMPLETE ---")
        print("You can run this script again to add more data to the CSV.")
        print(f"Next, train the model by running: python src/python_ml_dashboard/train_lstm.py")