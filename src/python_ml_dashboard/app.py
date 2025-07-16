
# import streamlit as st
# import pandas as pd
# import numpy as np
# import os
# import sys
# import json
# import pytz
# from datetime import datetime
# from geopy.geocoders import Nominatim
# import tensorflow as tf
# import pickle
# from dotenv import load_dotenv

# # --- Load Environment Variables ---
# load_dotenv()
# OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# # --- Path Setup ---
# def setup_path():
#     current_dir = os.path.dirname(os.path.abspath(__file__))
#     project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
#     if project_root not in sys.path:
#         sys.path.insert(0, os.path.join(project_root, 'src'))

# setup_path()
# import rust_data_collector

# # --- Page Configuration and Constants ---
# st.set_page_config(page_title="AI Smart Energy Optimizer", page_icon="💡", layout="wide")
# GERMAN_TIMEZONE = pytz.timezone('Europe/Berlin')
# DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')
# MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lstm_energy_model.h5')
# ENCODER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'label_encoder.pkl')
# SCALER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scaler.pkl')
# SEQUENCE_LENGTH = 24

# # --- Caching & Loading ---
# @st.cache_data
# def get_coords(location_str):
#     try:
#         geolocator = Nominatim(user_agent="smart_energy_optimizer", timeout=10)
#         location = geolocator.geocode(location_str)
#         return (location.latitude, location.longitude) if location else (None, None)
#     except Exception:
#         return None, None

# @st.cache_resource
# def load_ai_model():
#     if not all(os.path.exists(p) for p in [MODEL_PATH, ENCODER_PATH, SCALER_PATH]):
#         return None, None, None
#     try:
#         model = tf.keras.models.load_model(MODEL_PATH)
#         with open(ENCODER_PATH, 'rb') as f: encoder = pickle.load(f)
#         with open(SCALER_PATH, 'rb') as f: scaler = pickle.load(f)
#         return model, encoder, scaler
#     except Exception as e:
#         st.error(f"Error loading AI model: {e}. Please retrain the model.")
#         return None, None, None

# # --- AI Prediction Logic ---
# def generate_ai_predictions(df, model, encoder, scaler):
#     if model is None or len(df) < SEQUENCE_LENGTH:
#         df['recommendation'] = "Not enough data for AI prediction."
#         return df
#     features = ['price_eur_kwh', 'solar_potential']
#     scaled_features = scaler.transform(df[features])
#     sequences = []
#     for i in range(len(scaled_features) - SEQUENCE_LENGTH + 1):
#         sequences.append(scaled_features[i:i + SEQUENCE_LENGTH])
#     if not sequences:
#         df['recommendation'] = "Not enough data to form a sequence."
#         return df
#     predictions_probs = model.predict(np.array(sequences))
#     predicted_indices = np.argmax(predictions_probs, axis=1)
#     predicted_actions = encoder.inverse_transform(predicted_indices)
#     recommendations = ["Awaiting data"] * (SEQUENCE_LENGTH - 1) + list(predicted_actions)
#     df['recommendation'] = recommendations
#     return df

# # --- UI Components ---
# def display_ai_action_plan(df):
#     st.header("⚡ Your AI-Powered Energy Plan")
#     actions = {"Charge EV": ("🚗", "Lowest Price"), "Sell to Grid": ("💰", "Highest Price & Solar"), "Charge Solar": ("☀️", "Best Solar Generation")}
#     action_found = False
#     cols = st.columns(len(actions))
#     col_idx = 0
#     for action, (icon, reason) in actions.items():
#         best_time = pd.NaT
#         value = 0
#         unit = ""
#         if action == "Charge EV":
#             if not df[df['recommendation'] == action].empty:
#                 best_time = df[df['recommendation'] == action]['price_eur_kwh'].idxmin()
#                 value = df.loc[best_time, 'price_eur_kwh']
#                 unit = "€/kWh"
#         elif action == "Sell to Grid":
#             if not df[df['recommendation'] == action].empty:
#                 best_time = df[df['recommendation'] == action]['price_eur_kwh'].idxmax()
#                 value = df.loc[best_time, 'price_eur_kwh']
#                 unit = "€/kWh"
#         elif action == "Charge Solar":
#             if not df[df['recommendation'] == action].empty:
#                 best_time = df[df['recommendation'] == action]['solar_potential'].idxmax()
#                 value = df.loc[best_time, 'solar_potential']
#                 unit = "kW"
#         if pd.notna(best_time):
#             action_found = True
#             with cols[col_idx]:
#                 st.metric(label=f"{icon} {action}", value=f"{value:.3f} {unit}", help=f"Optimal time based on AI analysis: {reason}")
#                 st.write(f"**Best Time: {best_time.strftime('%A, %b %d, %I:%M %p')}**")
#             col_idx += 1
#     if not action_found:
#         st.info("No specific actions recommended by the AI in the current forecast.", icon="🤖")

# # --- Main App ---
# st.title("💡 AI Smart Energy Optimizer")

# # --- Sidebar ---
# with st.sidebar:
#     st.header("Controls")
#     location_input = st.text_input("Enter Your Location", "Mannheim, Germany")
#     lat, lon = get_coords(location_input)
#     if not lat or not lon: st.error("Could not find location."); st.stop()
#     st.success(f"📍 Location: {location_input}")

#     if not OPENWEATHER_API_KEY:
#         st.error("OPENWEATHER_API_KEY not found! Please ensure it is set in your .env file.")
#     elif st.button("🔄 Fetch Fresh Data & Predict"):
#         with st.spinner(f"Fetching data for {location_input}..."):
#             try:
#                 message = rust_data_collector.fetch_and_save_data(lat, lon, DATA_DIR, OPENWEATHER_API_KEY)
#                 st.success(message)
#                 st.rerun() 
#             except Exception as e:
#                 st.error(f"Data fetch failed: {e}")

# # --- Data Loading and Display (MODIFIED) ---
# model, encoder, scaler = load_ai_model()
# weather_file = os.path.join(DATA_DIR, "openweather_data.json")
# price_file = os.path.join(DATA_DIR, "awattar_price_data.json")

# if model is None:
#     st.warning("AI model not found. Please train the model by running `train_lstm.py`.", icon="🤖")
# elif not os.path.exists(price_file) or not os.path.exists(weather_file):
#     st.info("👋 Welcome! Click 'Fetch Fresh Data & Predict' in the sidebar to begin.")
# else:
#     with st.spinner("🤖 AI is analyzing the future..."):
#         # Process Price Data
#         with open(price_file, 'r') as f: price_df = pd.DataFrame(json.load(f)['data'])
#         price_df['timestamp'] = pd.to_datetime(price_df['start_timestamp'], unit='ms', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
#         price_df['price_eur_kwh'] = price_df['marketprice'] / 1000.0
#         price_df = price_df.set_index('timestamp')[['price_eur_kwh']]

#         # MODIFIED: Process the hourly data from the 'hourly' key
#         with open(weather_file, 'r') as f:
#             weather_data = json.load(f)['hourly']
#         weather_df = pd.DataFrame(weather_data)
        
#         weather_df['weather_condition'] = weather_df['weather'].apply(lambda x: x[0]['main'])
#         weather_df['timestamp'] = pd.to_datetime(weather_df['dt'], unit='s', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
#         weather_df = weather_df.set_index('timestamp')[['temp', 'weather_condition']]
        
#         # Combine dataframes
#         combined_df = price_df.join(weather_df, how='inner').ffill().dropna()

#         # Calculate Solar Potential
#         max_solar_kw = 5.5
#         weather_coeffs = {'Clear': 1.0, 'Clouds': 0.6, 'Rain': 0.3, 'Mist': 0.35, 'Fog': 0.2, 'Snow': 0.25, 'Drizzle': 0.4, 'Thunderstorm': 0.1}
#         sunlight_factor = np.sin(np.pi * (combined_df.index.hour - 6) / 12).clip(0, 1)
#         weather_factor = combined_df['weather_condition'].map(weather_coeffs).fillna(0.5)
#         combined_df['solar_potential'] = max_solar_kw * sunlight_factor * weather_factor

#         combined_df = generate_ai_predictions(combined_df, model, encoder, scaler)
    
#     display_ai_action_plan(combined_df)
#     st.header("🗓️ Detailed Forecast & AI Recommendations")
#     display_df = combined_df[['temp', 'weather_condition', 'price_eur_kwh', 'solar_potential', 'recommendation']].copy()
#     display_df.index = display_df.index.strftime('%A, %b %d, %I:%M %p')
#     st.dataframe(display_df.style.highlight_min(subset=['price_eur_kwh'], color='lightgreen').highlight_max(subset=['price_eur_kwh'], color='#ffcccb').format({
#         "temp": "{:.1f}°C", "price_eur_kwh": "{:.3f} €/kWh", "solar_potential": "{:.2f} kW"
#     }))
import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import json
import pytz
from datetime import datetime
from geopy.geocoders import Nominatim
import tensorflow as tf
import pickle
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()
# MODIFIED: Loading the new API key
WEATHERAPI_API_KEY = os.getenv("WEATHERAPI_API_KEY")

# --- Path Setup ---
def setup_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, os.path.join(project_root, 'src'))

setup_path()
import rust_data_collector

# --- Page Configuration and Constants ---
st.set_page_config(page_title="AI Smart Energy Optimizer", page_icon="💡", layout="wide")
GERMAN_TIMEZONE = pytz.timezone('Europe/Berlin')
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lstm_energy_model.h5')
ENCODER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'label_encoder.pkl')
SCALER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scaler.pkl')
SEQUENCE_LENGTH = 24

# --- Caching & Loading ---
@st.cache_data
def get_coords(location_str):
    try:
        geolocator = Nominatim(user_agent="smart_energy_optimizer", timeout=10)
        location = geolocator.geocode(location_str)
        return (location.latitude, location.longitude) if location else (None, None)
    except Exception:
        return None, None

@st.cache_resource
def load_ai_model():
    if not all(os.path.exists(p) for p in [MODEL_PATH, ENCODER_PATH, SCALER_PATH]):
        return None, None, None
    try:
        model = tf.keras.models.load_model(MODEL_PATH)
        with open(ENCODER_PATH, 'rb') as f: encoder = pickle.load(f)
        with open(SCALER_PATH, 'rb') as f: scaler = pickle.load(f)
        return model, encoder, scaler
    except Exception as e:
        st.error(f"Error loading AI model: {e}. Please retrain the model.")
        return None, None, None

# --- AI Prediction Logic ---
def generate_ai_predictions(df, model, encoder, scaler):
    if model is None or len(df) < SEQUENCE_LENGTH:
        df['recommendation'] = "Not enough data for AI prediction."
        return df
    features = ['price_eur_kwh', 'solar_potential']
    scaled_features = scaler.transform(df[features])
    sequences = []
    for i in range(len(scaled_features) - SEQUENCE_LENGTH + 1):
        sequences.append(scaled_features[i:i + SEQUENCE_LENGTH])
    if not sequences:
        df['recommendation'] = "Not enough data to form a sequence."
        return df
    predictions_probs = model.predict(np.array(sequences))
    predicted_indices = np.argmax(predictions_probs, axis=1)
    predicted_actions = encoder.inverse_transform(predicted_indices)
    recommendations = ["Awaiting data"] * (SEQUENCE_LENGTH - 1) + list(predicted_actions)
    df['recommendation'] = recommendations
    return df

# --- UI Components ---
def display_ai_action_plan(df):
    st.header("⚡ Your AI-Powered Energy Plan")
    actions = {"Charge EV": ("🚗", "Lowest Price"), "Sell to Grid": ("💰", "Highest Price & Solar"), "Charge Solar": ("☀️", "Best Solar Generation")}
    action_found = False
    cols = st.columns(len(actions))
    col_idx = 0
    for action, (icon, reason) in actions.items():
        best_time = pd.NaT
        value = 0
        unit = ""
        if not df[df['recommendation'] == action].empty:
            if action == "Charge EV":
                best_time = df[df['recommendation'] == action]['price_eur_kwh'].idxmin()
                value = df.loc[best_time, 'price_eur_kwh']
                unit = "€/kWh"
            elif action == "Sell to Grid":
                best_time = df[df['recommendation'] == action]['price_eur_kwh'].idxmax()
                value = df.loc[best_time, 'price_eur_kwh']
                unit = "€/kWh"
            elif action == "Charge Solar":
                best_time = df[df['recommendation'] == action]['solar_potential'].idxmax()
                value = df.loc[best_time, 'solar_potential']
                unit = "kW"
        
        if pd.notna(best_time):
            action_found = True
            with cols[col_idx]:
                st.metric(label=f"{icon} {action}", value=f"{value:.3f} {unit}", help=f"Optimal time based on AI analysis: {reason}")
                st.write(f"**Best Time: {best_time.strftime('%A, %b %d, %I:%M %p')}**")
            col_idx += 1
            
    if not action_found:
        st.info("No specific actions recommended by the AI in the current forecast.", icon="🤖")

# --- Main App ---
st.title("💡 AI Smart Energy Optimizer")

# --- Sidebar ---
with st.sidebar:
    st.header("Controls")
    location_input = st.text_input("Enter Your Location", "Mannheim, Germany")
    lat, lon = get_coords(location_input)
    if not lat or not lon: st.error("Could not find location."); st.stop()
    st.success(f"📍 Location: {location_input}")

    if not WEATHERAPI_API_KEY:
        st.error("WEATHERAPI_API_KEY not found! Please ensure it is set in your .env file.")
    elif st.button("🔄 Fetch Fresh Data & Predict"):
        with st.spinner(f"Fetching data for {location_input}..."):
            try:
                # MODIFIED: Passing the new API key
                message = rust_data_collector.fetch_and_save_data(lat, lon, DATA_DIR, WEATHERAPI_API_KEY)
                st.success(message)
                st.rerun() 
            except Exception as e:
                st.error(f"Data fetch failed: {e}")

# --- Data Loading and Display (MODIFIED) ---
model, encoder, scaler = load_ai_model()
weather_file = os.path.join(DATA_DIR, "weather_data.json") # Renamed for clarity
price_file = os.path.join(DATA_DIR, "awattar_price_data.json")

if model is None:
    st.warning("AI model not found. Please train the model by running `train_lstm.py`.", icon="🤖")
elif not os.path.exists(price_file) or not os.path.exists(weather_file):
    st.info("👋 Welcome! Click 'Fetch Fresh Data & Predict' in the sidebar to begin.")
else:
    with st.spinner("🤖 AI is analyzing the future..."):
        with open(price_file, 'r') as f: price_df = pd.DataFrame(json.load(f)['data'])
        price_df['timestamp'] = pd.to_datetime(price_df['start_timestamp'], unit='ms', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
        price_df['price_eur_kwh'] = price_df['marketprice'] / 1000.0
        price_df = price_df.set_index('timestamp')[['price_eur_kwh']]

        # MODIFIED: Process data from WeatherAPI.com
        with open(weather_file, 'r') as f:
            # The hourly data is nested inside 'forecast' -> 'forecastday'
            forecast_days = json.load(f)['forecast']['forecastday']
            hourly_data = []
            for day in forecast_days:
                hourly_data.extend(day['hour'])
        
        weather_df = pd.DataFrame(hourly_data)
        
        # Map the new column names to the ones our app expects
        weather_df['temp'] = weather_df['temp_c']
        weather_df['weather_condition'] = weather_df['condition'].apply(lambda x: x['text'])
        weather_df['timestamp'] = pd.to_datetime(weather_df['time_epoch'], unit='s', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
        weather_df = weather_df.set_index('timestamp')[['temp', 'weather_condition']]
        
        combined_df = price_df.join(weather_df, how='inner').ffill().dropna()

        # Translate WeatherAPI conditions to our simplified categories for solar potential
        def map_condition(condition_text):
            condition_text = condition_text.lower()
            if 'sun' in condition_text or 'clear' in condition_text: return 'Clear'
            if 'cloudy' in condition_text or 'overcast' in condition_text: return 'Clouds'
            if 'rain' in condition_text or 'drizzle' in condition_text: return 'Rain'
            if 'snow' in condition_text or 'sleet' in condition_text: return 'Snow'
            if 'mist' in condition_text or 'fog' in condition_text: return 'Mist'
            if 'thunder' in condition_text: return 'Thunderstorm'
            return 'Clouds' # Default to cloudy

        combined_df['weather_condition_simple'] = combined_df['weather_condition'].apply(map_condition)
        
        max_solar_kw = 5.5
        weather_coeffs = {'Clear': 1.0, 'Clouds': 0.6, 'Rain': 0.3, 'Mist': 0.35, 'Fog': 0.2, 'Snow': 0.25, 'Drizzle': 0.4, 'Thunderstorm': 0.1}
        # sunlight_factor = np.sin(np.pi * (combined_df.index.hour - 6) / 12).clip(0, 1)
        sunlight_factor = np.clip(np.sin(np.pi * (combined_df.index.hour - 6) / 12), 0, 1) 
        weather_factor = combined_df['weather_condition_simple'].map(weather_coeffs).fillna(0.5)
        combined_df['solar_potential'] = max_solar_kw * sunlight_factor * weather_factor

        combined_df = generate_ai_predictions(combined_df, model, encoder, scaler)
    
    display_ai_action_plan(combined_df)
    st.header("🗓️ Detailed Forecast & AI Recommendations")
    display_df = combined_df[['temp', 'weather_condition', 'price_eur_kwh', 'solar_potential', 'recommendation']].copy()
    display_df.index = display_df.index.strftime('%A, %b %d, %I:%M %p')
    st.dataframe(display_df.style.highlight_min(subset=['price_eur_kwh'], color='lightgreen').highlight_max(subset=['price_eur_kwh'], color='#ffcccb').format({
        "temp": "{:.1f}°C", "price_eur_kwh": "{:.3f} €/kWh", "solar_potential": "{:.2f} kW"
    }))