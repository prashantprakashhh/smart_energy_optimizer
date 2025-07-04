# src/python_ml_dashboard/data_processor.py
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import pytz # For timezone handling

GERMAN_TIMEZONE = pytz.timezone('Europe/Berlin')

def load_smard_prices(filepath: str) -> pd.DataFrame:
    """Loads and processes SMARD electricity price data."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    df = pd.DataFrame(data['data'])
    # SMARD timestamps are in milliseconds, convert to seconds
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df['timestamp'] = df['timestamp'].dt.tz_convert(GERMAN_TIMEZONE)
    df.rename(columns={'value': 'price_eur_mwh'}, inplace=True)
    df.set_index('timestamp', inplace=True)
    df = df.resample('H').mean() # Ensure hourly and fill gaps if any, simple mean
    df['price_eur_kwh'] = df['price_eur_mwh'] / 1000 # Convert EUR/MWh to EUR/kWh
    return df[['price_eur_kwh']]

def load_weather_data(filepath: str) -> pd.DataFrame:
    """Loads and processes OpenWeatherMap weather forecast data."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    # Process hourly forecast
    hourly_df = pd.DataFrame(data['hourly'])
    hourly_df['timestamp'] = pd.to_datetime(hourly_df['dt'], unit='s', utc=True)
    hourly_df['timestamp'] = hourly_df['timestamp'].dt.tz_convert(GERMAN_TIMEZONE)
    hourly_df.set_index('timestamp', inplace=True)

    # Extract relevant weather features
    hourly_df['temperature_c'] = hourly_df['temp']
    hourly_df['humidity'] = hourly_df['humidity']
    hourly_df['cloudiness_percent'] = hourly_df['clouds'].apply(lambda x: x['all'])
    hourly_df['pop'] = hourly_df['pop'] # Probability of precipitation

    # Create a simplified 'solar_potential' heuristic (can be replaced by real data)
    hourly_df['hour_of_day'] = hourly_df.index.hour
    hourly_df['day_period_factor'] = hourly_df['hour_of_day'].apply(
        lambda h: max(0, -0.05 * (h - 12)**2 + 1.0) # Peak at noon, zero at 0/24 (simple parabola)
    )
    hourly_df['solar_potential'] = (100 - hourly_df['cloudiness_percent']) / 100 * hourly_df['day_period_factor']
    hourly_df['solar_potential'] = hourly_df['solar_potential'].clip(0, 1) # Ensure 0-1 range

    return hourly_df[['temperature_c', 'humidity', 'cloudiness_percent', 'pop', 'solar_potential']]

def get_combined_data(data_dir: str) -> pd.DataFrame:
    """Combines electricity prices and weather data."""
    smard_file = os.path.join(data_dir, "smard_prices.json")
    weather_file = os.path.join(data_dir, "weather_data.json")

    prices_df = load_smard_prices(smard_file)
    weather_df = load_weather_data(weather_file)

    # Combine dataframes on their time index
    combined_df = pd.merge(
        prices_df,
        weather_df,
        left_index=True,
        right_index=True,
        how='inner' # Only keep hours where both data sources exist
    )
    return combined_df

if __name__ == "__main__":
    from config import DATA_DIR
    print(f"Attempting to load data from: {DATA_DIR}")
    # Make sure you've run the Rust data collector first to create these files
    # import rust_data_collector # This won't work in __main__ directly, needs sys.path setup
    # rust_data_collector.fetch_and_save_data(DATA_DIR, 49.4875, 8.4660)
    combined_df = get_combined_data(DATA_DIR)
    print("Combined Data Head:")
    print(combined_df.head())
    print("\nCombined Data Info:")
    combined_df.info()