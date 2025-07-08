import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib
import os
from .config import DATA_DIR

# Define the path for the history and model files
HISTORY_FILE = os.path.join(DATA_DIR, "history.csv")
MODEL_FILE = os.path.join(DATA_DIR, "price_predictor.joblib")

def train_price_prediction_model():
    """
    Reads the historical data, trains a linear regression model to predict
    electricity prices, and saves the trained model to a file.
    """
    print("Starting model training...")

    if not os.path.exists(HISTORY_FILE):
        return "History file not found. Please fetch data at least once.", None

    # Load the historical data
    df = pd.read_csv(HISTORY_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # --- Feature Engineering ---
    # We will use the hour of the day and the weather condition as features
    df['hour'] = df['timestamp'].dt.hour
    # Convert weather conditions into numerical categories (one-hot encoding)
    df = pd.get_dummies(df, columns=['weather_condition'], drop_first=True)

    # Define features (X) and target (y)
    features = [col for col in df.columns if col.startswith('hour') or col.startswith('weather_condition_')]
    X = df[features]
    y = df['price_eur_kwh']

    # Split data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # --- Model Training ---
    model = LinearRegression()
    model.fit(X_train, y_train)

    # --- Evaluate the Model ---
    predictions = model.predict(X_test)
    mse = mean_squared_error(y_test, predictions)
    print(f"Model training complete. Mean Squared Error: {mse:.4f}")

    # --- Save the Trained Model ---
    joblib.dump(model, MODEL_FILE)
    print(f"Model saved to {MODEL_FILE}")

    return f"Model trained successfully! MSE: {mse:.4f}", model

if __name__ == '__main__':
    # This allows you to run the trainer directly from the command line for testing
    train_price_prediction_model()