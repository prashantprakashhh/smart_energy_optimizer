# import pandas as pd
# import numpy as np
# import os
# import sys
# import json
# import pytz
# from sklearn.preprocessing import MinMaxScaler, LabelEncoder
# from sklearn.model_selection import train_test_split
# import tensorflow as tf
# from tensorflow.keras.models import Sequential
# from tensorflow.keras.layers import LSTM, Dense, Dropout
# from tensorflow.keras.callbacks import EarlyStopping
# import pickle

# # --- Path Setup ---
# def setup_path():
#     current_dir = os.path.dirname(os.path.abspath(__file__))
#     project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
#     if project_root not in sys.path:
#         sys.path.insert(0, project_root)

# setup_path()

# # --- Configuration ---
# GERMAN_TIMEZONE = pytz.timezone('Europe/Berlin')
# DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')
# MODEL_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lstm_energy_model.h5')
# SCALER_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scaler.pkl')
# ENCODER_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'label_encoder.pkl')
# SEQUENCE_LENGTH = 24  # Use 24 hours of data to predict the next hour

# # --- Data Loading and Preprocessing ---
# def load_and_prepare_data():
#     """Loads, merges, and preprocesses the weather and price data."""
#     price_file = os.path.join(DATA_DIR, "awattar_price_data.json")
#     weather_file = os.path.join(DATA_DIR, "openweather_data.json")

#     if not os.path.exists(price_file) or not os.path.exists(weather_file):
#         print("❌ Error: Data files not found. Please run the data fetcher first.")
#         sys.exit(1)

#     # Load and process price data
#     with open(price_file, 'r') as f:
#         price_data = json.load(f)['data']
#     price_df = pd.DataFrame(price_data)
#     price_df['timestamp'] = pd.to_datetime(price_df['start_timestamp'], unit='ms', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
#     price_df['price_eur_kwh'] = price_df['marketprice'] / 1000.0
#     price_df = price_df.set_index('timestamp')[['price_eur_kwh']]

#     # Load and process weather data
#     with open(weather_file, 'r') as f:
#         weather_data = json.load(f)['hourly']
#     weather_df = pd.DataFrame(weather_data)
#     weather_df['timestamp'] = pd.to_datetime(weather_df['dt'], unit='s', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
#     weather_df['weather_condition'] = weather_df['weather'].apply(lambda x: x[0]['main'])
    
#     # Calculate solar potential
#     max_solar_kw = 5.5
#     weather_coeffs = {'Clear': 1.0, 'Clouds': 0.6, 'Rain': 0.3, 'Mist': 0.35, 'Fog': 0.2, 'Snow': 0.25, 'Drizzle': 0.4, 'Thunderstorm': 0.1}
#     sunlight_factor = np.sin(np.pi * (weather_df['timestamp'].dt.hour - 6) / 12).clip(0, 1)
#     weather_factor = weather_df['weather_condition'].map(weather_coeffs).fillna(0.5)
#     weather_df['solar_potential'] = max_solar_kw * sunlight_factor * weather_factor
#     weather_df = weather_df.set_index('timestamp')[['solar_potential']]

#     # Combine data
#     df = price_df.join(weather_df, how='inner').ffill().dropna()
#     print("✅ Data loaded and merged.")
#     return df

# def create_labels(df):
#     """Creates target labels based on price and solar potential."""
#     conditions = [
#         (df['price_eur_kwh'] <= df['price_eur_kwh'].quantile(0.25)),  # Cheap price -> Charge EV
#         (df['price_eur_kwh'] >= df['price_eur_kwh'].quantile(0.80)) & (df['solar_potential'] >= df['solar_potential'].quantile(0.75)), # Expensive & Sunny -> Sell
#         (df['solar_potential'] >= df['solar_potential'].quantile(0.75)) # Just sunny -> Charge Solar
#     ]
#     choices = ['Charge EV', 'Sell to Grid', 'Charge Solar']
#     df['action'] = np.select(conditions, choices, default='Do Nothing')
#     print("✅ Target labels created.")
#     return df

# def create_sequences(df, features, target, sequence_length):
#     """Creates sequences of data for LSTM training."""
#     X, y = [], []
#     for i in range(len(df) - sequence_length):
#         X.append(df[features].iloc[i:i + sequence_length].values)
#         y.append(df[target].iloc[i + sequence_length])
#     print(f"✅ Created {len(X)} sequences.")
#     return np.array(X), np.array(y)

# # --- Model Training ---
# def build_and_train_model(X_train, y_train_encoded, X_val, y_val_encoded, num_classes):
#     """Builds and trains the LSTM model."""
#     model = Sequential([
#         LSTM(units=50, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])),
#         Dropout(0.2),
#         LSTM(units=50),
#         Dropout(0.2),
#         Dense(units=25, activation='relu'),
#         Dense(units=num_classes, activation='softmax') # Softmax for multi-class classification
#     ])
    
#     model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    
#     early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
    
#     print("\n🚀 Starting model training...")
#     history = model.fit(
#         X_train, y_train_encoded,
#         epochs=50,
#         batch_size=32,
#         validation_data=(X_val, y_val_encoded),
#         callbacks=[early_stopping],
#         verbose=1
#     )
#     print("✅ Model training complete.")
#     return model

# # --- Main Execution ---
# if __name__ == "__main__":
#     # 1. Prepare Data
#     main_df = load_and_prepare_data()
#     main_df = create_labels(main_df)
    
#     # 2. Feature Scaling and Encoding
#     features_to_scale = ['price_eur_kwh', 'solar_potential']
#     scaler = MinMaxScaler()
#     main_df[features_to_scale] = scaler.fit_transform(main_df[features_to_scale])
    
#     encoder = LabelEncoder()
#     main_df['action_encoded'] = encoder.fit_transform(main_df['action'])
    
#     # 3. Create Sequences
#     X, y = create_sequences(main_df, features_to_scale, 'action_encoded', SEQUENCE_LENGTH)
    
#     # 4. Split Data
#     X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
#     print(f"Data split: {len(X_train)} training samples, {len(X_val)} validation samples.")
    
#     # 5. Build and Train Model
#     num_classes = len(encoder.classes_)
#     model = build_and_train_model(X_train, y_train, X_val, y_val, num_classes)
    
#     # 6. Save Model and Preprocessors
#     model.save(MODEL_SAVE_PATH)
#     with open(SCALER_SAVE_PATH, 'wb') as f:
#         pickle.dump(scaler, f)
#     with open(ENCODER_SAVE_PATH, 'wb') as f:
#         pickle.dump(encoder, f)
        
#     print(f"\n🎉 Success! Model saved to {MODEL_SAVE_PATH}")
#     print(f"Scaler saved to {SCALER_SAVE_PATH}")
#     print(f"Encoder saved to {ENCODER_SAVE_PATH}")
import pandas as pd
import numpy as np
import os
import sys
import json
import pytz
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
import pickle

# --- Path Setup ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

# --- Configuration ---
GERMAN_TIMEZONE = pytz.timezone('Europe/Berlin')
MODEL_SAVE_PATH = os.path.join(CURRENT_DIR, 'lstm_energy_model.h5')
SCALER_SAVE_PATH = os.path.join(CURRENT_DIR, 'scaler.pkl')
ENCODER_SAVE_PATH = os.path.join(CURRENT_DIR, 'label_encoder.pkl')
SEQUENCE_LENGTH = 12  # Use 12 hours of data to predict the next hour

# --- Data Loading and Preprocessing ---
def load_and_prepare_data():
    price_file = os.path.join(DATA_DIR, "awattar_price_data.json")
    weather_file = os.path.join(DATA_DIR, "weather_data.json")

    if not os.path.exists(price_file) or not os.path.exists(weather_file):
        print(f"❌ Error: Data files not found in '{DATA_DIR}'. Please run the data fetcher in the web app first.")
        sys.exit(1)

    with open(price_file, 'r') as f:
        price_data = json.load(f)['data']
    price_df = pd.DataFrame(price_data)
    price_df['timestamp'] = pd.to_datetime(price_df['start_timestamp'], unit='ms', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
    price_df['price_eur_kwh'] = price_df['marketprice'] / 1000.0
    price_df = price_df.set_index('timestamp')[['price_eur_kwh']]

    with open(weather_file, 'r') as f:
        forecast_days = json.load(f)['forecast']['forecastday']
        hourly_data = []
        for day in forecast_days:
            hourly_data.extend(day['hour'])
    
    weather_df = pd.DataFrame(hourly_data)
    weather_df['temp_c'] = weather_df['temp_c']
    weather_df['weather_condition_text'] = weather_df['condition'].apply(lambda x: x['text'])
    weather_df['timestamp'] = pd.to_datetime(weather_df['time_epoch'], unit='s', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
    weather_df = weather_df.set_index('timestamp')[['temp_c', 'weather_condition_text']]
    
    df = price_df.join(weather_df, how='inner').ffill().dropna()
    
    # --- THIS IS THE FIX ---
    # Check if there's enough data *before* proceeding
    if len(df) < SEQUENCE_LENGTH:
        print(f"❌ Error: Not enough overlapping data to create a single training sequence.")
        print(f"   Need at least {SEQUENCE_LENGTH} hours of data, but found only {len(df)}.")
        print(f"   Please try fetching new data in the web app later.")
        sys.exit(1)
        
    print("✅ Data loaded and merged successfully.")
    return df

def map_and_calculate_solar(df):
    def map_condition(condition_text):
        condition_text = condition_text.lower()
        if 'sun' in condition_text or 'clear' in condition_text: return 'Clear'
        if 'cloudy' in condition_text or 'overcast' in condition_text: return 'Clouds'
        if 'rain' in condition_text or 'drizzle' in condition_text: return 'Rain'
        if 'snow' in condition_text or 'sleet' in condition_text: return 'Snow'
        if 'mist' in condition_text or 'fog' in condition_text: return 'Mist'
        if 'thunder' in condition_text: return 'Thunderstorm'
        return 'Clouds'

    df['weather_condition'] = df['weather_condition_text'].apply(map_condition)
    
    max_solar_kw = 5.5
    weather_coeffs = {'Clear': 1.0, 'Clouds': 0.6, 'Rain': 0.3, 'Mist': 0.35, 'Fog': 0.2, 'Snow': 0.25, 'Drizzle': 0.4, 'Thunderstorm': 0.1}
    sunlight_factor = np.clip(np.sin(np.pi * (df.index.hour - 6) / 12), 0, 1)
    weather_factor = df['weather_condition'].map(weather_coeffs).fillna(0.5)
    df['solar_potential'] = max_solar_kw * sunlight_factor * weather_factor
    print("✅ Solar potential calculated.")
    return df

def create_labels(df):
    conditions = [
        (df['price_eur_kwh'] <= df['price_eur_kwh'].quantile(0.25)),
        (df['price_eur_kwh'] >= df['price_eur_kwh'].quantile(0.80)) & (df['solar_potential'] >= df['solar_potential'].quantile(0.75)),
        (df['solar_potential'] >= df['solar_potential'].quantile(0.75))
    ]
    choices = ['Charge EV', 'Sell to Grid', 'Charge Solar']
    df['action'] = np.select(conditions, choices, default='Do Nothing')
    print("✅ Target labels created.")
    return df

def create_sequences(df, features, target, sequence_length):
    X, y = [], []
    for i in range(len(df) - sequence_length):
        X.append(df[features].iloc[i:i + sequence_length].values)
        y.append(df[target].iloc[i + sequence_length])
    print(f"✅ Created {len(X)} sequences.")
    return np.array(X), np.array(y)

def build_and_train_model(X_train, y_train_encoded, X_val, y_val_encoded, num_classes):
    model = Sequential([
        LSTM(units=50, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])),
        Dropout(0.2),
        LSTM(units=50),
        Dropout(0.2),
        Dense(units=25, activation='relu'),
        Dense(units=num_classes, activation='softmax')
    ])
    
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
    
    print("\n🚀 Starting model training...")
    model.fit(
        X_train, y_train_encoded,
        epochs=50,
        batch_size=32,
        validation_data=(X_val, y_val_encoded),
        callbacks=[early_stopping],
        verbose=1
    )
    print("✅ Model training complete.")
    return model

# --- Main Execution ---
if __name__ == "__main__":
    main_df = load_and_prepare_data()
    main_df = map_and_calculate_solar(main_df)
    main_df = create_labels(main_df)
    
    features_to_scale = ['price_eur_kwh', 'solar_potential']
    scaler = MinMaxScaler()
    main_df[features_to_scale] = scaler.fit_transform(main_df[features_to_scale])
    
    encoder = LabelEncoder()
    main_df['action_encoded'] = encoder.fit_transform(main_df['action'])
    
    X, y = create_sequences(main_df, features_to_scale, 'action_encoded', SEQUENCE_LENGTH)
    
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"Data split: {len(X_train)} training samples, {len(X_val)} validation samples.")
    
    num_classes = len(encoder.classes_)
    model = build_and_train_model(X_train, y_train, X_val, y_val, num_classes)
    
    model.save(MODEL_SAVE_PATH)
    with open(SCALER_SAVE_PATH, 'wb') as f:
        pickle.dump(scaler, f)
    with open(ENCODER_SAVE_PATH, 'wb') as f:
        pickle.dump(encoder, f)
        
    print(f"\n🎉 Success! Model and preprocessors saved.")