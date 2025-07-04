# src/python_ml_dashboard/ml_model.py
import pandas as pd
from datetime import datetime, time
import numpy as np
from typing import Dict, Any

def predict_future_energy_profile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Placeholder: In a real scenario, this would forecast future electricity
    prices, solar generation, and perhaps household demand.
    For now, it simply returns the fetched data.
    """
    return df.copy()

def make_smart_decisions(
    df_forecast: pd.DataFrame,
    user_prefs: Dict[str, Any],
    solar_panel_output_kw_peak: float = 5.0, # Example: 5 kWp solar system capacity
    house_base_consumption_kw: float = 0.3 # Example: constant base load of the house
) -> pd.DataFrame:
    """
    Makes smart recommendations based on forecasted data and user preferences.
    This is currently rule-based.
    """
    recommendations_df = df_forecast.copy()

    # Calculate estimated solar generation (simple heuristic)
    recommendations_df['estimated_solar_generation_kw'] = recommendations_df['solar_potential'] * solar_panel_output_kw_peak

    # Calculate net consumption/production *before* major appliances/EV
    recommendations_df['net_grid_demand_kw'] = (
        house_base_consumption_kw
        - recommendations_df['estimated_solar_generation_kw']
    )

    # Initialize recommendation columns
    recommendations_df['charge_ev'] = False
    recommendations_df['run_dishwasher'] = False
    recommendations_df['run_washing_machine'] = False
    recommendations_df['sell_to_grid'] = False
    recommendations_df['reason'] = ''

    # Get user preferences
    working_hours_start = time(user_prefs['WORKING_HOURS_START'])
    working_hours_end = time(user_prefs['WORKING_HOURS_END'])
    ev_charge_power_kw = user_prefs['EV_CHARGING_POWER_KW']
    dishwasher_power_kw = user_prefs['DISHWASHER_POWER_KW']
    washing_machine_power_kw = user_prefs['WASHING_MACHINE_POWER_KW']

    # Make decisions for each hour
    for index, row in recommendations_df.iterrows():
        current_time = index.time()
        current_price = row['price_eur_kwh']
        solar_available = row['estimated_solar_generation_kw']
        is_working_hours = working_hours_start <= current_time < working_hours_end

        hour_reasons = []
        actions_taken = {} # Track actions for current hour to avoid double-claiming solar

        # --- Priority 1: Maximize Self-Consumption & Smart Selling ---
        # If we have excess solar
        if solar_available > 0.05: # Small threshold to ignore tiny amounts
            # If solar generation exceeds base consumption, consider selling or using for high-load items
            net_after_base = solar_available - house_base_consumption_kw

            # Consider running appliances or EV first with excess solar
            if net_after_base > dishwasher_power_kw * 0.7 and not actions_taken.get('dishwasher'):
                recommendations_df.loc[index, 'run_dishwasher'] = True
                hour_reasons.append(f"Running Dishwasher with excess solar ({net_after_base:.2f}kW available).")
                actions_taken['dishwasher'] = True
                net_after_base -= dishwasher_power_kw

            if net_after_base > washing_machine_power_kw * 0.7 and not actions_taken.get('washing_machine'):
                recommendations_df.loc[index, 'run_washing_machine'] = True
                hour_reasons.append(f"Running Washing Machine with excess solar ({net_after_base:.2f}kW available).")
                actions_taken['washing_machine'] = True
                net_after_base -= washing_machine_power_kw

            if not is_working_hours and net_after_base > ev_charge_power_kw * 0.5 and not actions_taken.get('ev'):
                recommendations_df.loc[index, 'charge_ev'] = True
                hour_reasons.append(f"Charging EV with excess solar ({net_after_base:.2f}kW available).")
                actions_taken['ev'] = True
                net_after_base -= ev_charge_power_kw

            # Sell remaining excess solar if it's significant and price is good
            # Arbitrary threshold for selling price (e.g., above 10% of max price)
            max_price = recommendations_df['price_eur_kwh'].max()
            sell_price_threshold = max_price * 0.1 # Example: only sell if price is > 10% of max observed price
            if net_after_base > 0.1 and current_price >= sell_price_threshold: # Check if there's significant excess
                recommendations_df.loc[index, 'sell_to_grid'] = True
                hour_reasons.append(f"Selling {net_after_base:.2f}kW excess solar at good price ({current_price:.4f} €/kWh).")
            elif net_after_base > 0.1:
                hour_reasons.append(f"Excess solar ({net_after_base:.2f}kW) available, but selling price not optimal.")


        # --- Priority 2: Use Low Grid Price for Appliances/EV (if not using solar) ---
        # Identify cheapest 25% of hours for grid power
        price_quartile_threshold_ev = recommendations_df['price_eur_kwh'].quantile(0.25)
        price_quartile_threshold_appliance = recommendations_df['price_eur_kwh'].quantile(0.15) # Even cheaper for appliances

        # Charge EV if not during working hours AND price is low, AND not already decided to charge with solar
        if not is_working_hours and current_price <= price_quartile_threshold_ev and not actions_taken.get('ev'):
            recommendations_df.loc[index, 'charge_ev'] = True
            hour_reasons.append(f"Charging EV at low grid price ({current_price:.4f} €/kWh).")
            actions_taken['ev'] = True

        # Run Washing Machine if price is very low and not already decided for solar
        if current_price <= price_quartile_threshold_appliance and not actions_taken.get('washing_machine'):
            recommendations_df.loc[index, 'run_washing_machine'] = True
            hour_reasons.append(f"Running Washing Machine at very low grid price ({current_price:.4f} €/kWh).")
            actions_taken['washing_machine'] = True

        # Run Dishwasher if price is very low and not already decided for solar
        if current_price <= price_quartile_threshold_appliance and not actions_taken.get('dishwasher'):
            recommendations_df.loc[index, 'run_dishwasher'] = True
            hour_reasons.append(f"Running Dishwasher at very low grid price ({current_price:.4f} €/kWh).")
            actions_taken['dishwasher'] = True

        # Combine reasons
        recommendations_df.loc[index, 'reason'] = "; ".join(hour_reasons) if hour_reasons else "No specific action recommended."

    return recommendations_df