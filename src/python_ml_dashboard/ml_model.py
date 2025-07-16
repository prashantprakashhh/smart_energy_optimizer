# import pandas as pd
# import numpy as np

# def make_smart_decisions(df, prefs):
#     """
#     Analyzes the combined data and user preferences to make hourly recommendations.
#     This version identifies the absolute best times to charge or sell.
#     """
#     df_rec = df.copy()
    
#     # --- Define Dynamic Thresholds ---
#     # Find the absolute cheapest and most expensive hours in the forecast period
#     cheapest_hour = df_rec['price_eur_kwh'].idxmin()
#     most_expensive_hour = df_rec['price_eur_kwh'].idxmax()

#     # --- Initialize Recommendation Columns ---
#     df_rec['charge_ev'] = False
#     df_rec['run_appliance'] = False
#     df_rec['sell_to_grid'] = False
#     df_rec['reason'] = 'Standard grid usage.' # Default reason

#     # --- Assign Recommendations Based on Optimal Times ---

#     # Rule 1: Charge EV at the absolute cheapest time
#     if pd.notna(cheapest_hour):
#         df_rec.loc[cheapest_hour, 'charge_ev'] = True
#         df_rec.loc[cheapest_hour, 'reason'] = f"Best time to charge. Price is lowest at {df_rec.loc[cheapest_hour, 'price_eur_kwh']:.3f} €/kWh."

#     # Rule 2: Sell to Grid at the most expensive time, ONLY if there is significant solar
#     if pd.notna(most_expensive_hour) and df_rec.loc[most_expensive_hour, 'estimated_solar_generation_kw'] > 1.0:
#         df_rec.loc[most_expensive_hour, 'sell_to_grid'] = True
#         df_rec.loc[most_expensive_hour, 'reason'] = f"Best time to sell. Price is highest at {df_rec.loc[most_expensive_hour, 'price_eur_kwh']:.3f} €/kWh."

#     # Rule 3: Run general appliances when solar is high but it's not the absolute best selling time
#     high_solar_hours = df_rec[(df_rec['estimated_solar_generation_kw'] > 1.5) & (df_rec.index != most_expensive_hour)]
#     for hour in high_solar_hours.index:
#         df_rec.loc[hour, 'run_appliance'] = True
#         df_rec.loc[hour, 'reason'] = "Good time for appliances due to high solar generation."
            
#     return df_rec
import pandas as pd
import numpy as np
import tensorflow as tf
import pickle

# --- 1. Load the trained model and preprocessors ---
try:
    MODEL = tf.keras.models.load_model('src/python_ml_dashboard/lstm_energy_model.h5')
    with open('src/python_ml_dashboard/label_encoder.pkl', 'rb') as f:
        LABEL_ENCODER = pickle.load(f)
    with open('src/python_ml_dashboard/scaler.pkl', 'rb') as f:
        SCALER = pickle.load(f)
    SEQUENCE_LENGTH = MODEL.input_shape[1] # Get sequence length from model's input shape (e.g., 24)
    print("LSTM model and preprocessors loaded successfully.")
except Exception as e:
    print(f"Error loading model: {e}. Falling back to rule-based system.")
    MODEL = None

# --- Original Rule-Based Function (as a fallback) ---
def get_recommendation_rule_based(hour_data):
    """The original rule-based logic."""
    price = hour_data['price']
    solar = hour_data['solar_potential']
    
    # Define price thresholds based on the entire day's price data
    price_quantile_15 = hour_data['price_quantile_15']
    price_quantile_25 = hour_data['price_quantile_25']

    if solar > 0.7:
        return "Sell to Grid"
    elif solar > 0.5:
        return "Run Dishwasher"
    elif price < price_quantile_15:
        return "Charge EV"
    elif price < price_quantile_25:
        return "Run Washing Machine"
    else:
        return "Do Nothing"

# --- 2. New Function to use the LSTM Model ---
def predict_with_lstm(historical_data, future_data):
    """
    Uses the trained LSTM model to predict actions for the future hours.
    
    :param historical_data: A DataFrame with the last SEQUENCE_LENGTH hours of data.
    :param future_data: A DataFrame with the future hours we want to predict.
    :return: A list of recommended actions.
    """
    if not MODEL:
        # Fallback if model failed to load
        return [get_recommendation_rule_based(row) for _, row in future_data.iterrows()]

    # Scale the features using the same scaler from training
    scaled_features = SCALER.transform(historical_data[['price', 'solar_potential']])
    
    # Reshape into a single sequence sample: (1, SEQUENCE_LENGTH, num_features)
    sequence = np.array([scaled_features])
    
    # Predict the probability of each action
    prediction_probabilities = MODEL.predict(sequence)[0]
    
    # Get the index of the action with the highest probability
    predicted_index = np.argmax(prediction_probabilities)
    
    # Decode the index back to the action name (e.g., "Charge EV")
    predicted_action = LABEL_ENCODER.inverse_transform([predicted_index])[0]
    
    # For this example, we'll apply the same prediction to all future hours.
    # A more advanced implementation would predict one hour at a time in a loop.
    return [predicted_action] * len(future_data)


# --- 3. Main Function (Updated) ---
def predict_future_energy_profile(df, working_hours_start, working_hours_end):
    """
    Processes data and decides whether to use the LSTM model or the rule-based system.
    """
    df_copy = df.copy()
    
    # Calculate price quantiles for the rule-based fallback
    df_copy['price_quantile_15'] = df_copy['price'].quantile(0.15)
    df_copy['price_quantile_25'] = df_copy['price'].quantile(0.25)
    
    # --- Integration Logic ---
    if MODEL and len(df_copy) >= SEQUENCE_LENGTH:
        print("Sufficient data found. Using LSTM model for predictions.")
        # We need historical data to predict the future.
        # We'll use the first `SEQUENCE_LENGTH` rows as our "history" to predict the rest.
        historical_data = df_copy.iloc[:SEQUENCE_LENGTH]
        future_data = df_copy.iloc[SEQUENCE_LENGTH:]
        
        # If there are future hours to predict, use the model
        if not future_data.empty:
            # For simplicity, we'll use the same prediction for all future hours based on one look-back period.
            # A more robust solution would slide the window and predict one hour at a time.
            recommendations = predict_with_lstm(historical_data, future_data)
            df_copy.loc[SEQUENCE_LENGTH:, 'recommendation'] = recommendations
            # For the historical part, we can fill with a default value or run rule-based logic
            df_copy.loc[:SEQUENCE_LENGTH, 'recommendation'] = 'No Prediction'
        else:
            # If not enough data for a future prediction, use rule-based for all
            df_copy['recommendation'] = df_copy.apply(get_recommendation_rule_based, axis=1)

    else:
        print("Insufficient data for LSTM or model not loaded. Using rule-based system.")
        df_copy['recommendation'] = df_copy.apply(get_recommendation_rule_based, axis=1)
        
    return df_copy