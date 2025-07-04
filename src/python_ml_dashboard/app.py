# src/python_ml_dashboard/app.py
import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime, timedelta, time
import pytz # For timezone handling

# Add the parent directory to the Python path to import rust_data_collector
# and other modules from smart_energy_optimizer/src/python_ml_dashboard/
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))
# sys.path.insert(0, os.path.join(project_root, 'src', 'rust_data_collector', 'target', 'release')) # Important: Add the Rust build output directory to PYTHONPATH

st.set_page_config(
    page_title="Smart Home Energy Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.write("--- DEBUG INFO ---")
st.write(f"DEBUG: sys.path at start of app.py: {sys.path}")

# Import Rust data collector
try:
    import rust_data_collector
    st.write(f"DEBUG: Successfully imported rust_data_collector. Module path: {rust_data_collector.__file__}")
except ImportError:
    st.error("Rust data collector module not found. Please ensure it's built and accessible.")
    st.info("Run `cargo build --release` in `src/rust_data_collector` and ensure the generated library is in your system's PATH or PYTHONPATH (or copied to site-packages).")
    st.stop() # Stop execution if Rust module isn't available

# Import local Python modules
from python_ml_dashboard.config import (
    LATITUDE, LONGITUDE, DATA_DIR, WORKING_HOURS_START, WORKING_HOURS_END,
    EV_CHARGE_TARGET_SOC, EV_BATTERY_CAPACITY_KWH, EV_CHARGING_POWER_KW,
    DISHWASHER_POWER_KW, WASHING_MACHINE_POWER_KW
)
from python_ml_dashboard.data_processor import get_combined_data, GERMAN_TIMEZONE
from python_ml_dashboard.ml_model import make_smart_decisions, predict_future_energy_profile

# --- Streamlit UI Setup ---
st.set_page_config(
    page_title="Smart Home Energy Optimizer",
    page_icon="⚡",
    layout="wide", # Use wide layout for more space
    initial_sidebar_state="expanded"
)

# Custom CSS for a classic and cool look (as defined in .streamlit/config.toml)
# This just provides some additional styling.
st.markdown(
    """
    <style>
    /* Add any additional CSS overrides here if needed, but config.toml handles main theme */
    </style>
    """,
    unsafe_allow_html=True
)

st.title("⚡ Smart Home Energy Optimizer")
st.markdown("Optimize your home's energy consumption based on real-time electricity prices and solar output.")

# --- Sidebar for User Inputs and Data Fetching ---
st.sidebar.header("Settings & Data Control")

user_location = st.sidebar.text_input("Your Location (e.g., Mannheim, Germany)", "Mannheim, Germany")
st.sidebar.write(f"Using fixed coordinates for {user_location}: Lat {LATITUDE}, Lon {LONGITUDE}")

st.sidebar.subheader("User Preferences")
# Use current values from config as defaults for sliders
working_hours_start_input = st.sidebar.slider("Working Hours Start (24h)", 0, 23, WORKING_HOURS_START)
working_hours_end_input = st.sidebar.slider("Working Hours End (24h)", 0, 23, WORKING_HOURS_END)

ev_charge_power = st.sidebar.slider("EV Charging Power (kW)", 3.0, 22.0, EV_CHARGING_POWER_KW, 0.5)
dishwasher_power = st.sidebar.slider("Dishwasher Power (kW)", 0.5, 3.0, DISHWASHER_POWER_KW, 0.1)
washing_machine_power = st.sidebar.slider("Washing Machine Power (kW)", 0.5, 3.0, WASHING_MACHINE_POWER_KW, 0.1)

user_prefs = {
    "WORKING_HOURS_START": working_hours_start_input,
    "WORKING_HOURS_END": working_hours_end_input,
    "EV_CHARGING_POWER_KW": ev_charge_power,
    "DISHWASHER_POWER_KW": dishwasher_power,
    "WASHING_MACHINE_POWER_KW": washing_machine_power,
    "EV_CHARGE_TARGET_SOC": EV_CHARGE_TARGET_SOC,
    "EV_BATTERY_CAPACITY_KWH": EV_BATTERY_CAPACITY_KWH,
}

# Ensure data directory exists before trying to save
os.makedirs(DATA_DIR, exist_ok=True)

if st.sidebar.button("Fetch Latest Data (via Rust)"):
    with st.spinner("Fetching data from APIs..."):
        try:
            rust_data_collector.fetch_and_save_data(DATA_DIR, LATITUDE, LONGITUDE)
            st.sidebar.success("Data fetched and saved successfully!")
            # Re-run the app to update data
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error fetching data: {e}")
            st.warning("Please ensure your OPENWEATHER_API_KEY is set correctly in the .env file.")
            st.stop()

# --- Main Content Area ---
st.header("Hourly Recommendations")

# Check if data files exist before attempting to load
smard_file_exists = os.path.exists(os.path.join(DATA_DIR, "smard_prices.json"))
weather_file_exists = os.path.exists(os.path.join(DATA_DIR, "weather_data.json"))

if not smard_file_exists or not weather_file_exists:
    st.info("Please click 'Fetch Latest Data' in the sidebar to get started.")
else:
    # Load and process data
    try:
        combined_df = get_combined_data(DATA_DIR)
        st.success(f"Data loaded successfully covering {combined_df.index.min().strftime('%Y-%m-%d %H:%M')} to {combined_df.index.max().strftime('%Y-%m-%d %H:%M')} (Germany/Berlin Time).")

        # Perform ML (placeholder) and decision making
        df_forecast = predict_future_energy_profile(combined_df) # Currently returns input df
        recommendations_df = make_smart_decisions(df_forecast, user_prefs)

        st.subheader("Optimal Usage Schedule")

        # Get current hour recommendation based on German timezone
        now_utc = datetime.utcnow().replace(second=0, microsecond=0)
        now_local = now_utc.astimezone(GERMAN_TIMEZONE)
        
        # Ensure the index is timezone-aware for accurate lookup
        recommendations_df.index = recommendations_df.index.tz_localize(None).tz_localize(GERMAN_TIMEZONE)
        
        # Filter for the current hour
        current_hour_rec = recommendations_df[
            (recommendations_df.index.hour == now_local.hour) &
            (recommendations_df.index.day == now_local.day) &
            (recommendations_df.index.month == now_local.month) &
            (recommendations_df.index.year == now_local.year)
        ]

        if not current_hour_rec.empty:
            current_rec = current_hour_rec.iloc[0]
            st.markdown(f"### Current Hour Recommendation ({now_local.strftime('%Y-%m-%d %H:%M')}):")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(label="Electricity Price (EUR/kWh)", value=f"{current_rec['price_eur_kwh']:.4f} €")
            with col2:
                st.metric(label="Estimated Solar (kW)", value=f"{current_rec['estimated_solar_generation_kw']:.2f} kW")
            with col3:
                st.metric(label="Net Grid Demand (kW)", value=f"{current_rec['net_grid_demand_kw']:.2f} kW")
            with col4:
                st.metric(label="Cloudiness", value=f"{current_rec['cloudiness_percent']:.0f}%")

            st.write("---")
            st.markdown("#### Actions for the current hour:")
            if current_rec['charge_ev']:
                st.success("🚗 Charge EV now!")
            if current_rec['run_dishwasher']:
                st.success("🍽️ Run Dishwasher now!")
            if current_rec['run_washing_machine']:
                st.success("🧺 Run Washing Machine now!")
            if current_rec['sell_to_grid']:
                st.success("💰 Sell excess power to the grid!")
            if not (current_rec['charge_ev'] or current_rec['run_dishwasher'] or current_rec['run_washing_machine'] or current_rec['sell_to_grid']):
                st.info("😴 No specific actions recommended for this hour. Good time for low consumption.")
            if current_rec['reason']:
                st.caption(f"Reason: {current_rec['reason']}")

        else:
            st.warning("No recommendation available for the current hour. Data might be outdated or missing. Try fetching latest data.")

        st.markdown("---")
        st.subheader("Upcoming Hours' Recommendations")

        # Display upcoming 24 hours (starting from next hour)
        upcoming_start_time = now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        upcoming_df = recommendations_df[recommendations_df.index >= upcoming_start_time].head(24)

        if not upcoming_df.empty:
            display_df = upcoming_df[[
                'price_eur_kwh',
                'estimated_solar_generation_kw',
                'net_grid_demand_kw',
                'charge_ev',
                'run_dishwasher',
                'run_washing_machine',
                'sell_to_grid',
                'reason'
            ]].copy()
            display_df.index = display_df.index.strftime('%Y-%m-%d %H:%M')
            display_df.rename(columns={
                'price_eur_kwh': 'Price (€/kWh)',
                'estimated_solar_generation_kw': 'Est. Solar (kW)',
                'net_grid_demand_kw': 'Net Demand (kW)',
                'charge_ev': 'Charge EV',
                'run_dishwasher': 'Run Dishwasher',
                'run_washing_machine': 'Run Washing Machine',
                'sell_to_grid': 'Sell to Grid',
                'reason': 'Reason'
            }, inplace=True)

            def style_boolean(val):
                if val:
                    return 'background-color: #2EC4B6; color: white; font-weight: bold; border-radius: 3px; padding: 2px 5px;'
                return ''

            st.dataframe(display_df.style.applymap(style_boolean, subset=['Charge EV', 'Run Dishwasher', 'Run Washing Machine', 'Sell to Grid']),
                         use_container_width=True)

            st.markdown("---")
            st.subheader("Price & Solar Trend (Last 48 Hours + Forecast)")
            st.line_chart(recommendations_df[['price_eur_kwh', 'estimated_solar_generation_kw']])

            st.markdown("---")
            st.subheader("Raw Data Preview (Last 5 Rows)")
            st.dataframe(combined_df.tail())

    except Exception as e:
        st.error(f"Error processing or displaying data: {e}")
        st.warning("Ensure the Rust data collector successfully fetched data and saved it to the `data/` directory.")
        st.warning("You might need to click 'Fetch Latest Data' in the sidebar.")