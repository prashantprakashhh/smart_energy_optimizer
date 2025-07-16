# import numpy as np
# import pandas as pd
# import tensorflow as tf
# from sklearn.model_selection import train_test_split
# from sklearn.preprocessing import MinMaxScaler, LabelEncoder

# # --- 1. Configuration ---
# SEQUENCE_LENGTH = 24  # Use 24 hours of past data to predict the next hour
# MODEL_SAVE_PATH = 'lstm_energy_model.h5'
# DATA_PATH = 'generated_training_data.csv'

# # --- 2. Load and Preprocess Data ---
# print("Loading and preprocessing data...")
# df = pd.read_csv(DATA_PATH)

# # Encode the 'action' labels into numbers
# label_encoder = LabelEncoder()
# df['action_encoded'] = label_encoder.fit_transform(df['action'])
# NUM_CLASSES = len(label_encoder.classes_)
# print(f"Found {NUM_CLASSES} unique actions: {label_encoder.classes_}")

# # Scale numerical features to be between 0 and 1
# scaler = MinMaxScaler()
# df[['price', 'solar_potential']] = scaler.fit_transform(df[['price', 'solar_potential']])

# # --- 3. Create Sequences ---
# print(f"Creating sequences with length {SEQUENCE_LENGTH}...")
# features = df[['price', 'solar_potential']].values
# labels = df['action_encoded'].values

# X, y = [], []
# for i in range(len(features) - SEQUENCE_LENGTH):
#     X.append(features[i:i + SEQUENCE_LENGTH])
#     y.append(labels[i + SEQUENCE_LENGTH])

# X = np.array(X)
# y = tf.keras.utils.to_categorical(y, num_classes=NUM_CLASSES) # One-hot encode labels

# # --- 4. Split Data ---
# X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
# print(f"Training data shape: {X_train.shape}")
# print(f"Validation data shape: {X_val.shape}")


# # --- 5. Build the LSTM Model ---
# print("Building the LSTM model...")
# model = tf.keras.Sequential([
#     tf.keras.layers.LSTM(
#         units=50,
#         return_sequences=True,
#         input_shape=(X_train.shape[1], X_train.shape[2]) # (SEQUENCE_LENGTH, num_features)
#     ),
#     tf.keras.layers.Dropout(0.2),
#     tf.keras.layers.LSTM(units=50),
#     tf.keras.layers.Dropout(0.2),
#     tf.keras.layers.Dense(units=30, activation='relu'),
#     tf.keras.layers.Dense(NUM_CLASSES, activation='softmax') # Output layer: probabilities for each action
# ])

# model.compile(
#     optimizer='adam',
#     loss='categorical_crossentropy', # Good for multi-class classification
#     metrics=['accuracy']
# )
# model.summary()

# # --- 6. Train the Model ---
# print("Training the model...")
# history = model.fit(
#     X_train, y_train,
#     epochs=50, # Adjust as needed
#     batch_size=32,
#     validation_data=(X_val, y_val),
#     verbose=1
# )

# # --- 7. Save the Trained Model ---
# print(f"Saving model to {MODEL_SAVE_PATH}...")
# model.save(MODEL_SAVE_PATH)
# print("Training complete and model saved! 🎉")

# # You can also save the label encoder and scaler for later use in the app
# import pickle
# with open('label_encoder.pkl', 'wb') as f:
#     pickle.dump(label_encoder, f)
# with open('scaler.pkl', 'wb') as f:
#     pickle.dump(scaler, f)

import os
import pickle
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, LabelEncoder

# --- 1. Configuration (Using Absolute Paths) ---
# Get the absolute path of the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Define absolute paths for all files to prevent errors
DATA_PATH = os.path.join(SCRIPT_DIR, 'generated_training_data.csv')
MODEL_SAVE_PATH = os.path.join(SCRIPT_DIR, 'lstm_energy_model.h5')
ENCODER_PATH = os.path.join(SCRIPT_DIR, 'label_encoder.pkl')
SCALER_PATH = os.path.join(SCRIPT_DIR, 'scaler.pkl')

SEQUENCE_LENGTH = 24  # Use 24 hours of past data to predict the next hour

# --- 2. Load and Preprocess Data ---
print(f"Loading data from: {DATA_PATH}")
try:
    df = pd.read_csv(DATA_PATH)
except FileNotFoundError:
    print(f"❌ ERROR: Cannot find the training data file at {DATA_PATH}")
    print("Please make sure you have run 'python src/python_ml_dashboard/generate_dataset.py' first.")
    exit()

# Encode the 'action' labels into numbers
label_encoder = LabelEncoder()
df['action_encoded'] = label_encoder.fit_transform(df['action'])
NUM_CLASSES = len(label_encoder.classes_)
print(f"✅ Found {NUM_CLASSES} unique actions: {label_encoder.classes_}")

# Scale numerical features to be between 0 and 1
scaler = MinMaxScaler()
df[['price', 'solar_potential']] = scaler.fit_transform(df[['price', 'solar_potential']])

# --- 3. Create Sequences for LSTM ---
print(f"Creating sequences with length {SEQUENCE_LENGTH}...")
features = df[['price', 'solar_potential']].values
labels = df['action_encoded'].values

X, y = [], []
# Ensure we don't go out of bounds
if len(features) <= SEQUENCE_LENGTH:
    print("❌ ERROR: Not enough data to create even one sequence.")
    print(f"You have {len(features)} rows of data but need at least {SEQUENCE_LENGTH + 1}.")
    exit()

for i in range(len(features) - SEQUENCE_LENGTH):
    X.append(features[i:i + SEQUENCE_LENGTH])
    y.append(labels[i + SEQUENCE_LENGTH])

X = np.array(X)
y = tf.keras.utils.to_categorical(y, num_classes=NUM_CLASSES) # One-hot encode labels

# --- 4. Split Data into Training and Validation Sets ---
X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"✅ Training data shape: {X_train.shape}")
print(f"✅ Validation data shape: {X_val.shape}")

# --- 5. Build the LSTM Model ---
print("Building the LSTM model...")
model = tf.keras.Sequential([
    tf.keras.layers.LSTM(
        units=50,
        return_sequences=True,
        input_shape=(X_train.shape[1], X_train.shape[2]) # (SEQUENCE_LENGTH, num_features)
    ),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.LSTM(units=50),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(units=30, activation='relu'),
    tf.keras.layers.Dense(NUM_CLASSES, activation='softmax') # Output layer: probabilities for each action
])

model.compile(
    optimizer='adam',
    loss='categorical_crossentropy',
    metrics=['accuracy']
)
model.summary()

# --- 6. Train the Model ---
print("\n--- 🧠 Starting Model Training ---")
history = model.fit(
    X_train, y_train,
    epochs=50, # Adjust as needed
    batch_size=32,
    validation_data=(X_val, y_val),
    verbose=1
)
print("--- ✅ Model Training Complete ---")

# --- 7. Save the Trained Model and Preprocessors ---
print(f"Saving model to {MODEL_SAVE_PATH}...")
model.save(MODEL_SAVE_PATH)

print(f"Saving label encoder to {ENCODER_PATH}...")
with open(ENCODER_PATH, 'wb') as f:
    pickle.dump(label_encoder, f)

print(f"Saving scaler to {SCALER_PATH}...")
with open(SCALER_PATH, 'wb') as f:
    pickle.dump(scaler, f)

print("\n--- 🎉 All files saved! ---")
print("Next, you'll need to update 'ml_model.py' to use these new paths.")