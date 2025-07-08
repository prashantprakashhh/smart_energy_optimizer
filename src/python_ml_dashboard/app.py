import streamlit as st
import pandas as pd
import os
import sys
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim
import json

# --- Path Setup ---
def setup_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    src_path = os.path.join(project_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

setup_path()

# --- Page and Module Imports ---
st.set_page_config(page_title="Predictive AI Energy Optimizer", page_icon="🤖", layout="wide")
import rust_data_collector
# Import the trainer function directly
from python_ml_dashboard.trainer import train_price_prediction_model, MODEL_FILE

# --- Geocoding Function ---
@st.cache_data
def get_coords(location_str):
    """Converts a location string to (latitude, longitude) with error handling."""
    try:
        geolocator = Nominatim(user_agent="smart_energy_optimizer", timeout=10)
        location = geolocator.geocode(location_str)
        if location:
            return location.latitude, location.longitude
    except Exception:
        return None, None
    return None, None

# --- UI Layout ---
st.title("🤖 Predictive AI Energy Optimizer")
st.sidebar.header("Data & AI Control")

# --- Location Input ---
location_input = st.sidebar.text_input("Enter Your Location", "Stuttgart, Germany")
lat, lon = get_coords(location_input)

if not lat or not lon:
    st.sidebar.error("Could not find location. Please try again.")
    st.stop()
st.sidebar.success(f"📍 Location: {location_input}")

# --- Step 1: Data Fetching ---
st.sidebar.markdown("---")
st.sidebar.subheader("Step 1: Get Fresh Data")
if st.sidebar.button("Fetch & Log Data"):
    with st.spinner(f"Fetching data for {location_input}..."):
        try:
            message = rust_data_collector.fetch_and_save_data(lat, lon)
            st.sidebar.success(message)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Data fetch failed: {e}")

# --- Step 2: Plan Optimization ---
st.sidebar.markdown("---")
st.sidebar.subheader("Step 2: Create Energy Plan")
st.sidebar.write("Set appliance run times:")
ev_hours = st.sidebar.slider("EV Charge Duration (h)", 1, 8, 4)
washer_hours = st.sidebar.slider("Washing Machine Duration (h)", 1, 3, 1)
dishwasher_hours = st.sidebar.slider("Dishwasher Duration (h)", 1, 3, 2)

if st.sidebar.button("Create Optimized Plan"):
    with st.spinner("Rust is optimizing your schedule..."):
        try:
            msg = rust_data_collector.create_optimized_plan(ev_hours, washer_hours, dishwasher_hours)
            st.sidebar.success(msg)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Planning failed: {e}")

# --- Step 3: Predictive AI Training ---
st.sidebar.markdown("---")
st.sidebar.subheader("Step 3: Train Predictive AI")
if st.sidebar.button("Train Price Predictor"):
    with st.spinner("Training AI with historical data... please wait."):
        try:
            message, model = train_price_prediction_model()
            st.sidebar.success(message)
            st.session_state['model_ready'] = True
        except Exception as e:
            st.sidebar.error(f"AI Training failed: {e}")


# --- Main Content Area ---
st.header("Your AI-Generated Energy Plan")
plan_file = "data/plan.json"

if not os.path.exists(plan_file):
    st.info("👋 Welcome! Please fetch data and create a plan to begin.")
else:
    try:
        with open(plan_file, 'r') as f:
            plan = json.load(f)
        
        st.subheader("Optimized Appliance Schedule")

        def display_plan(plan_item, name, icon):
            time = pd.to_datetime(plan_item['start_time'], unit='ms', utc=True).tz_convert('Europe/Berlin')
            st.metric(
                label=f"{icon} {name} at {time.strftime('%I:%M %p')}",
                value=f"{plan_item['price']:.3f} €/kWh",
                help=plan_item['reason']
            )

        cols = st.columns(4)
        with cols[0]:
            display_plan(plan['ev_charge'], "EV Charge", "🚗")
        with cols[1]:
            display_plan(plan['washing_machine'], "Washer", "🧺")
        with cols[2]:
            display_plan(plan['dishwasher'], "Dishwasher", "🍽️")
        with cols[3]:
            display_plan(plan['best_time_to_sell'], "Sell Solar", "☀️")

        if 'model_ready' in st.session_state:
            st.success("✅ A predictive price model has been trained and is ready for future use!")

    except Exception as e:
        st.error(f"Error displaying plan: {e}", icon="🔥")