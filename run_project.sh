#!/bin/bash
# run_project.sh
# This script automates the full build, copy, rename, and run cycle for the Smart Energy Optimizer.

# Exit immediately if a command exits with a non-zero status.
# set -e

echo "--- Starting Comprehensive Build and Run Script ---"

# --- 0. Safeguard: Deactivate any existing venv or conda env ---
if command -v deactivate &> /dev/null; then
    deactivate
fi
if [ -n "$CONDA_PREFIX" ]; then
    conda deactivate
fi
echo "Cleaned up previous environment activations."

# --- 1. Activate your Python virtual environment cleanly ---
# Ensure the script runs from the project root for relative paths to work
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

source .venv/bin/activate
echo "Virtual environment activated: $(which python3)"

# --- 2. Define environment variables for Rust build ---
PYTHON_EXECUTABLE="$(which python3)"
export PYO3_PYTHON="${PYTHON_EXECUTABLE}"
echo "PYO3_PYTHON set to: ${PYO3_PYTHON}"

# Infer base Python path (where libpython might be)
PYTHON_BINDIR_OF_BASE="$(${PYTHON_EXECUTABLE} -c 'import sysconfig; print(sysconfig.get_config_var("BINDIR"))')"
PYTHON_BASE_PATH=$(dirname "${PYTHON_BINDIR_OF_BASE}")
echo "Base Python installation path inferred: ${PYTHON_BASE_PATH}"

PYTHON_REAL_LIBDIR="${PYTHON_BASE_PATH}/lib"
echo "Detected REAL base Python lib directory: ${PYTHON_REAL_LIBDIR}"

PYTHON_VERSION_SHORT="$(${PYTHON_EXECUTABLE} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Python version: ${PYTHON_VERSION_SHORT}"

# Set RUSTFLAGS for the linker
export RUSTFLAGS="-L${PYTHON_REAL_LIBDIR} -lpython${PYTHON_VERSION_SHORT}"
echo "RUSTFLAGS set to: ${RUSTFLAGS}"

# Unset conflicting variables
unset LDFLAGS
unset CFLAGS
echo "Unset LDFLAGS and CFLAGS."

# --- 3. Clean all Python __pycache__ and old Rust builds ---
echo "Cleaning all __pycache__ directories..."
find . -depth -name "__pycache__" -exec rm -rf {} \;
echo "Cleaning old Rust build artifacts..."
cargo clean --manifest-path src/rust_data_collector/Cargo.toml

# --- 4. Remove any potentially misleading Python files/directories with the same module name (safe version) ---
echo "Searching for and removing conflicting Python module files..."
find "${PWD}" -type f -name "rust_data_collector.py" -delete -print
# We are NOT aggressively deleting directories to prevent accidental source code loss.

# --- 5. Build the Rust project ---
echo "Building Rust project..."
cd src/rust_data_collector
cargo build --release
if [ $? -ne 0 ]; then
    echo "Rust build failed! Please check the output above for errors."
    exit 1
fi
echo "Rust build completed successfully."
cd "${SCRIPT_DIR}" # Go back to original script directory

# --- 6. Get the exact site-packages path for the venv ---
PYTHON_SITE_PACKAGES="$(${PYTHON_EXECUTABLE} -c "import site; print(site.getsitepackages()[0])")"
echo "Target site-packages for copy: ${PYTHON_SITE_PACKAGES}"

# --- 7. Remove any existing, potentially stale .dylib or .so in site-packages ---
echo "Removing any stale librust_data_collector.dylib or rust_data_collector.so from site-packages..."
rm -f "${PYTHON_SITE_PACKAGES}/librust_data_collector.dylib"
rm -f "${PYTHON_SITE_PACKAGES}/rust_data_collector.so"

# --- 8. Copy the freshly compiled Rust library AND RENAME IT to .so for Python discovery ---
echo "Copying and renaming new librust_data_collector.dylib to rust_data_collector.so..."
cp src/rust_data_collector/target/release/librust_data_collector.dylib "${PYTHON_SITE_PACKAGES}/rust_data_collector.so"
ls -l "${PYTHON_SITE_PACKAGES}/rust_data_collector.so" # Confirm new file is there
echo "Copy and rename complete."

# --- 9. Run the Streamlit Dashboard ---
echo "Starting Streamlit app..."
cd src/python_ml_dashboard
streamlit run app.py

echo "--- Script Finished ---"