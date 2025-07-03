# src/python_ml_dashboard/ml_model.py
import pandas as pd
from datetime import datetime, time
import numpy as np
from typing import Dict, Any

# Placeholder for a more complex ML model later
def predict_future_energy_profile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Placeholder: In a real scenario, this would forecast future electricity
    prices, solar generation, and perhaps household demand.
    For now, it uses the fetched data as "future" data.
    """
    # This function simply returns the input DataFrame,
    # treating current/historical fetched data as "forecast" for demo.
    # Future enhancement: train ML models to predict these values for days ahead.
    return df.copy()

def make_smart_decisions(
    df_forecast: pd.DataFrame,
    user_prefs: Dict[str, Any],
    solar_panel_output_kw_peak: float = 5.0, # Example: 5 kWp solar system
    house_base_consumption_kw: float = 0.3 # Example: constant base load
) -> pd.DataFrame:
    """
    Makes smart recommendations based on forecasted data and user preferences.
    This is currently rule-based.
    """
    recommendations_df = df_forecast.copy()

    # Calculate estimated solar generation (simple heuristic)
    # This needs to be replaced by actual solar data or a robust PV model.
    # For now: Solar potential (0-1) * peak capacity.
    recommendations_df['estimated_solar_generation_kw'] = recommendations_df['solar_potential'] * solar_panel_output_kw_peak

    # Calculate net consumption/production
    recommendations_df['net_grid_demand_kw'] = (
        house_base_consumption_kw
        - recommendations_df['estimated_solar_generation_kw']
    )

    # Initialize recommendation columns
    recommendations_df['charge_ev'] = False
    recommendations_df['run_dishwasher'] = False
    recommendations_df['run_washing_machine'] = False
    recommendations_df['sell_to_grid'] = False # True if we have excess power to sell
    recommendations_df['reason'] = ''

    # Get user preferences
    working_hours_start = time(user_prefs['WORKING_HOURS_START'])
    working_hours_end = time(user_prefs['WORKING_HOURS_END'])
    ev_charge_power_kw = user_prefs['EV_CHARGING_POWER_KW']
    dishwasher_power_kw = user_prefs['DISHWASHER_POWER_KW']
    washing_machine_power_kw = user_prefs['WASHING_MACHINE_POWER_KW']

    # Sort by price to prioritize cheapest times
    # Make decisions for each hour
    for index, row in recommendations_df.iterrows():
        current_time = index.time()
        current_price = row['price_eur_kwh']
        net_demand_before_appliances = row['net_grid_demand_kw']
        solar_available = row['estimated_solar_generation_kw']
        is_working_hours = working_hours_start <= current_time < working_hours_end

        hour_reasons = []

        # Decision Logic Priority:
        # 1. Self-consume solar or sell excess if profitable
        # 2. Charge EV during cheapest or excess solar hours (outside working hours)
        # 3. Run appliances during cheapest or excess solar hours

        # --- Self-consumption / Selling to Grid ---
        if solar_available > 0:
            # If we have excess solar, try to use it or sell it
            if net_demand_before_appliances < 0: # We are generating more than base consumption
                recommendations_df.loc[index, 'sell_to_grid'] = True
                hour_reasons.append(f"Excess solar ({solar_available:.2f}kW) available to sell.")
                # Deduct from net_demand if selling
                net_demand_after_selling = net_demand_before_appliances
            else: # Solar is just covering base consumption
                hour_reasons.append(f"Solar ({solar_available:.2f}kW) covering base consumption.")
        
        # --- EV Charging ---
        # Prioritize EV charging when price is low AND not during working hours
        # Or when there's significant excess solar power
        # Simple heuristic: charge if price is in the lowest quartile OR if solar available is high
        price_quartile_threshold = recommendations_df['price_eur_kwh'].quantile(0.25)
        # Assuming we want to charge the EV to a target, this needs state management.
        # For simplicity, let's assume we want to charge the EV when conditions are good.
        
        if not is_working_hours and (current_price <= price_quartile_threshold or solar_available > ev_charge_power_kw * 0.5): # e.g., if solar covers half EV power
            if net_demand_before_appliances - ev_charge_power_kw < 0: # If solar can cover EV charge + base load
                 recommendations_df.loc[index, 'charge_ev'] = True
                 recommendations_df.loc[index, 'sell_to_grid'] = False # Don't sell if charging EV with solar
                 hour_reasons.append(f"Charging EV using solar/cheap power (price: {current_price:.4f} EUR/kWh).")
            elif current_price <= price_quartile_threshold: # Charge purely based on low price
                 recommendations_df.loc[index, 'charge_ev'] = True
                 hour_reasons.append(f"Charging EV at low grid price ({current_price:.4f} EUR/kWh).")


        # --- Appliance Running (Dishwasher, Washing Machine) ---
        # Prioritize when price is very low or when there's excess solar
        appliance_threshold = recommendations_df['price_eur_kwh'].quantile(0.15) # Even lower threshold for appliances
        
        if not recommendations_df.loc[index, 'charge_ev']: # Don't conflict with EV if EV is priority
            if current_price <= appliance_threshold or solar_available > washing_machine_power_kw * 0.7:
                 recommendations_df.loc[index, 'run_washing_machine'] = True
                 hour_reasons.append(f"Running Washing Machine at low price/excess solar.")

            if current_price <= appliance_threshold or solar_available > dishwasher_power_kw * 0.7:
                 recommendations_df.loc[index, 'run_dishwasher'] = True
                 hour_reasons.append(f"Running Dishwasher at low price/excess solar.")

        # Combine reasons
        recommendations_df.loc[index, 'reason'] = "; ".join(hour_reasons)

    return recommendations_df