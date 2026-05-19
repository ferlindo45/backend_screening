#!/bin/bash

echo "========================================="
echo "Stock Screening System Installation"
echo "========================================="

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p data/stock_data
mkdir -p models/saved_models

# Download IndoBERT model (optional - will download on first use)
echo "Setup completed successfully!"
echo ""
echo "To run the system:"
echo "1. Collect data: python run.py collect"
echo "2. Train models: python run.py train"
echo "3. Run API: python run.py api"
echo "4. Generate predictions: python run.py predict"
echo ""
echo "Or run everything: python run.py all"