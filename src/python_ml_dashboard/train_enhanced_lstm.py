import pandas as pd
import numpy as np
import os
import sys
import json
import pytz
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.optimizers import Adam
import pickle
import warnings
warnings.filterwarnings('ignore')

# --- Configuration ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
GERMAN_TIMEZONE = pytz.timezone('Europe/Berlin')

# Model paths
MODEL_SAVE_PATH = os.path.join(CURRENT_DIR, 'enhanced_lstm_model.h5')
SCALER_SAVE_PATH = os.path.join(CURRENT_DIR, 'enhanced_scaler.pkl')
ENCODER_SAVE_PATH = os.path.join(CURRENT_DIR, 'enhanced_encoder.pkl')
HISTORICAL_DATA_PATH = os.path.join(DATA_DIR, 'historical_data.json')

# Training parameters
SEQUENCE_LENGTH = 24
PREDICTION_HORIZON = 1
MIN_DATA_POINTS = 48  # Minimum 2 days of data

# --- Enhanced Data Loading ---
def load_comprehensive_data():
    """Load both current and historical data for training"""
    all_data = []
    
    # Load current forecast data
    price_file = os.path.join(DATA_DIR, "awattar_price_data.json")
    weather_file = os.path.join(DATA_DIR, "weather_data.json")
    
    if os.path.exists(price_file) and os.path.exists(weather_file):
        current_data = load_current_data(price_file, weather_file)
        if not current_data.empty:
            all_data.append(current_data)
    
    # Load historical data
    if os.path.exists(HISTORICAL_DATA_PATH):
        historical_data = load_historical_data()
        if not historical_data.empty:
            all_data.append(historical_data)
    
    # Generate synthetic data if needed
    if len(all_data) == 0 or sum(len(df) for df in all_data) < MIN_DATA_POINTS:
        print("⚠️ Insufficient real data. Generating synthetic data for training...")
        synthetic_data = generate_synthetic_data(days=21)  # 3 weeks of data
        all_data.append(synthetic_data)
    
    # Combine all data
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=False)
        combined_df = combined_df.sort_index().drop_duplicates()
        
        # Ensure index is datetime
        if not isinstance(combined_df.index, pd.DatetimeIndex):
            print("⚠️ Converting index to DatetimeIndex...")
            if 'timestamp' in combined_df.columns:
                combined_df.index = pd.to_datetime(combined_df['timestamp'])
                combined_df.drop('timestamp', axis=1, inplace=True)
            else:
                # Reset index and convert if possible
                combined_df.reset_index(inplace=True)
                if 'timestamp' in combined_df.columns:
                    combined_df.index = pd.to_datetime(combined_df['timestamp'])
                    combined_df.drop('timestamp', axis=1, inplace=True)
                else:
                    raise ValueError("Cannot convert index to datetime - no timestamp column found")
        
        # Ensure timezone-aware
        if combined_df.index.tz is None:
            combined_df.index = combined_df.index.tz_localize(GERMAN_TIMEZONE)
        elif combined_df.index.tz != GERMAN_TIMEZONE:
            combined_df.index = combined_df.index.tz_convert(GERMAN_TIMEZONE)
        
        print(f"✅ Loaded {len(combined_df)} data points for training")
        print(f"📅 Data range: {combined_df.index.min()} to {combined_df.index.max()}")
        return combined_df
    else:
        raise ValueError("No data available for training")

def load_current_data(price_file, weather_file):
    """Load current forecast data"""
    try:
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
        weather_df['temp'] = weather_df['temp_c']
        weather_df['weather_condition'] = weather_df['condition'].apply(lambda x: x['text'])
        weather_df['timestamp'] = pd.to_datetime(weather_df['time_epoch'], unit='s', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
        weather_df = weather_df.set_index('timestamp')[['temp', 'weather_condition']]
        
        df = price_df.join(weather_df, how='inner').ffill().dropna()
        return df
    except Exception as e:
        print(f"Error loading current data: {e}")
        return pd.DataFrame()

def load_historical_data():
    """Load historical data"""
    try:
        with open(HISTORICAL_DATA_PATH, 'r') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            
            # Ensure timezone-aware
            if df.index.tz is None:
                df.index = df.index.tz_localize(GERMAN_TIMEZONE)
            elif df.index.tz != GERMAN_TIMEZONE:
                df.index = df.index.tz_convert(GERMAN_TIMEZONE)
                
        return df
    except Exception as e:
        print(f"Error loading historical data: {e}")
        return pd.DataFrame()

def generate_synthetic_data(days=21):
    """Generate more realistic synthetic energy data"""
    print(f"🔄 Generating synthetic training data for {days} days...")
    
    # Create time index
    start_date = datetime.now(GERMAN_TIMEZONE) - timedelta(days=days)
    end_date = datetime.now(GERMAN_TIMEZONE)
    time_index = pd.date_range(start=start_date, end=end_date, freq='H', tz=GERMAN_TIMEZONE)
    
    # More realistic price patterns
    np.random.seed(42)
    base_price = 0.25
    
    # Strong daily pattern (peak hours more expensive)
    daily_pattern = []
    for hour in time_index.hour:
        if 6 <= hour <= 9 or 17 <= hour <= 21:  # Peak hours
            daily_pattern.append(0.15)
        elif 22 <= hour <= 23 or 0 <= hour <= 5:  # Off-peak
            daily_pattern.append(-0.10)
        else:  # Mid-day
            daily_pattern.append(0.05)
    
    daily_pattern = np.array(daily_pattern)
    
    # Weekly pattern (higher on weekdays)
    weekly_pattern = np.where(time_index.weekday < 5, 0.03, -0.03)
    
    # Add some volatility
    volatility = np.random.normal(0, 0.08, len(time_index))
    
    # Market events (occasional price spikes)
    spike_probability = 0.05  # 5% chance of spike
    spikes = np.random.random(len(time_index)) < spike_probability
    spike_values = np.where(spikes, np.random.uniform(0.2, 0.5, len(time_index)), 0)
    
    prices = base_price + daily_pattern + weekly_pattern + volatility + spike_values
    prices = np.clip(prices, 0.05, 0.80)
    
    # More realistic weather patterns
    base_temp = 15 + 15 * np.sin(2 * np.pi * (time_index.dayofyear - 80) / 365)
    daily_temp_variation = 8 * np.sin(2 * np.pi * (time_index.hour - 14) / 24)
    temp_noise = np.random.normal(0, 3, len(time_index))
    temperatures = base_temp + daily_temp_variation + temp_noise
    
    # Weather conditions with some persistence
    weather_conditions = []
    current_weather = 'Clear'
    weather_transition = {
        'Clear': {'Clear': 0.7, 'Clouds': 0.25, 'Rain': 0.05},
        'Clouds': {'Clear': 0.3, 'Clouds': 0.5, 'Rain': 0.2},
        'Rain': {'Clear': 0.1, 'Clouds': 0.4, 'Rain': 0.5}
    }
    
    for _ in range(len(time_index)):
        weather_conditions.append(current_weather)
        # Transition to next weather state
        rand = np.random.random()
        cumsum = 0
        for next_weather, prob in weather_transition[current_weather].items():
            cumsum += prob
            if rand <= cumsum:
                current_weather = next_weather
                break
    
    # Create DataFrame
    df = pd.DataFrame({
        'price_eur_kwh': prices,
        'temp': temperatures,
        'weather_condition': weather_conditions
    }, index=time_index)
    
    print(f"✅ Generated {len(df)} synthetic data points")
    return df

def engineer_features(df):
    """Create enhanced features for training"""
    print("🔧 Engineering features...")
    
    # Verify index is DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be DatetimeIndex for feature engineering")
    
    # Map weather conditions
    def map_condition(condition_text):
        condition_text = str(condition_text).lower()
        if 'sun' in condition_text or 'clear' in condition_text: return 'Clear'
        if 'cloudy' in condition_text or 'overcast' in condition_text: return 'Clouds'
        if 'rain' in condition_text or 'drizzle' in condition_text: return 'Rain'
        if 'snow' in condition_text or 'sleet' in condition_text: return 'Snow'
        if 'mist' in condition_text or 'fog' in condition_text: return 'Mist'
        if 'thunder' in condition_text: return 'Thunderstorm'
        return 'Clouds'
    
    df['weather_condition_simple'] = df['weather_condition'].apply(map_condition)
    
    # Calculate solar potential
    max_solar_kw = 5.5
    weather_coeffs = {
        'Clear': 1.0, 'Clouds': 0.6, 'Rain': 0.3, 'Mist': 0.35, 
        'Fog': 0.2, 'Snow': 0.25, 'Drizzle': 0.4, 'Thunderstorm': 0.1
    }
    
    sunlight_factor = np.clip(np.sin(np.pi * (df.index.hour - 6) / 12), 0, 1)
    weather_factor = df['weather_condition_simple'].map(weather_coeffs).fillna(0.5)
    df['solar_potential'] = max_solar_kw * sunlight_factor * weather_factor
    
    # Time-based features
    df['hour_of_day'] = df.index.hour
    df['day_of_week'] = df.index.dayofweek
    df['month'] = df.index.month
    df['is_weekend'] = (df.index.weekday >= 5).astype(int)
    
    # Lag features (previous hour values)
    df['price_lag_1'] = df['price_eur_kwh'].shift(1)
    df['price_lag_2'] = df['price_eur_kwh'].shift(2)
    df['solar_lag_1'] = df['solar_potential'].shift(1)
    
    # Rolling statistics
    df['price_ma_6h'] = df['price_eur_kwh'].rolling(window=6, min_periods=1).mean()
    df['price_ma_24h'] = df['price_eur_kwh'].rolling(window=24, min_periods=1).mean()
    df['solar_ma_6h'] = df['solar_potential'].rolling(window=6, min_periods=1).mean()
    
    # Price volatility
    df['price_volatility'] = df['price_eur_kwh'].rolling(window=6, min_periods=1).std()
    
    # Fill NaN values using forward fill then backward fill
    df = df.fillna(method='ffill').fillna(method='bfill')
    
    # If still NaN values, fill with column means
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].isna().any():
            df[col].fillna(df[col].mean(), inplace=True)
    
    return df

def create_enhanced_labels(df):
    """Create more balanced target labels for different scenarios"""
    print("🎯 Creating enhanced labels...")
    
    # Calculate percentiles for decision making
    price_low = df['price_eur_kwh'].quantile(0.25)
    price_high = df['price_eur_kwh'].quantile(0.75)
    solar_low = df['solar_potential'].quantile(0.25)
    solar_high = df['solar_potential'].quantile(0.75)
    
    actions = []
    for i in range(len(df)):
        current_price = df['price_eur_kwh'].iloc[i]
        current_solar = df['solar_potential'].iloc[i]
        current_hour = df.index[i].hour
        
        # More balanced decision logic
        if current_price <= price_low:
            # Very cheap electricity - good for charging
            if current_hour >= 22 or current_hour <= 6:  # Night time
                actions.append('Charge_EV')
            else:
                actions.append('Run_Appliances')
        elif current_solar >= solar_high and current_hour >= 10 and current_hour <= 16:
            # High solar during day
            actions.append('Store_Solar')
        elif current_price >= price_high:
            # Expensive electricity - good for selling
            actions.append('Sell_to_Grid')
        elif current_solar >= solar_low and current_price <= price_high:
            # Moderate conditions - normal operation
            actions.append('Normal_Operation')
        else:
            # Default case
            actions.append('Normal_Operation')
    
    df['optimal_action'] = actions
    
    # Print label distribution
    label_counts = df['optimal_action'].value_counts()
    print("📊 Label distribution:")
    for label, count in label_counts.items():
        print(f"  {label}: {count} ({count/len(df)*100:.1f}%)")
    
    # Ensure we have at least 3 different labels
    if len(label_counts) < 3:
        print("⚠️ Adding more label variety...")
        # Force some variety by modifying some labels
        indices_to_modify = np.random.choice(df.index, size=min(20, len(df)//3), replace=False)
        for idx in indices_to_modify:
            if df.loc[idx, 'price_eur_kwh'] <= df['price_eur_kwh'].quantile(0.3):
                df.loc[idx, 'optimal_action'] = 'Charge_EV'
            elif df.loc[idx, 'solar_potential'] >= df['solar_potential'].quantile(0.7):
                df.loc[idx, 'optimal_action'] = 'Store_Solar'
            else:
                df.loc[idx, 'optimal_action'] = 'Sell_to_Grid'
    
    return df

def prepare_sequences(df, target_column, sequence_length=SEQUENCE_LENGTH):
    """Prepare sequences for LSTM training"""
    print("📊 Preparing sequences for training...")
    
    # Feature columns
    feature_columns = [
        'price_eur_kwh', 'solar_potential', 'temp', 'hour_of_day', 'day_of_week',
        'month', 'is_weekend', 'price_lag_1', 'price_lag_2', 'solar_lag_1',
        'price_ma_6h', 'price_ma_24h', 'solar_ma_6h', 'price_volatility'
    ]
    
    # Ensure all feature columns exist
    feature_columns = [col for col in feature_columns if col in df.columns]
    
    X, y = [], []
    for i in range(len(df) - sequence_length):
        X.append(df[feature_columns].iloc[i:i + sequence_length].values)
        y.append(df[target_column].iloc[i + sequence_length])
    
    return np.array(X), np.array(y), feature_columns

def build_enhanced_model(input_shape, num_classes):
    """Build simpler but more effective model"""
    print("🏗️ Building enhanced LSTM model...")
    
    model = Sequential([
        LSTM(units=32, return_sequences=True, input_shape=input_shape),
        Dropout(0.3),
        
        LSTM(units=16, return_sequences=False),
        Dropout(0.3),
        
        Dense(units=16, activation='relu'),
        Dropout(0.2),
        
        Dense(units=num_classes, activation='softmax')
    ])
    
    # Use a slightly higher learning rate
    optimizer = Adam(learning_rate=0.002)
    model.compile(
        optimizer=optimizer,
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    return model

def train_enhanced_model(model, X_train, y_train, X_val, y_val):
    """Train with better parameters"""
    print("🚀 Training enhanced model...")
    
    # Calculate class weights to handle imbalanced data
    classes = np.unique(y_train)
    class_weights = compute_class_weight('balanced', classes=classes, y=y_train)
    class_weight_dict = dict(zip(classes, class_weights))
    
    print(f"📊 Using class weights: {class_weight_dict}")
    
    # Define callbacks
    early_stopping = EarlyStopping(
        monitor='val_accuracy',  # Monitor accuracy instead of loss
        patience=10,
        restore_best_weights=True,
        verbose=1,
        mode='max'
    )
    
    reduce_lr = ReduceLROnPlateau(
        monitor='val_accuracy',
        factor=0.5,
        patience=5,
        min_lr=0.0001,
        verbose=1,
        mode='max'
    )
    
    # Train model with class weights
    history = model.fit(
        X_train, y_train,
        epochs=50,  # Reduced epochs for faster training
        batch_size=16,  # Smaller batch size
        validation_data=(X_val, y_val),
        callbacks=[early_stopping, reduce_lr],
        class_weight=class_weight_dict,
        verbose=1
    )
    
    return model, history

def evaluate_model(model, X_test, y_test, encoder):
    """Evaluate model performance"""
    print("📈 Evaluating model performance...")
    
    # Make predictions
    y_pred_probs = model.predict(X_test, verbose=0)
    y_pred = np.argmax(y_pred_probs, axis=1)
    
    # Print classification report
    print("\n📊 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=encoder.classes_))
    
    # Calculate accuracy
    accuracy = np.mean(y_pred == y_test)
    print(f"\n✅ Model Accuracy: {accuracy:.4f}")
    
    return accuracy

# --- Main Training Pipeline ---
def main():
    print("🤖 Starting Enhanced LSTM Training Pipeline")
    print("=" * 50)
    
    try:
        # Load and prepare data
        df = load_comprehensive_data()
        
        if len(df) < MIN_DATA_POINTS:
            print(f"⚠️ Only {len(df)} data points available. Generating more synthetic data...")
            # Generate more synthetic data
            synthetic_df = generate_synthetic_data(days=21)  # 3 weeks of data
            df = pd.concat([df, synthetic_df]).sort_index().drop_duplicates()
            print(f"✅ Total data points after augmentation: {len(df)}")
        
        # Engineer features
        df = engineer_features(df)
        
        # Create labels with better balance
        df = create_enhanced_labels(df)
        
        # Check if we have enough variety in labels
        label_counts = df['optimal_action'].value_counts()
        if len(label_counts) < 3:
            print("⚠️ Adding more label variety...")
            # Force some variety in labels
            df['optimal_action'] = np.random.choice(['Normal_Operation', 'Store_Solar', 'Sell_to_Grid'], 
                                                   size=len(df), p=[0.6, 0.25, 0.15])
        
        # Prepare sequences
        X, y, feature_columns = prepare_sequences(df, 'optimal_action')
        
        if len(X) < 10:
            print("❌ Error: Not enough sequences for training")
            return
        
        # Encode labels
        encoder = LabelEncoder()
        y_encoded = encoder.fit_transform(y)
        
        # Scale features
        scaler = MinMaxScaler()
        X_scaled = np.zeros_like(X)
        
        # Fit scaler on the first sequence and apply to all
        scaler.fit(X[0])
        for i in range(X.shape[0]):
            X_scaled[i] = scaler.transform(X[i])
        
        # Split data with stratification
        try:
            X_train, X_temp, y_train, y_temp = train_test_split(
                X_scaled, y_encoded, test_size=0.3, random_state=42, stratify=y_encoded
            )
            
            X_val, X_test, y_val, y_test = train_test_split(
                X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
            )
        except ValueError:
            # If stratification fails, do it without stratification
            print("⚠️ Cannot stratify - some classes have too few samples")
            X_train, X_temp, y_train, y_temp = train_test_split(
                X_scaled, y_encoded, test_size=0.3, random_state=42
            )
            
            X_val, X_test, y_val, y_test = train_test_split(
                X_temp, y_temp, test_size=0.5, random_state=42
            )
        
        print(f"📊 Data split: {len(X_train)} train, {len(X_val)} val, {len(X_test)} test")
        
        # Build and train model
        input_shape = (X_train.shape[1], X_train.shape[2])
        num_classes = len(encoder.classes_)
        
        model = build_enhanced_model(input_shape, num_classes)
        model, history = train_enhanced_model(model, X_train, y_train, X_val, y_val)
        
        # Evaluate model
        accuracy = evaluate_model(model, X_test, y_test, encoder)
        
        # Save model and preprocessors
        print("💾 Saving model and preprocessors...")
        model.save(MODEL_SAVE_PATH)
        
        with open(SCALER_SAVE_PATH, 'wb') as f:
            pickle.dump(scaler, f)
        
        with open(ENCODER_SAVE_PATH, 'wb') as f:
            pickle.dump(encoder, f)
        
        print(f"\n🎉 Training Complete!")
        print(f"✅ Model saved to: {MODEL_SAVE_PATH}")
        print(f"✅ Scaler saved to: {SCALER_SAVE_PATH}")
        print(f"✅ Encoder saved to: {ENCODER_SAVE_PATH}")
        print(f"📈 Final Accuracy: {accuracy:.4f}")
        print(f"🎯 Model can predict: {', '.join(encoder.classes_)}")
        
        # Print some model statistics
        print(f"\n📊 Model Statistics:")
        print(f"  - Training samples: {len(X_train)}")
        print(f"  - Validation samples: {len(X_val)}")
        print(f"  - Test samples: {len(X_test)}")
        print(f"  - Features: {len(feature_columns)}")
        print(f"  - Sequence length: {SEQUENCE_LENGTH}")
        print(f"  - Classes: {num_classes}")
        
        # Show feature importance (feature names)
        print(f"\n🔧 Features used:")
        for i, feature in enumerate(feature_columns):
            print(f"  {i+1}. {feature}")
        
    except Exception as e:
        print(f"❌ Training failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()