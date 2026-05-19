"""
Setup script to install all required dependencies and download NLTK data
"""

import subprocess
import sys
import nltk
import os

def install_packages():
    """Install required Python packages"""
    packages = [
        'yfinance',
        'pandas',
        'numpy',
        'scikit-learn',
        'xgboost',
        'transformers',
        'torch',
        'fastapi',
        'uvicorn',
        'python-dotenv',
        'joblib',
        'pydantic',
        'requests',
        'beautifulsoup4',
        'nltk'
    ]
    
    print("Installing required packages...")
    for package in packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✓ Installed {package}")
        except Exception as e:
            print(f"✗ Failed to install {package}: {e}")

def download_nltk_data():
    """Download NLTK data"""
    print("\nDownloading NLTK data...")
    resources = ['punkt', 'stopwords', 'punkt_tab']
    
    for resource in resources:
        try:
            nltk.download(resource, quiet=False)
            print(f"✓ Downloaded {resource}")
        except Exception as e:
            print(f"✗ Failed to download {resource}: {e}")
    
    # Verify download
    try:
        from nltk.corpus import stopwords
        stopwords.words('indonesian')
        print("✓ NLTK stopwords verified")
    except:
        print("⚠ Using fallback stopwords")

def create_directories():
    """Create necessary directories"""
    directories = [
        'data/stock_data',
        'models/saved_models',
        'logs'
    ]
    
    print("\nCreating directories...")
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created {directory}")

def test_imports():
    """Test if all imports work"""
    print("\nTesting imports...")
    try:
        import yfinance
        print("✓ yfinance")
    except ImportError as e:
        print(f"✗ yfinance: {e}")
    
    try:
        import pandas
        print("✓ pandas")
    except ImportError as e:
        print(f"✗ pandas: {e}")
    
    try:
        import fastapi
        print("✓ fastapi")
    except ImportError as e:
        print(f"✗ fastapi: {e}")
    
    try:
        import transformers
        print("✓ transformers")
    except ImportError as e:
        print(f"✗ transformers: {e}")

def main():
    """Main setup function"""
    print("=" * 60)
    print("STOCK SCREENING SYSTEM - SETUP")
    print("=" * 60)
    
    # Install packages
    install_packages()
    
    # Download NLTK data
    download_nltk_data()
    
    # Create directories
    create_directories()
    
    # Test imports
    test_imports()
    
    print("\n" + "=" * 60)
    print("SETUP COMPLETED!")
    print("=" * 60)
    print("\nYou can now run the system with:")
    print("  python run.py")
    print("\nOr run the API directly with:")
    print("  python api/main.py")

if __name__ == "__main__":
    main()