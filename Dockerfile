# Use Python as the base image
FROM python:3.10-slim

# Install system dependencies (needed for Rust and Python packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (needed to compile your data collector)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Set the working directory
WORKDIR /app

# Copy requirement files first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Build the Rust Project
WORKDIR /app/src/rust_data_collector
RUN cargo build --release

# Move the compiled Rust library to the Python site-packages (or local folder)
# We move it to the dashboard folder so app.py can find it locally
RUN cp target/release/librust_data_collector.so /app/src/python_ml_dashboard/rust_data_collector.so || \
    cp target/release/librust_data_collector.dylib /app/src/python_ml_dashboard/rust_data_collector.so || \
    echo "Warning: check rust output name"

# Go back to dashboard directory
WORKDIR /app/src/python_ml_dashboard

# Expose Streamlit port
EXPOSE 8501

# Run the app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]