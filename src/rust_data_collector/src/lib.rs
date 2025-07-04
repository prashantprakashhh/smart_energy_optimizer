// src/rust_data_collector/src/lib.rs

use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use chrono::{Utc, Duration};
use dotenv::dotenv;
use std::env;
use std::fs;
use std::path::Path;
use pyo3::prelude::*;

// --- Data Structures for API Responses ---

// OpenWeatherMap Current Weather (simplified)
#[derive(Debug, Serialize, Deserialize)]
pub struct OpenWeatherCurrent {
    pub main: OpenWeatherMain,
    pub weather: Vec<OpenWeatherWeather>,
    pub dt: i64, // Unix timestamp
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OpenWeatherMain {
    pub temp: f64,
    pub feels_like: f64,
    pub humidity: i32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OpenWeatherWeather {
    pub description: String,
    pub icon: String,
}

// OpenWeatherMap Hourly Forecast (simplified)
#[derive(Debug, Serialize, Deserialize)]
pub struct OpenWeatherHourlyForecast {
    pub dt: i64, // Unix timestamp
    pub temp: f64,
    pub weather: Vec<OpenWeatherWeather>,
    pub pop: f64, // Probability of precipitation
    pub clouds: OpenWeatherClouds,
    // Note: OpenWeatherMap's hourly forecast doesn't directly give solar irradiance
    // For a more accurate solar prediction, a dedicated solar API (like Solcast, Meteotest)
    // or a sophisticated solar model based on cloud cover, time of day, season, etc., is needed.
    // For now, we'll just get general weather.
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OpenWeatherClouds {
    pub all: i32, // Cloudiness, %
}

// Wrapper for OpenWeatherMap One Call API response
#[derive(Debug, Serialize, Deserialize)]
pub struct OpenWeatherOneCallResponse {
    pub current: OpenWeatherCurrent,
    pub hourly: Vec<OpenWeatherHourlyForecast>,
    // daily, alerts, minutely etc. can be added if needed
}

// SMARD API (Day-ahead auction price)
// Example SMARD JSON: {"data":[{"timestamp":1672531200000,"value":-0.01},{"timestamp":...}]}
#[derive(Debug, Serialize, Deserialize)]
pub struct SmardDataPoint {
    pub timestamp: i64, // Milliseconds since epoch
    pub value: f64,     // Price in EUR/MWh
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SmardApiResponse {
    pub data: Vec<SmardDataPoint>,
}


// --- Functions to Fetch Data ---

fn get_openweather_data(api_key: &str, lat: f64, lon: f64) -> Result<OpenWeatherOneCallResponse, reqwest::Error> {
    let url = format!(
        "https://api.openweathermap.org/data/3.0/onecall?lat={}&lon={}&exclude=minutely,daily,alerts&appid={}&units=metric",
        lat, lon, api_key
    );
    println!("DEBUG (Rust): OpenWeatherMap API Request URL: {}", url);
    let client = Client::new();
    let response = client.get(&url).send()?; // This sends the request and gets the reqwest::blocking::Response object

    // --- Corrected Debug Block and Error Handling ---
    let status = response.status(); // Access status BEFORE consuming the response body
    println!("DEBUG (Rust): OpenWeatherMap Response Status: {}", status);

    // Consume the response body into text
    let response_text = response.text()?; // .text() consumes the response, so we need to clone if we wanted to read it multiple times (not needed here)
    println!("DEBUG (Rust): OpenWeatherMap Raw Response (first 500 chars): {}", &response_text[..std::cmp::min(response_text.len(), 500)]);

    // Check for non-200 status codes. reqwest's `error_for_status()` is the idiomatic way.
    // If the status is 4xx or 5xx, this will convert it into a reqwest::Error.
    let response_for_status = response_text.clone(); // Clone to use for potential error reporting
    let mut response_result = Ok(()); // Dummy result to build upon

    // Manually check status and build custom error if not success
    if !status.is_success() {
        println!("ERROR (Rust): OpenWeatherMap API returned non-success status {}. Full raw response: {}", status, response_text);
        return Err(reqwest::Error::builder()
            .status(status)
            .text(response_text) // Include the full text for debugging
            .build());
    }

    // Now, attempt to deserialize the text
    let parsed_response: OpenWeatherOneCallResponse = serde_json::from_str(&response_text)
        .map_err(|e| {
            // If deserialization fails, print the full response text for more context
            println!("ERROR (Rust): Failed to deserialize OpenWeatherMap response. Error: {}", e);
            println!("ERROR (Rust): Full raw response was: {}", response_text); // CRUCIAL: Full response on error
            
            // Build a reqwest::Error for deserialization failure using its builder.
            // reqwest::Error::builder().build() creates a generic error.
            reqwest::Error::builder()
                .text(response_text) // Include the response text for debugging
                .build() // This creates a generic reqwest::Error, kind will be "Unknown"
        })?;

    Ok(parsed_response)
}

// For SMARD, we will fetch data for the last 48 hours for demonstration.
// SMARD API data URLs are typically structured like this for 'Day-ahead auction price' (filter 1001):
// https://www.smard.de/app/chart_data/1001/DE/index_hour.json
// This index_hour.json gives the current state of hourly data.
// For historical ranges, you might need to use `table_data` or download CSVs,
// but for a live system, the `index_hour.json` is typically updated regularly.
// Let's simulate fetching for a specific time range to make it more robust.
// SMARD timestamps are in milliseconds.
fn get_smard_day_ahead_prices(
    base_url: &str,
    filter: &str,
    region: &str,
    resolution: &str,
    start_timestamp_ms: i64,
    end_timestamp_ms: i64
) -> Result<SmardApiResponse, reqwest::Error> {
    // SMARD's chart_data endpoint doesn't support direct time range queries.
    // It provides data up to "index_hour.json".
    // To get historical data, one typically downloads CSVs from their "Data download" section.
    // For continuous fetching, you would periodically hit `index_hour.json` and append.
    // For this example, let's hardcode a URL for a recent period or use the general index.
    // A robust solution would involve checking the latest timestamp and fetching new data.
    
    // For simplicity, let's fetch the general hourly index, which usually contains recent data.
    // Note: The specific URL format for historical data ranges might differ or require manual download.
    let url = format!("{}/{}/{}/index_{}.json", base_url, filter, region, resolution);
    println!("Fetching SMARD data from: {}", url); // Debug print
    let client = Client::new();
    let response = client.get(&url).send()?.json::<SmardApiResponse>()?;

    // Filter data by timestamp in Rust, as SMARD `index_hour.json` returns all available data.
    let filtered_data: Vec<SmardDataPoint> = response.data.into_iter()
        .filter(|dp| dp.timestamp >= start_timestamp_ms && dp.timestamp <= end_timestamp_ms)
        .collect();

    Ok(SmardApiResponse { data: filtered_data })
}

// --- Python Bindings ---
#[pyfunction]
fn fetch_and_save_data(data_dir: &str, lat: f64, lon: f64) -> PyResult<String> {
    dotenv().ok(); // Load .env file

    println!("DEBUG (Rust): Attempting to load OPENWEATHER_API_KEY...");
    let openweather_api_key = env::var("OPENWEATHER_API_KEY")
    .map_err(|e| {
        // This line will print to the terminal where Streamlit is running if the key is not found
        println!("ERROR (Rust): OPENWEATHER_API_KEY not found or invalid. Error details: {}", e);
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("OPENWEATHER_API_KEY not set: {}", e))
    })?;
    println!("DEBUG (Rust): OPENWEATHER_API_KEY successfully loaded.");
    
    // SMARD API keys are commented out in .env and config.py as per our findings for public data.
    let smard_base_url = "https://www.smard.de/app/chart_data";
    let smard_price_filter = "1001";
    let smard_region = "DE";
    let smard_resolution = "hour";

    let now = Utc::now();
    let end_timestamp_ms = now.timestamp_millis();
    let start_timestamp_ms = (now - Duration::hours(48)).timestamp_millis(); // Last 48 hours

    // Fetch OpenWeatherMap data
    println!("Fetching OpenWeatherMap data...");
    let weather_data = get_openweather_data(&openweather_api_key, lat, lon)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to fetch OpenWeatherMap data: {}", e)))?;
    let weather_path = Path::new(data_dir).join("weather_data.json");
    fs::write(&weather_path, serde_json::to_string_pretty(&weather_data).unwrap())
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write weather data: {}", e)))?;
    println!("OpenWeatherMap data saved to {:?}", weather_path);

    // Fetch SMARD data
    println!("Fetching SMARD data...");
    let smard_data = get_smard_day_ahead_prices(
        smard_base_url,
        smard_price_filter,
        smard_region,
        smard_resolution,
        start_timestamp_ms,
        end_timestamp_ms
    )
    .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to fetch SMARD data: {}", e)))?;
    let smard_path = Path::new(data_dir).join("smard_prices.json");
    fs::write(&smard_path, serde_json::to_string_pretty(&smard_data).unwrap())
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write SMARD data: {}", e)))?;
    println!("SMARD data saved to {:?}", smard_path);

    Ok("Data fetching complete.".to_string())
}

/// A Python module implemented in Rust.
#[pymodule]
fn rust_data_collector(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fetch_and_save_data, m)?)?;
    Ok(())
}