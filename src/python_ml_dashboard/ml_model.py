import pandas as pd
import numpy as np

def make_smart_decisions(df, prefs):
    """
    Analyzes the combined data and user preferences to make hourly recommendations.
    This version identifies the absolute best times to charge or sell.
    """
    df_rec = df.copy()
    
    # --- Define Dynamic Thresholds ---
    # Find the absolute cheapest and most expensive hours in the forecast period
    cheapest_hour = df_rec['price_eur_kwh'].idxmin()
    most_expensive_hour = df_rec['price_eur_kwh'].idxmax()

    # --- Initialize Recommendation Columns ---
    df_rec['charge_ev'] = False
    df_rec['run_appliance'] = False
    df_rec['sell_to_grid'] = False
    df_rec['reason'] = 'Standard grid usage.' # Default reason

    # --- Assign Recommendations Based on Optimal Times ---

    # Rule 1: Charge EV at the absolute cheapest time
    if pd.notna(cheapest_hour):
        df_rec.loc[cheapest_hour, 'charge_ev'] = True
        df_rec.loc[cheapest_hour, 'reason'] = f"Best time to charge. Price is lowest at {df_rec.loc[cheapest_hour, 'price_eur_kwh']:.3f} €/kWh."

    # Rule 2: Sell to Grid at the most expensive time, ONLY if there is significant solar
    if pd.notna(most_expensive_hour) and df_rec.loc[most_expensive_hour, 'estimated_solar_generation_kw'] > 1.0:
        df_rec.loc[most_expensive_hour, 'sell_to_grid'] = True
        df_rec.loc[most_expensive_hour, 'reason'] = f"Best time to sell. Price is highest at {df_rec.loc[most_expensive_hour, 'price_eur_kwh']:.3f} €/kWh."

    # Rule 3: Run general appliances when solar is high but it's not the absolute best selling time
    high_solar_hours = df_rec[(df_rec['estimated_solar_generation_kw'] > 1.5) & (df_rec.index != most_expensive_hour)]
    for hour in high_solar_hours.index:
        df_rec.loc[hour, 'run_appliance'] = True
        df_rec.loc[hour, 'reason'] = "Good time for appliances due to high solar generation."
            
    return df_rec