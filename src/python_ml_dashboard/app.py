import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import json
import pytz
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
import tensorflow as tf
import pickle
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# --- Load Environment Variables ---
load_dotenv()
WEATHERAPI_API_KEY = os.getenv("WEATHERAPI_API_KEY")

# --- Path Setup ---
def setup_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, os.path.join(project_root, 'src'))

setup_path()
import rust_data_collector

# --- Page Configuration and Constants ---
st.set_page_config(page_title="AI Smart Energy Optimizer", page_icon="💡", layout="wide")
GERMAN_TIMEZONE = pytz.timezone('Europe/Berlin')
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'enhanced_lstm_model.h5')
ENCODER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'enhanced_encoder.pkl')
SCALER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'enhanced_scaler.pkl')
HISTORICAL_DATA_PATH = os.path.join(DATA_DIR, 'historical_data.json')
SEQUENCE_LENGTH = 24

# --- Appliance Configurations ---
APPLIANCES = {
    'EV Charging': {
        'power_kw': 7.4,
        'duration_hours': 6,
        'priority': 'low_price',
        'flexible': True,
        'icon': '🚗'
    },
    'Dishwasher': {
        'power_kw': 1.8,
        'duration_hours': 2,
        'priority': 'low_price',
        'flexible': True,
        'icon': '🍽️'
    },
    'Washing Machine': {
        'power_kw': 2.3,
        'duration_hours': 2.5,
        'priority': 'low_price',
        'flexible': True,
        'icon': '👕'
    },
    'Solar Storage': {
        'power_kw': 5.5,
        'duration_hours': 1,
        'priority': 'high_solar',
        'flexible': False,
        'icon': '🔋'
    },
    'Grid Selling': {
        'power_kw': 5.5,
        'duration_hours': 1,
        'priority': 'high_price',
        'flexible': False,
        'icon': '💰'
    }
}

# --- Caching & Loading ---
@st.cache_data
def get_coords(location_str):
    try:
        geolocator = Nominatim(user_agent="smart_energy_optimizer", timeout=10)
        location = geolocator.geocode(location_str)
        return (location.latitude, location.longitude) if location else (None, None)
    except Exception:
        return None, None

@st.cache_resource
def load_ai_model():
    if not all(os.path.exists(p) for p in [MODEL_PATH, ENCODER_PATH, SCALER_PATH]):
        return None, None, None
    try:
        model = tf.keras.models.load_model(MODEL_PATH)
        with open(ENCODER_PATH, 'rb') as f: 
            encoder = pickle.load(f)
        with open(SCALER_PATH, 'rb') as f: 
            scaler = pickle.load(f)
        return model, encoder, scaler
    except Exception as e:
        st.error(f"Error loading AI model: {e}")
        return None, None, None

def save_historical_data(df):
    """Save current data to historical records for better training"""
    try:
        historical_data = []
        if os.path.exists(HISTORICAL_DATA_PATH):
            with open(HISTORICAL_DATA_PATH, 'r') as f:
                historical_data = json.load(f)
        
        # Add current data
        current_data = df.reset_index().to_dict('records')
        for record in current_data:
            record['timestamp'] = record['timestamp'].isoformat()
        
        historical_data.extend(current_data)
        
        # Keep only last 30 days of data
        cutoff_date = datetime.now(GERMAN_TIMEZONE) - timedelta(days=30)
        historical_data = [
            record for record in historical_data 
            if datetime.fromisoformat(record['timestamp']) > cutoff_date
        ]
        
        with open(HISTORICAL_DATA_PATH, 'w') as f:
            json.dump(historical_data, f)
            
    except Exception as e:
        st.warning(f"Could not save historical data: {e}")

def load_historical_data():
    """Load historical data for training"""
    if not os.path.exists(HISTORICAL_DATA_PATH):
        return pd.DataFrame()
    
    try:
        with open(HISTORICAL_DATA_PATH, 'r') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
        return df
    except Exception as e:
        st.warning(f"Could not load historical data: {e}")
        return pd.DataFrame()

def calculate_appliance_costs(df, appliance_config):
    """Calculate cost for running appliance at each time slot"""
    power_kw = appliance_config['power_kw']
    duration_hours = appliance_config['duration_hours']
    
    costs = []
    for i in range(len(df) - int(duration_hours) + 1):
        cost = (df['price_eur_kwh'].iloc[i:i+int(duration_hours)].sum() * power_kw)
        costs.append(cost)
    
    # Pad with NaN for incomplete windows
    costs.extend([np.nan] * (len(df) - len(costs)))
    return costs

def add_missing_features(df):
    """Add features that the model expects"""
    # Time-based features
    df['hour_of_day'] = df.index.hour
    df['day_of_week'] = df.index.dayofweek
    df['month'] = df.index.month
    df['is_weekend'] = (df.index.weekday >= 5).astype(int)
    
    # Lag features (handle missing values)
    df['price_lag_1'] = df['price_eur_kwh'].shift(1).fillna(df['price_eur_kwh'].iloc[0])
    df['price_lag_2'] = df['price_eur_kwh'].shift(2).fillna(df['price_eur_kwh'].iloc[0])
    df['solar_lag_1'] = df['solar_potential'].shift(1).fillna(df['solar_potential'].iloc[0])
    
    # Rolling statistics
    df['price_ma_6h'] = df['price_eur_kwh'].rolling(window=6, min_periods=1).mean()
    df['price_ma_24h'] = df['price_eur_kwh'].rolling(window=24, min_periods=1).mean()
    df['solar_ma_6h'] = df['solar_potential'].rolling(window=6, min_periods=1).mean()
    
    # Price volatility
    df['price_volatility'] = df['price_eur_kwh'].rolling(window=6, min_periods=1).std().fillna(0)
    
    # Fill any remaining NaN values
    df = df.fillna(method='ffill').fillna(method='bfill')
    
    return df

def generate_basic_recommendations(df, appliance, config):
    """Generate basic recommendations without AI model"""
    recommendations = {'optimal_times': [], 'avoid_times': []}
    
    if config['priority'] == 'low_price':
        # Find cheapest times
        cost_col = f'{appliance}_cost'
        if cost_col in df.columns and not df[cost_col].isna().all():
            # Get bottom 20% of costs
            threshold = df[cost_col].quantile(0.2)
            optimal_times = df[df[cost_col] <= threshold].index.tolist()
            recommendations['optimal_times'] = optimal_times[:5]  # Limit to top 5
            
            # Get top 20% of costs as avoid times
            avoid_threshold = df[cost_col].quantile(0.8)
            avoid_times = df[df[cost_col] >= avoid_threshold].index.tolist()
            recommendations['avoid_times'] = avoid_times[:3]  # Limit to top 3
    
    elif config['priority'] == 'high_solar':
        # Find highest solar potential times
        threshold = df['solar_potential'].quantile(0.8)
        optimal_times = df[df['solar_potential'] >= threshold].index.tolist()
        recommendations['optimal_times'] = optimal_times[:5]
        
        # Avoid low solar times
        avoid_threshold = df['solar_potential'].quantile(0.2)
        avoid_times = df[df['solar_potential'] <= avoid_threshold].index.tolist()
        recommendations['avoid_times'] = avoid_times[:3]
    
    elif config['priority'] == 'high_price':
        # Find highest price times for selling
        threshold = df['price_eur_kwh'].quantile(0.8)
        optimal_times = df[df['price_eur_kwh'] >= threshold].index.tolist()
        recommendations['optimal_times'] = optimal_times[:5]
        
        # Avoid low price times
        avoid_threshold = df['price_eur_kwh'].quantile(0.2)
        avoid_times = df[df['price_eur_kwh'] <= avoid_threshold].index.tolist()
        recommendations['avoid_times'] = avoid_times[:3]
    
    return recommendations

def generate_ai_recommendations(df, model, encoder, scaler, feature_columns):
    """Generate AI-enhanced recommendations"""
    recommendations = {}
    
    try:
        # Prepare sequences for prediction
        X = []
        for i in range(len(df) - SEQUENCE_LENGTH + 1):
            sequence = df[feature_columns].iloc[i:i + SEQUENCE_LENGTH].values
            X.append(sequence)
        
        if len(X) == 0:
            return recommendations
        
        X = np.array(X)
        
        # Scale the features
        X_scaled = np.zeros_like(X)
        for i in range(X.shape[0]):
            X_scaled[i] = scaler.transform(X[i])
        
        # Make predictions
        predictions = model.predict(X_scaled, verbose=0)
        predicted_classes = np.argmax(predictions, axis=1)
        
        # Map predictions back to actions
        predicted_actions = encoder.inverse_transform(predicted_classes)
        
        # Process predictions for each appliance
        for appliance in APPLIANCES.keys():
            appliance_recommendations = {'ai_optimal_times': [], 'confidence_scores': []}
            
            # Find times when this appliance should be used based on AI predictions
            for i, (action, confidence) in enumerate(zip(predicted_actions, predictions)):
                actual_time_idx = i + SEQUENCE_LENGTH - 1
                if actual_time_idx < len(df):
                    actual_time = df.index[actual_time_idx]
                    max_confidence = np.max(confidence)
                    
                    # Map actions to appliances
                    if (appliance == 'EV Charging' and action in ['Charge_EV', 'Run_Appliances']) or \
                       (appliance == 'Dishwasher' and action in ['Run_Dishwasher', 'Run_Appliances']) or \
                       (appliance == 'Washing Machine' and action in ['Run_Washing_Machine', 'Run_Appliances']) or \
                       (appliance == 'Solar Storage' and action == 'Store_Solar') or \
                       (appliance == 'Grid Selling' and action == 'Sell_to_Grid'):
                        
                        appliance_recommendations['ai_optimal_times'].append(actual_time)
                        appliance_recommendations['confidence_scores'].append(max_confidence)
            
            recommendations[appliance] = appliance_recommendations
        
    except Exception as e:
        print(f"⚠️ AI recommendation generation failed: {e}")
    
    return recommendations

def generate_enhanced_predictions(df, model, encoder, scaler):
    """Enhanced prediction with appliance-specific recommendations"""
    print(f"🔍 Generating predictions for {len(df)} data points...")
    
    # Always provide fallback recommendations even without model
    recommendations = {}
    
    # Calculate appliance costs for basic recommendations
    for appliance, config in APPLIANCES.items():
        cost_col = f'{appliance}_cost'
        df[cost_col] = calculate_appliance_costs(df, config)
        recommendations[appliance] = generate_basic_recommendations(df, appliance, config)
    
    # If model is available and we have enough data, enhance with AI predictions
    if model is not None and encoder is not None and scaler is not None and len(df) >= SEQUENCE_LENGTH:
        try:
            # Add missing features that the model expects
            df = add_missing_features(df)
            
            # Prepare features for model prediction
            feature_columns = [
                'price_eur_kwh', 'solar_potential', 'temp', 'hour_of_day', 'day_of_week',
                'month', 'is_weekend', 'price_lag_1', 'price_lag_2', 'solar_lag_1',
                'price_ma_6h', 'price_ma_24h', 'solar_ma_6h', 'price_volatility'
            ]
            
            # Ensure all required features exist
            available_features = [col for col in feature_columns if col in df.columns]
            
            if len(available_features) >= 5:  # Minimum required features
                ai_recommendations = generate_ai_recommendations(df, model, encoder, scaler, available_features)
                # Merge AI recommendations with basic ones
                for appliance in recommendations:
                    if appliance in ai_recommendations:
                        recommendations[appliance].update(ai_recommendations[appliance])
            else:
                print(f"⚠️ Missing required features. Available: {available_features}")
                
        except Exception as e:
            print(f"⚠️ AI prediction failed: {e}. Using basic recommendations.")
    
    # Apply recommendations to dataframe
    for appliance, rec_data in recommendations.items():
        rec_col = f'{appliance}_recommendation'
        df[rec_col] = 'Normal'
        
        # Apply optimal times (combine basic and AI recommendations)
        optimal_times = set()
        if 'optimal_times' in rec_data:
            optimal_times.update(rec_data['optimal_times'])
        if 'ai_optimal_times' in rec_data:
            optimal_times.update(rec_data['ai_optimal_times'])
        
        if optimal_times:
            df.loc[list(optimal_times), rec_col] = 'Optimal'
        
        # Apply avoid times
        if 'avoid_times' in rec_data:
            avoid_indices = rec_data['avoid_times']
            df.loc[avoid_indices, rec_col] = 'Avoid'
    
    return df

def display_enhanced_action_plan(df):
    """Display enhanced action plan with appliance-specific recommendations"""
    st.header("⚡ Your AI-Powered Smart Home Energy Plan")
    
    # Show data availability status
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Data Points", len(df))
    with col2:
        model, _, _ = load_ai_model()
        model_status = "✅ AI Model" if model is not None else "⚠️ Basic Rules"
        st.metric("🤖 Intelligence", model_status)
    with col3:
        time_range = f"{df.index[0].strftime('%H:%M')} - {df.index[-1].strftime('%H:%M')}"
        st.metric("⏰ Time Range", time_range)
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Optimal Times", "📊 Cost Analysis", "📈 Charts", "📋 Detailed View"])
    
    with tab1:
        st.subheader("🎯 Recommended Actions")
        
        # Display recommendations in a more structured way
        recommendations_found = False
        
        for appliance, config in APPLIANCES.items():
            rec_col = f'{appliance}_recommendation'
            if rec_col in df.columns:
                optimal_times = df[df[rec_col] == 'Optimal']
                avoid_times = df[df[rec_col] == 'Avoid']
                
                if not optimal_times.empty or not avoid_times.empty:
                    recommendations_found = True
                    
                    with st.expander(f"{config['icon']} {appliance}", expanded=True):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if not optimal_times.empty:
                                st.success("✅ **Optimal Times:**")
                                for idx, time in enumerate(optimal_times.index[:3]):  # Show top 3
                                    time_str = time.strftime('%A, %H:%M')
                                    
                                    if config['priority'] == 'low_price':
                                        cost = optimal_times.loc[time, f'{appliance}_cost']
                                        if not pd.isna(cost):
                                            st.write(f"• {time_str} - Cost: €{cost:.2f}")
                                        else:
                                            st.write(f"• {time_str}")
                                    elif config['priority'] == 'high_solar':
                                        solar = optimal_times.loc[time, 'solar_potential']
                                        st.write(f"• {time_str} - Solar: {solar:.1f} kW")
                                    elif config['priority'] == 'high_price':
                                        price = optimal_times.loc[time, 'price_eur_kwh']
                                        st.write(f"• {time_str} - Price: €{price:.3f}/kWh")
                            else:
                                st.info("No optimal times found in current forecast")
                        
                        with col2:
                            if not avoid_times.empty:
                                st.error("❌ **Avoid These Times:**")
                                for time in avoid_times.index[:2]:  # Show top 2 to avoid
                                    time_str = time.strftime('%A, %H:%M')
                                    
                                    if config['priority'] == 'low_price':
                                        cost = avoid_times.loc[time, f'{appliance}_cost']
                                        if not pd.isna(cost):
                                            st.write(f"• {time_str} - Cost: €{cost:.2f}")
                                        else:
                                            st.write(f"• {time_str}")
                                    elif config['priority'] == 'high_solar':
                                        solar = avoid_times.loc[time, 'solar_potential']
                                        st.write(f"• {time_str} - Solar: {solar:.1f} kW")
                                    elif config['priority'] == 'high_price':
                                        price = avoid_times.loc[time, 'price_eur_kwh']
                                        st.write(f"• {time_str} - Price: €{price:.3f}/kWh")
        
        if not recommendations_found:
            st.warning("⚠️ No specific recommendations available. Using basic price/solar analysis.")
            
            # Show basic analysis
            cheapest_time = df.loc[df['price_eur_kwh'].idxmin()]
            most_expensive_time = df.loc[df['price_eur_kwh'].idxmax()]
            best_solar_time = df.loc[df['solar_potential'].idxmax()]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.success(f"💰 **Cheapest Electricity**  \n{cheapest_time.name.strftime('%A, %H:%M')}  \n€{cheapest_time['price_eur_kwh']:.3f}/kWh")
            with col2:
                st.info(f"☀️ **Best Solar Time**  \n{best_solar_time.name.strftime('%A, %H:%M')}  \n{best_solar_time['solar_potential']:.1f} kW")
            with col3:
                st.error(f"💸 **Most Expensive**  \n{most_expensive_time.name.strftime('%A, %H:%M')}  \n€{most_expensive_time['price_eur_kwh']:.3f}/kWh")
    
    with tab2:
        st.subheader("📊 Cost Analysis")
        
        # Calculate potential savings
        cost_data = []
        for appliance, config in APPLIANCES.items():
            cost_col = f'{appliance}_cost'
            if cost_col in df.columns and not df[cost_col].isna().all():
                min_cost = df[cost_col].min()
                max_cost = df[cost_col].max()
                avg_cost = df[cost_col].mean()
                
                cost_data.append({
                    'Appliance': appliance,
                    'Min Cost (€)': min_cost,
                    'Max Cost (€)': max_cost,
                    'Average Cost (€)': avg_cost,
                    'Potential Savings (€)': max_cost - min_cost,
                    'Savings %': ((max_cost - min_cost) / max_cost * 100) if max_cost > 0 else 0
                })
        
        if cost_data:
            cost_df = pd.DataFrame(cost_data)
            
            # Format the dataframe
            styled_df = cost_df.style.format({
                'Min Cost (€)': '{:.2f}',
                'Max Cost (€)': '{:.2f}',
                'Average Cost (€)': '{:.2f}',
                'Potential Savings (€)': '{:.2f}',
                'Savings %': '{:.1f}%'
            })
            
            st.dataframe(styled_df, use_container_width=True)
            
            # Show total potential savings
            total_savings = cost_df['Potential Savings (€)'].sum()
            st.metric("💰 Total Potential Daily Savings", f"€{total_savings:.2f}")
        else:
            st.info("Cost analysis not available - need more data points")
    
    with tab3:
        st.subheader("📈 Energy Forecast Charts")
        
        # Price and solar chart
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Electricity Prices & Solar Generation', 'Appliance Recommendations'),
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
        )
        
        # Price chart
        fig.add_trace(
            go.Scatter(x=df.index.strftime('%Y-%m-%d %H:%M'), y=df['price_eur_kwh'], name='Price (€/kWh)', 
                      line=dict(color='red', width=2)),
            row=1, col=1
        )
        
        # Solar chart on secondary y-axis
        fig.add_trace(
            go.Scatter(x=df.index.strftime('%Y-%m-%d %H:%M'), y=df['solar_potential'], name='Solar (kW)', 
                      line=dict(color='orange', width=2)),
            row=1, col=1, secondary_y=True
        )
        
        # Add optimal times as vertical lines
        # colors = ['green', 'blue', 'purple', 'brown', 'pink']
        # for i, (appliance, config) in enumerate(APPLIANCES.items()):
        #     rec_col = f'{appliance}_recommendation'
        #     if rec_col in df.columns:
        #         optimal_times = df[df[rec_col] == 'Optimal']
        #         if not optimal_times.empty:
        #             for time in optimal_times.index[:2]:  # Show first 2 optimal times
        #                 fig.add_vline(x=time.isoformat(), line_dash="dash", line_color=colors[i % len(colors)], 
        #                             annotation_text=f"{config['icon']} {appliance}", 
        #                             annotation_position="top")
        
        # Recommendations scatter plot
        y_pos = 0

        colors = ['green', 'blue', 'purple', 'brown', 'pink'] 

        for appliance, config in APPLIANCES.items():
            rec_col = f'{appliance}_recommendation'
            if rec_col in df.columns:
                optimal_times = df[df[rec_col] == 'Optimal']
                if not optimal_times.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=optimal_times.index.strftime('%Y-%m-%d %H:%M'),
                            y=[y_pos] * len(optimal_times),
                            mode='markers',
                            name=f"{config['icon']} {appliance}",
                            marker=dict(size=12, color=colors[y_pos % len(colors)])
                        ),
                        row=2, col=1
                    )
                    y_pos += 1
        
        fig.update_layout(height=600, title_text="Smart Energy Forecast & Recommendations")
        fig.update_yaxes(title_text="Price (€/kWh)", row=1, col=1)
        fig.update_yaxes(title_text="Solar Power (kW)", secondary_y=True, row=1, col=1)
        fig.update_yaxes(title_text="Appliances", row=2, col=1)
        fig.update_xaxes(title_text="Time", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("📋 Detailed Forecast Data")
        
        # Prepare display dataframe
        display_columns = ['temp', 'weather_condition', 'price_eur_kwh', 'solar_potential']
        
        # Add recommendation columns
        for appliance in APPLIANCES.keys():
            rec_col = f'{appliance}_recommendation'
            if rec_col in df.columns:
                display_columns.append(rec_col)
        
        # Add cost columns
        for appliance in APPLIANCES.keys():
            cost_col = f'{appliance}_cost'
            if cost_col in df.columns:
                display_columns.append(cost_col)
        
        display_df = df[display_columns].copy()
        display_df.index = display_df.index.strftime('%a %d %b, %H:%M')
        
        # Create formatting dictionary
        format_dict = {
            "temp": "{:.1f}°C",
            "price_eur_kwh": "€{:.3f}/kWh",
            "solar_potential": "{:.2f} kW"
        }
        
        # Add cost column formatting
        for appliance in APPLIANCES.keys():
            cost_col = f'{appliance}_cost'
            if cost_col in display_columns:
                format_dict[cost_col] = "€{:.2f}"
        
        # Display with filtering options
        st.write("**Filter by recommendation:**")
        filter_option = st.selectbox(
            "Show only:",
            ["All times", "Optimal times only", "Times to avoid"],
            key="detail_filter"
        )
        
        if filter_option == "Optimal times only":
            # Show only rows where at least one appliance has 'Optimal' recommendation
            optimal_mask = False
            for appliance in APPLIANCES.keys():
                rec_col = f'{appliance}_recommendation'
                if rec_col in df.columns:
                    optimal_mask = optimal_mask | (df[rec_col] == 'Optimal')
            
            if optimal_mask.any():
                display_df = display_df[optimal_mask]
            else:
                st.info("No optimal times found in current forecast")
        
        elif filter_option == "Times to avoid":
            # Show only rows where at least one appliance has 'Avoid' recommendation
            avoid_mask = False
            for appliance in APPLIANCES.keys():
                rec_col = f'{appliance}_recommendation'
                if rec_col in df.columns:
                    avoid_mask = avoid_mask | (df[rec_col] == 'Avoid')
            
            if avoid_mask.any():
                display_df = display_df[avoid_mask]
            else:
                st.info("No times to avoid identified in current forecast")
        
        # Apply styling
        styled_df = display_df.style.format(format_dict)
        
        # Highlight optimal and avoid times
        def highlight_recommendations(val):
            if val == 'Optimal':
                return 'background-color: #90EE90'  # Light green
            elif val == 'Avoid':
                return 'background-color: #FFB6C1'  # Light red
            return ''
        
        for appliance in APPLIANCES.keys():
            rec_col = f'{appliance}_recommendation'
            if rec_col in display_df.columns:
                styled_df = styled_df.applymap(highlight_recommendations, subset=[rec_col])
        
        st.dataframe(styled_df, use_container_width=True)

# --- Main App ---
st.title("💡 AI Smart Energy Optimizer")
st.markdown("*Optimize your home energy usage with AI-powered predictions*")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Controls")
    location_input = st.text_input("Enter Your Location", "Mannheim, Germany")
    lat, lon = get_coords(location_input)
    
    if not lat or not lon: 
        st.error("Could not find location.")
        st.stop()
    
    st.success(f"📍 Location: {location_input}")
    
    # Data collection settings
    st.subheader("Data Collection")
    auto_collect = st.checkbox("Auto-collect data every hour", value=False)
    
    if not WEATHERAPI_API_KEY:
        st.error("WEATHERAPI_API_KEY not found! Please set it in your .env file.")
    elif st.button("🔄 Fetch Fresh Data & Predict"):
        with st.spinner(f"Fetching data for {location_input}..."):
            try:
                message = rust_data_collector.fetch_and_save_data(lat, lon, DATA_DIR, WEATHERAPI_API_KEY)
                st.success(message)
                st.rerun()
            except Exception as e:
                st.error(f"Data fetch failed: {e}")
    
    # Model training
    st.subheader("AI Model")
    if st.button("🤖 Train Enhanced Model"):
        with st.spinner("Training enhanced model..."):
            try:
                os.system(f"python {os.path.join(os.path.dirname(__file__), 'train_enhanced_lstm.py')}")
                st.success("Model training completed!")
                st.rerun()
            except Exception as e:
                st.error(f"Training failed: {e}")

# --- Main Data Processing ---
model, encoder, scaler = load_ai_model()
weather_file = os.path.join(DATA_DIR, "weather_data.json")
price_file = os.path.join(DATA_DIR, "awattar_price_data.json")

if not os.path.exists(price_file) or not os.path.exists(weather_file):
    st.info("👋 Welcome! Click 'Fetch Fresh Data & Predict' to begin.")
else:
    with st.spinner("🤖 AI is analyzing your energy future..."):
        # Load price data
        with open(price_file, 'r') as f: 
            price_df = pd.DataFrame(json.load(f)['data'])
        price_df['timestamp'] = pd.to_datetime(price_df['start_timestamp'], unit='ms', utc=True).dt.tz_convert(GERMAN_TIMEZONE)
        price_df['price_eur_kwh'] = price_df['marketprice'] / 1000.0
        price_df = price_df.set_index('timestamp')[['price_eur_kwh']]

        # Load weather data
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
        
        # Combine data
        combined_df = price_df.join(weather_df, how='inner').ffill().dropna()

        # Calculate solar potential
        def map_condition(condition_text):
            condition_text = condition_text.lower()
            if 'sun' in condition_text or 'clear' in condition_text: return 'Clear'
            if 'cloudy' in condition_text or 'overcast' in condition_text: return 'Clouds'
            if 'rain' in condition_text or 'drizzle' in condition_text: return 'Rain'
            if 'snow' in condition_text or 'sleet' in condition_text: return 'Snow'
            if 'mist' in condition_text or 'fog' in condition_text: return 'Mist'
            if 'thunder' in condition_text: return 'Thunderstorm'
            return 'Clouds'

        combined_df['weather_condition_simple'] = combined_df['weather_condition'].apply(map_condition)
        
        max_solar_kw = 5.5
        weather_coeffs = {
            'Clear': 1.0, 'Clouds': 0.6, 'Rain': 0.3, 'Mist': 0.35, 
            'Fog': 0.2, 'Snow': 0.25, 'Drizzle': 0.4, 'Thunderstorm': 0.1
        }
        
        sunlight_factor = np.clip(np.sin(np.pi * (combined_df.index.hour - 6) / 12), 0, 1)
        weather_factor = combined_df['weather_condition_simple'].map(weather_coeffs).fillna(0.5)
        combined_df['solar_potential'] = max_solar_kw * sunlight_factor * weather_factor

        # Generate enhanced predictions
        combined_df = generate_enhanced_predictions(combined_df, model, encoder, scaler)
        
        # Save historical data
        save_historical_data(combined_df)
        
        # Display results
        display_enhanced_action_plan(combined_df)
        
        # Show summary metrics
        st.header("📊 Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_price = combined_df['price_eur_kwh'].mean()
            st.metric("Average Price", f"€{avg_price:.3f}/kWh")
        
        with col2:
            max_solar = combined_df['solar_potential'].max()
            st.metric("Peak Solar", f"{max_solar:.1f} kW")
        
        with col3:
            # Count optimal recommendations
            optimal_count = 0
            for appliance in APPLIANCES.keys():
                rec_col = f'{appliance}_recommendation'
                if rec_col in combined_df.columns:
                    optimal_count += (combined_df[rec_col] == 'Optimal').sum()
            st.metric("Optimal Slots", optimal_count)
        
        with col4:
            forecast_hours = len(combined_df)
            st.metric("Forecast Hours", forecast_hours)

# --- Footer ---
st.markdown("---")
st.markdown("*Smart Energy Optimizer - Optimizing your home energy usage with AI*")