// use chrono::{Duration, Utc};
// use dotenv::dotenv;
// use pyo3::prelude::*;
// use reqwest;
// use serde::{Deserialize, Serialize};
// use serde_json;
// use std::collections::HashMap;
// use std::env;
// use std::error::Error as StdError;
// use std::fmt;
// use std::fs::{self, OpenOptions};
// use std::path::Path;
// use csv;

// // --- Custom Error Handling ---
// #[derive(Debug)]
// enum AppError {
//     Request(reqwest::Error),
//     Api(String),
//     Json(serde_json::Error),
//     Io(std::io::Error),
//     Env(env::VarError),
//     Csv(csv::Error),
// }

// impl fmt::Display for AppError {
//     fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
//         match *self {
//             AppError::Request(ref err) => write!(f, "HTTP Request Error: {}", err),
//             AppError::Api(ref msg) => write!(f, "API Error: {}", msg),
//             AppError::Json(ref err) => write!(f, "JSON Deserialization Error: {}", err),
//             AppError::Io(ref err) => write!(f, "File I/O Error: {}", err),
//             AppError::Env(ref err) => write!(f, "Environment Variable Error: {}", err),
//             AppError::Csv(ref err) => write!(f, "CSV Logging Error: {}", err),
//         }
//     }
// }
// impl StdError for AppError {}
// impl From<reqwest::Error> for AppError { fn from(err: reqwest::Error) -> Self { Self::Request(err) } }
// impl From<serde_json::Error> for AppError { fn from(err: serde_json::Error) -> Self { Self::Json(err) } }
// impl From<std::io::Error> for AppError { fn from(err: std::io::Error) -> Self { Self::Io(err) } }
// impl From<env::VarError> for AppError { fn from(err: env::VarError) -> Self { Self::Env(err) } }
// impl From<csv::Error> for AppError { fn from(err: csv::Error) -> Self { Self::Csv(err) } }
// impl From<AppError> for PyErr {
//     fn from(err: AppError) -> PyErr {
//         pyo3::exceptions::PyValueError::new_err(err.to_string())
//     }
// }

// // --- API & Plan Data Structures ---
// #[derive(Serialize, Deserialize, Debug, Clone)]
// struct AwattarPricePoint {
//     start_timestamp: i64,
//     end_timestamp: i64,
//     marketprice: f64,
// }
// #[derive(Serialize, Deserialize, Debug)]
// struct AwattarPriceResponse { data: Vec<AwattarPricePoint> }
// #[derive(Serialize, Deserialize, Debug)]
// struct OpenWeatherOneCallResponse { hourly: Vec<HourlyWeather> }
// #[derive(Serialize, Deserialize, Debug, Clone)]
// struct HourlyWeather {
//     dt: i64,
//     temp: f64,
//     weather: Vec<WeatherCondition>,
// }
// #[derive(Serialize, Deserialize, Debug, Clone)]
// struct WeatherCondition { main: String }

// #[derive(Serialize)]
// struct HistoryLogEntry {
//     timestamp: i64,
//     price_eur_kwh: f64,
//     temp: f64,
//     weather_condition: String,
// }

// #[derive(Serialize, Deserialize, Debug)]
// struct AppliancePlan {
//     start_time: i64,
//     price: f64,
//     reason: String,
// }
// #[derive(Serialize, Deserialize, Debug)]
// struct TrainedPlan {
//     ev_charge: AppliancePlan,
//     washing_machine: AppliancePlan,
//     dishwasher: AppliancePlan,
//     best_time_to_sell: AppliancePlan,
// }

// // --- Data Logging & Fetching Logic ---
// fn log_data_to_history(prices: &AwattarPriceResponse, weather: &OpenWeatherOneCallResponse) -> Result<(), AppError> {
//     let path = Path::new("data/history.csv");
//     let file_exists = path.exists();
//     let file = OpenOptions::new().write(true).create(true).append(true).open(path)?;
//     let mut wtr = csv::Writer::from_writer(file);
//     if !file_exists {
//         wtr.write_record(&["timestamp", "price_eur_kwh", "temp", "weather_condition"])?;
//     }
//     for price_point in &prices.data {
//         if let Some(weather_hour) = weather.hourly.iter().find(|w| w.dt * 1000 >= price_point.start_timestamp && w.dt * 1000 < price_point.end_timestamp) {
//             wtr.serialize(HistoryLogEntry {
//                 timestamp: price_point.start_timestamp,
//                 price_eur_kwh: price_point.marketprice / 1000.0,
//                 temp: weather_hour.temp,
//                 weather_condition: weather_hour.weather[0].main.clone(),
//             })?;
//         }
//     }
//     wtr.flush()?;
//     Ok(())
// }

// fn get_awattar_price_data() -> Result<AwattarPriceResponse, AppError> {
//     let now = Utc::now();
//     let start_timestamp = (now - Duration::days(1)).timestamp_millis();
//     let end_timestamp = (now + Duration::days(1)).timestamp_millis();
//     let url = format!("https://api.awattar.de/v1/marketdata?start={}&end={}", start_timestamp, end_timestamp);
//     let response = reqwest::blocking::get(&url)?;
//     if !response.status().is_success() { return Err(AppError::Api(format!("aWATTar API Error: {}", response.status()))); }
//     Ok(response.json()?)
// }

// fn get_openweather_data(api_key: &str, lat: f64, lon: f64) -> Result<OpenWeatherOneCallResponse, AppError> {
//     let url = format!("https://api.openweathermap.org/data/3.0/onecall?lat={}&lon={}&appid={}&units=metric&exclude=current,minutely,daily,alerts", lat, lon, api_key);
//     let response = reqwest::blocking::get(&url)?;
//     if !response.status().is_success() { return Err(AppError::Api(format!("OpenWeatherMap API Error: {}", response.status()))); }
//     Ok(response.json()?)
// }

// fn find_best_window(prices: &[AwattarPricePoint], duration_hours: usize, available_slots: &mut HashMap<i64, bool>) -> (usize, f64) {
//     let mut best_avg_price = f64::MAX;
//     let mut best_start_index = 0;
//     if prices.len() < duration_hours { return (0, f64::MAX); }
//     for i in 0..=(prices.len() - duration_hours) {
//         let window = &prices[i..i + duration_hours];
//         if window.iter().all(|p| *available_slots.get(&p.start_timestamp).unwrap_or(&false)) {
//             let avg_price: f64 = window.iter().map(|p| p.marketprice).sum::<f64>() / (duration_hours as f64);
//             if avg_price < best_avg_price {
//                 best_avg_price = avg_price;
//                 best_start_index = i;
//             }
//         }
//     }
//     for i in 0..duration_hours {
//         if let Some(slot) = available_slots.get_mut(&prices[best_start_index + i].start_timestamp) {
//             *slot = false;
//         }
//     }
//     (best_start_index, best_avg_price)
// }

// // --- Python Module Functions ---
// #[pyfunction]
// fn fetch_and_save_data(lat: f64, lon: f64) -> PyResult<String> {
//     dotenv().ok();
//     let openweather_api_key = env::var("OPENWEATHER_API_KEY").map_err(AppError::from)?;
//     let price_data = get_awattar_price_data()?;
//     let weather_data = get_openweather_data(&openweather_api_key, lat, lon)?;
//     log_data_to_history(&price_data, &weather_data)?;
//     let data_dir = Path::new("data");
//     fs::create_dir_all(data_dir)?;

//     // THIS IS THE FIX: Explicitly map the JSON error to our AppError type
//     fs::write(data_dir.join("openweather_data.json"), serde_json::to_string_pretty(&weather_data).map_err(AppError::from)?)?;
//     fs::write(data_dir.join("awattar_price_data.json"), serde_json::to_string_pretty(&price_data).map_err(AppError::from)?)?;
    
//     Ok("✅ Data fetched & logged for AI training.".to_string())
// }

// #[pyfunction]
// fn create_optimized_plan(ev_charge_duration_hours: u32, washer_duration_hours: u32, dishwasher_duration_hours: u32) -> PyResult<String> {
//     let price_data_str = fs::read_to_string("data/awattar_price_data.json").map_err(AppError::from)?;
//     let price_data: AwattarPriceResponse = serde_json::from_str(&price_data_str).map_err(AppError::from)?;
//     let prices = price_data.data;

//     let mut available_slots: HashMap<i64, bool> = prices.iter().map(|p| (p.start_timestamp, true)).collect();

//     let (ev_index, ev_price) = find_best_window(&prices, ev_charge_duration_hours as usize, &mut available_slots);
//     let (washer_index, washer_price) = find_best_window(&prices, washer_duration_hours as usize, &mut available_slots);
//     let (dishwasher_index, dishwasher_price) = find_best_window(&prices, dishwasher_duration_hours as usize, &mut available_slots);
    
//     let best_sell_index = prices.iter().enumerate().max_by(|(_, a), (_, b)| a.marketprice.partial_cmp(&b.marketprice).unwrap()).map(|(index, _)| index).unwrap_or(0);

//     let plan = TrainedPlan {
//         ev_charge: AppliancePlan { start_time: prices[ev_index].start_timestamp, price: ev_price / 1000.0, reason: "Lowest price for duration".to_string() },
//         washing_machine: AppliancePlan { start_time: prices[washer_index].start_timestamp, price: washer_price / 1000.0, reason: "Next best price slot".to_string() },
//         dishwasher: AppliancePlan { start_time: prices[dishwasher_index].start_timestamp, price: dishwasher_price / 1000.0, reason: "Next best price slot".to_string() },
//         best_time_to_sell: AppliancePlan { start_time: prices[best_sell_index].start_timestamp, price: prices[best_sell_index].marketprice / 1000.0, reason: "Highest grid price".to_string() },
//     };

//     // THIS IS THE FIX: Explicitly map the JSON error to our AppError type
//     fs::write("data/plan.json", serde_json::to_string_pretty(&plan).map_err(AppError::from)?)?;
    
//     Ok("✅ Optimized multi-appliance plan created.".to_string())
// }

// #[pymodule]
// fn rust_data_collector(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
//     m.add_function(wrap_pyfunction!(fetch_and_save_data, m)?)?;
//     m.add_function(wrap_pyfunction!(create_optimized_plan, m)?)?;
//     Ok(())
// }
use chrono::{Duration, Utc};
use dotenv::dotenv;
use pyo3::prelude::*;
use reqwest;
use serde::{Deserialize, Serialize};
use serde_json;
use std::collections::HashMap;
use std::env;
use std::error::Error as StdError;
use std::fmt;
use std::fs::{self, OpenOptions};
use std::path::Path;
use csv;

// --- Custom Error Handling ---
#[derive(Debug)]
enum AppError {
    Request(reqwest::Error),
    Api(String),
    Json(serde_json::Error),
    Io(std::io::Error),
    Env(env::VarError),
    Csv(csv::Error),
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            AppError::Request(ref err) => write!(f, "HTTP Request Error: {}", err),
            AppError::Api(ref msg) => write!(f, "API Error: {}", msg),
            AppError::Json(ref err) => write!(f, "JSON Deserialization Error: {}", err),
            AppError::Io(ref err) => write!(f, "File I/O Error: {}", err),
            AppError::Env(ref err) => write!(f, "Environment Variable Error: {}", err),
            AppError::Csv(ref err) => write!(f, "CSV Logging Error: {}", err),
        }
    }
}
impl StdError for AppError {}
impl From<reqwest::Error> for AppError { fn from(err: reqwest::Error) -> Self { Self::Request(err) } }
impl From<serde_json::Error> for AppError { fn from(err: serde_json::Error) -> Self { Self::Json(err) } }
impl From<std::io::Error> for AppError { fn from(err: std::io::Error) -> Self { Self::Io(err) } }
impl From<env::VarError> for AppError { fn from(err: env::VarError) -> Self { Self::Env(err) } }
impl From<csv::Error> for AppError { fn from(err: csv::Error) -> Self { Self::Csv(err) } }
impl From<AppError> for PyErr {
    fn from(err: AppError) -> PyErr {
        pyo3::exceptions::PyValueError::new_err(err.to_string())
    }
}

// --- API & Plan Data Structures ---
#[derive(Serialize, Deserialize, Debug, Clone)]
struct AwattarPricePoint {
    start_timestamp: i64,
    end_timestamp: i64,
    marketprice: f64,
}
#[derive(Serialize, Deserialize, Debug)]
struct AwattarPriceResponse { data: Vec<AwattarPricePoint> }
#[derive(Serialize, Deserialize, Debug)]
struct OpenWeatherOneCallResponse { hourly: Vec<HourlyWeather> }
#[derive(Serialize, Deserialize, Debug, Clone)]
struct HourlyWeather {
    dt: i64,
    temp: f64,
    weather: Vec<WeatherCondition>,
}
#[derive(Serialize, Deserialize, Debug, Clone)]
struct WeatherCondition { main: String }

#[derive(Serialize)]
struct HistoryLogEntry<'a> {
    timestamp: i64,
    price_eur_kwh: f64,
    temp: f64,
    weather_condition: &'a str,
}

#[derive(Serialize, Deserialize, Debug)]
struct AppliancePlan {
    start_time: i64,
    price: f64,
    reason: String,
}
#[derive(Serialize, Deserialize, Debug)]
struct TrainedPlan {
    ev_charge: AppliancePlan,
    washing_machine: AppliancePlan,
    dishwasher: AppliancePlan,
    best_time_to_sell: AppliancePlan,
}

// --- Data Logging & Fetching Logic ---
fn log_data_to_history(prices: &AwattarPriceResponse, weather: &OpenWeatherOneCallResponse) -> Result<(), AppError> {
    let path = Path::new("data/history.csv");
    let file_exists = path.exists();
    let file = OpenOptions::new().write(true).create(true).append(true).open(path)?;
    let mut wtr = csv::Writer::from_writer(file);
    if !file_exists {
        wtr.write_record(&["timestamp", "price_eur_kwh", "temp", "weather_condition"])?;
    }
    for price_point in &prices.data {
        if let Some(weather_hour) = weather.hourly.iter().find(|w| w.dt * 1000 >= price_point.start_timestamp && w.dt * 1000 < price_point.end_timestamp) {
            wtr.serialize(HistoryLogEntry {
                timestamp: price_point.start_timestamp,
                price_eur_kwh: price_point.marketprice / 1000.0,
                temp: weather_hour.temp,
                weather_condition: &weather_hour.weather[0].main,
            })?;
        }
    }
    wtr.flush()?;
    Ok(())
}

fn get_awattar_price_data() -> Result<AwattarPriceResponse, AppError> {
    let now = Utc::now();
    let start_timestamp = (now - Duration::days(1)).timestamp_millis();
    let end_timestamp = (now + Duration::days(1)).timestamp_millis();
    let url = format!("https://api.awattar.de/v1/marketdata?start={}&end={}", start_timestamp, end_timestamp);
    let response = reqwest::blocking::get(&url)?;
    if !response.status().is_success() { return Err(AppError::Api(format!("aWATTar API Error: {}", response.status()))); }
    Ok(response.json()?)
}

fn get_openweather_data(api_key: &str, lat: f64, lon: f64) -> Result<OpenWeatherOneCallResponse, AppError> {
    let url = format!("https://api.openweathermap.org/data/3.0/onecall?lat={}&lon={}&appid={}&units=metric&exclude=current,minutely,daily,alerts", lat, lon, api_key);
    let response = reqwest::blocking::get(&url)?;
    let status = response.status();
    if !status.is_success() {
        let err_text = response.text().unwrap_or_else(|_| "Could not read error body".to_string());
        return Err(AppError::Api(format!("OpenWeatherMap Forecast API Error (Status {}): {}", status, err_text)));
    }
    Ok(response.json()?)
}

fn find_best_window(prices: &[AwattarPricePoint], duration_hours: usize, available_slots: &mut HashMap<i64, bool>) -> (usize, f64) {
    let mut best_avg_price = f64::MAX;
    let mut best_start_index = 0;
    if prices.len() < duration_hours { return (0, f64::MAX); }
    for i in 0..=(prices.len() - duration_hours) {
        let window = &prices[i..i + duration_hours];
        if window.iter().all(|p| *available_slots.get(&p.start_timestamp).unwrap_or(&false)) {
            let avg_price: f64 = window.iter().map(|p| p.marketprice).sum::<f64>() / (duration_hours as f64);
            if avg_price < best_avg_price {
                best_avg_price = avg_price;
                best_start_index = i;
            }
        }
    }
    for i in 0..duration_hours {
        if let Some(slot) = available_slots.get_mut(&prices[best_start_index + i].start_timestamp) {
            *slot = false;
        }
    }
    (best_start_index, best_avg_price)
}

// --- Python Module Functions ---
#[pyfunction]
fn fetch_and_save_data(lat: f64, lon: f64) -> PyResult<String> {
    dotenv().ok();
    let openweather_api_key = env::var("OPENWEATHER_API_KEY").map_err(AppError::from)?;
    let price_data = get_awattar_price_data()?;
    let weather_data = get_openweather_data(&openweather_api_key, lat, lon)?;
    log_data_to_history(&price_data, &weather_data)?;
    let data_dir = Path::new("data");
    fs::create_dir_all(data_dir)?;

    // THIS IS THE FIX: Explicitly map the serde_json::Error to our AppError
    fs::write(data_dir.join("openweather_data.json"), serde_json::to_string_pretty(&weather_data).map_err(AppError::from)?)?;
    fs::write(data_dir.join("awattar_price_data.json"), serde_json::to_string_pretty(&price_data).map_err(AppError::from)?)?;
    
    Ok("✅ Data fetched & logged for AI training.".to_string())
}

#[pyfunction]
fn create_optimized_plan(ev_charge_duration_hours: u32, washer_duration_hours: u32, dishwasher_duration_hours: u32) -> PyResult<String> {
    let price_data_str = fs::read_to_string("data/awattar_price_data.json").map_err(AppError::from)?;
    // THIS IS THE FIX: Explicitly map the serde_json::Error to our AppError
    let price_data: AwattarPriceResponse = serde_json::from_str(&price_data_str).map_err(AppError::from)?;
    let prices = price_data.data;

    let mut available_slots: HashMap<i64, bool> = prices.iter().map(|p| (p.start_timestamp, true)).collect();

    let (ev_index, ev_price) = find_best_window(&prices, ev_charge_duration_hours as usize, &mut available_slots);
    let (washer_index, washer_price) = find_best_window(&prices, washer_duration_hours as usize, &mut available_slots);
    let (dishwasher_index, dishwasher_price) = find_best_window(&prices, dishwasher_duration_hours as usize, &mut available_slots);
    
    let best_sell_index = prices.iter().enumerate().max_by(|(_, a), (_, b)| a.marketprice.partial_cmp(&b.marketprice).unwrap()).map(|(index, _)| index).unwrap_or(0);

    let plan = TrainedPlan {
        ev_charge: AppliancePlan { start_time: prices[ev_index].start_timestamp, price: ev_price / 1000.0, reason: "Lowest price for duration".to_string() },
        washing_machine: AppliancePlan { start_time: prices[washer_index].start_timestamp, price: washer_price / 1000.0, reason: "Next best price slot".to_string() },
        dishwasher: AppliancePlan { start_time: prices[dishwasher_index].start_timestamp, price: dishwasher_price / 1000.0, reason: "Next best price slot".to_string() },
        best_time_to_sell: AppliancePlan { start_time: prices[best_sell_index].start_timestamp, price: prices[best_sell_index].marketprice / 1000.0, reason: "Highest grid price".to_string() },
    };

    // THIS IS THE FIX: Explicitly map the serde_json::Error to our AppError
    fs::write("data/plan.json", serde_json::to_string_pretty(&plan).map_err(AppError::from)?)?;
    
    Ok("✅ Optimized multi-appliance plan created.".to_string())
}

#[pymodule]
fn rust_data_collector(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fetch_and_save_data, m)?)?;
    m.add_function(wrap_pyfunction!(create_optimized_plan, m)?)?;
    Ok(())
}