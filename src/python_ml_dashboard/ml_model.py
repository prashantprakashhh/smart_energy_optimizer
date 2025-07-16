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
import os
import pickle
import numpy as np
import pandas as pd
import tensorflow as tf

# --- 1. Configuration (Using Absolute Paths) ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, 'lstm_energy_model.h5')
ENCODER_PATH = os.path.join(SCRIPT_DIR, 'label_encoder.pkl')
SCALER_PATH = os.path.join(SCRIPT_DIR, 'scaler.pkl')

# --- 2. Load the Trained Model and Preprocessors ---
try:
    print("Attempting to load the LSTM model and preprocessors...")
    MODEL = tf.keras.models.load_model(MODEL_PATH)
    with open(ENCODER_PATH, 'rb') as f:
        LABEL_ENCODER = pickle.load(f)
    with open(SCALER_PATH, 'rb') as f:
        SCALER = pickle.load(f)
    SEQUENCE_LENGTH = MODEL.input_shape[1]
    print("✅ Model and preprocessors loaded successfully.")
except Exception as e:
    print(f"❌ Critical Error loading model: {e}")
    print("Falling back to a simple rule-based system. Please check your model files.")
    MODEL = None

def predict_with_lstm(data_sequence):
    """Predicts the action for a single sequence of historical data."""
    # Scale the features
    scaled_sequence = SCALER.transform(data_sequence[['price', 'solar_potential']])
    
    # Reshape for the model: (1, sequence_length, num_features)
    reshaped_sequence = np.array([scaled_sequence])
    
    # Predict probabilities and get the most likely action
    prediction_probs = MODEL.predict(reshaped_sequence)[0]
    predicted_index = np.argmax(prediction_probs)
    
    # Convert the numerical prediction back to a human-readable action
    return LABEL_ENCODER.inverse_transform([predicted_index])[0]

def predict_future_energy_profile(df, working_hours_start, working_hours_end):
    """
    Processes the full dataframe to generate recommendations for each hour.
    """
    df_copy = df.copy()
    
    # Check if the model is loaded and if there's enough data
    if MODEL and len(df_copy) > SEQUENCE_LENGTH:
        print("Sufficient data available. Using LSTM model for predictions.")
        recommendations = []
        # Iterate through each hour that can be predicted
        for i in range(len(df_copy) - SEQUENCE_LENGTH):
            # The input sequence is the 24 hours *before* the hour we want to predict
            input_sequence = df_copy.iloc[i:i + SEQUENCE_LENGTH]
            prediction = predict_with_lstm(input_sequence)
            recommendations.append(prediction)
        
        # Add a placeholder for the initial hours that can't be predicted
        initial_placeholders = ['Awaiting more data'] * SEQUENCE_LENGTH
        df_copy['recommendation'] = initial_placeholders + recommendations
    else:
        # Fallback message if model isn't loaded or data is insufficient
        print("Insufficient data for LSTM or model not loaded. No recommendations generated.")
        df_copy['recommendation'] = 'Not enough data'
        
    return df_copy