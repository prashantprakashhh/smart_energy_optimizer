

// use pyo3::prelude::*;
// use serde::{Deserialize, Serialize};
// use std::error::Error as StdError;
// use std::fmt;
// use std::fs;
// use std::path::Path;

// // --- Custom Error Handling ---
// #[derive(Debug)]
// enum AppError {
//     Request(reqwest::Error),
//     Api(String),
//     Json(serde_json::Error),
//     Io(std::io::Error),
// }

// impl fmt::Display for AppError {
//     fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
//         match *self {
//             AppError::Request(ref err) => write!(f, "HTTP Request Error: {}", err),
//             AppError::Api(ref msg) => write!(f, "API Error: {}", msg),
//             AppError::Json(ref err) => write!(f, "JSON Deserialization Error: {}", err),
//             AppError::Io(ref err) => write!(f, "File I/O Error: {}", err),
//         }
//     }
// }
// impl StdError for AppError {}
// impl From<reqwest::Error> for AppError { fn from(err: reqwest::Error) -> Self { Self::Request(err) } }
// impl From<serde_json::Error> for AppError { fn from(err: serde_json::Error) -> Self { Self::Json(err) } }
// impl From<std::io::Error> for AppError { fn from(err: std::io::Error) -> Self { Self::Io(err) } }
// impl From<AppError> for PyErr {
//     fn from(err: AppError) -> PyErr {
//         pyo3::exceptions::PyValueError::new_err(err.to_string())
//     }
// }

// // --- Data Structures (for One Call API) ---
// #[derive(Serialize, Deserialize, Debug, Clone)]
// struct AwattarPricePoint {
//     start_timestamp: i64,
//     marketprice: f64,
// }
// #[derive(Serialize, Deserialize, Debug)]
// struct AwattarPriceResponse { data: Vec<AwattarPricePoint> }

// // Structures for the One Call API 3.0 Response
// #[derive(Serialize, Deserialize, Debug)]
// struct OpenWeatherOneCallResponse {
//     hourly: Vec<HourlyWeather>,
// }
// #[derive(Serialize, Deserialize, Debug, Clone)]
// struct HourlyWeather {
//     dt: i64,
//     temp: f64,
//     weather: Vec<WeatherCondition>,
// }
// #[derive(Serialize, Deserialize, Debug, Clone)]
// struct WeatherCondition {
//     main: String,
// }


// // --- API Fetching Logic ---
// fn get_awattar_price_data() -> Result<AwattarPriceResponse, AppError> {
//     let url = "https://api.awattar.de/v1/marketdata";
//     Ok(reqwest::blocking::get(url)?.json()?)
// }

// // MODIFIED: This function now calls the One Call 3.0 endpoint
// fn get_openweather_data(api_key: &str, lat: f64, lon: f64) -> Result<OpenWeatherOneCallResponse, AppError> {
//     let url = format!(
//         "https://api.openweathermap.org/data/3.0/onecall?lat={}&lon={}&exclude=current,minutely,daily,alerts&units=metric&appid={}",
//         lat, lon, api_key
//     );

//     let response = reqwest::blocking::get(&url)?;

//     if response.status().is_success() {
//         response.json().map_err(AppError::from)
//     } else {
//         let status = response.status();
//         let error_text = response.text().unwrap_or_else(|_| "Could not read error body".to_string());
//         Err(AppError::Api(format!(
//             "OpenWeatherMap API returned an error (Status {}): {}",
//             status, error_text
//         )))
//     }
// }

// // --- Python Module Function ---
// #[pyfunction]
// fn fetch_and_save_data(lat: f64, lon: f64, data_dir_path: String, api_key: String) -> Result<String, AppError> {
//     let price_data = get_awattar_price_data()?;
//     let weather_data = get_openweather_data(&api_key, lat, lon)?;
    
//     let data_dir = Path::new(&data_dir_path);
//     if !data_dir.exists() {
//         fs::create_dir_all(data_dir)?;
//     }

//     fs::write(data_dir.join("openweather_data.json"), serde_json::to_string_pretty(&weather_data)?)?;
//     fs::write(data_dir.join("awattar_price_data.json"), serde_json::to_string_pretty(&price_data)?)?;

//     Ok(format!("✅ Data (from One Call 3.0 API) fetched and saved to '{}'.", data_dir_path))
// }

// #[pymodule]
// fn rust_data_collector(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
//     m.add_function(wrap_pyfunction!(fetch_and_save_data, m)?)?;
//     Ok(())
// }


use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::error::Error as StdError;
use std::fmt;
use std::fs;
use std::path::Path;

// --- Custom Error Handling ---
#[derive(Debug)]
enum AppError {
    Request(reqwest::Error),
    Api(String),
    Json(serde_json::Error),
    Io(std::io::Error),
}
impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            AppError::Request(ref err) => write!(f, "HTTP Request Error: {}", err),
            AppError::Api(ref msg) => write!(f, "API Error: {}", msg),
            AppError::Json(ref err) => write!(f, "JSON Deserialization Error: {}", err),
            AppError::Io(ref err) => write!(f, "File I/O Error: {}", err),
        }
    }
}
impl StdError for AppError {}
impl From<reqwest::Error> for AppError { fn from(err: reqwest::Error) -> Self { Self::Request(err) } }
impl From<serde_json::Error> for AppError { fn from(err: serde_json::Error) -> Self { Self::Json(err) } }
impl From<std::io::Error> for AppError { fn from(err: std::io::Error) -> Self { Self::Io(err) } }
impl From<AppError> for PyErr {
    fn from(err: AppError) -> PyErr {
        pyo3::exceptions::PyValueError::new_err(err.to_string())
    }
}

// --- Data Structures ---
#[derive(Serialize, Deserialize, Debug, Clone)]
struct AwattarPricePoint {
    start_timestamp: i64,
    marketprice: f64,
}
#[derive(Serialize, Deserialize, Debug)]
struct AwattarPriceResponse { data: Vec<AwattarPricePoint> }

// MODIFIED: Structs for WeatherAPI.com
#[derive(Serialize, Deserialize, Debug)]
struct WeatherApiResponse {
    forecast: Forecast,
}
#[derive(Serialize, Deserialize, Debug)]
struct Forecast {
    forecastday: Vec<ForecastDay>,
}
#[derive(Serialize, Deserialize, Debug)]
struct ForecastDay {
    hour: Vec<Hour>,
}
#[derive(Serialize, Deserialize, Debug, Clone)]
struct Hour {
    time_epoch: i64,
    temp_c: f64,
    condition: Condition,
}
#[derive(Serialize, Deserialize, Debug, Clone)]
struct Condition {
    text: String,
}

// --- API Fetching Logic ---
fn get_awattar_price_data() -> Result<AwattarPriceResponse, AppError> {
    let url = "https://api.awattar.de/v1/marketdata";
    Ok(reqwest::blocking::get(url)?.json()?)
}

// MODIFIED: Fetches data from WeatherAPI.com
fn get_weather_data(api_key: &str, lat: f64, lon: f64) -> Result<WeatherApiResponse, AppError> {
    // We fetch 2 days of forecast to cover the next 48 hours.
    let url = format!(
        "http://api.weatherapi.com/v1/forecast.json?key={}&q={},{}&days=2&aqi=no&alerts=no",
        api_key, lat, lon
    );

    let response = reqwest::blocking::get(&url)?;

    if response.status().is_success() {
        response.json().map_err(AppError::from)
    } else {
        let status = response.status();
        let error_text = response.text().unwrap_or_else(|_| "Could not read error body".to_string());
        Err(AppError::Api(format!(
            "WeatherAPI.com returned an error (Status {}): {}",
            status, error_text
        )))
    }
}

// --- Python Module Function ---
#[pyfunction]
fn fetch_and_save_data(lat: f64, lon: f64, data_dir_path: String, api_key: String) -> Result<String, AppError> {
    let price_data = get_awattar_price_data()?;
    let weather_data = get_weather_data(&api_key, lat, lon)?;
    
    let data_dir = Path::new(&data_dir_path);
    if !data_dir.exists() {
        fs::create_dir_all(data_dir)?;
    }

    fs::write(data_dir.join("weather_data.json"), serde_json::to_string_pretty(&weather_data)?)?;
    fs::write(data_dir.join("awattar_price_data.json"), serde_json::to_string_pretty(&price_data)?)?;

    Ok(format!("✅ Data (from WeatherAPI.com) fetched and saved to '{}'.", data_dir_path))
}

#[pymodule]
fn rust_data_collector(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fetch_and_save_data, m)?)?;
    Ok(())
}