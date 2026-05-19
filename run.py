"""
Main entry point for running the stock screening system
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Main function to run the system"""
    print("=" * 60)
    print("STOCK SCREENING SYSTEM LQ45")
    print("=" * 60)
    print("\nOptions:")
    print("1. Run API Server (FastAPI)")
    print("2. Run Data Collection Only")
    print("3. Run Training Pipeline")
    print("4. Run Batch Prediction")
    print("5. Exit")
    
    while True:
        try:
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == '1':
                print("\nStarting API Server...")
                print("API will be available at http://localhost:8000")
                print("API Documentation at http://localhost:8000/docs")
                
                import uvicorn
                from api.main import app
                from config import API_HOST, API_PORT, API_DEBUG
                
                uvicorn.run(
                    "api.main:app",
                    host=API_HOST,
                    port=API_PORT,
                    reload=API_DEBUG
                )
                break
                
            elif choice == '2':
                print("\nRunning Data Collection...")
                from services.data_collector import DataCollector
                from config import LQ45_STOCKS
                
                collector = DataCollector()
                stock_data = collector.download_multiple_stocks(LQ45_STOCKS)
                
                print(f"\nData collected for {len(stock_data)} stocks:")
                for code, df in stock_data.items():
                    print(f"  - {code}: {len(df)} records")
                break
                
            elif choice == '3':
                print("\nRunning Training Pipeline...")
                from services.data_collector import DataCollector
                from services.feature_engineering import FeatureEngineer
                from services.ml_model import stock_predictor
                from config import LQ45_STOCKS
                
                collector = DataCollector()
                engineer = FeatureEngineer()
                
                stock_code = input("Enter stock code to train (e.g., BBRI.JK): ").strip()
                if not stock_code:
                    stock_code = LQ45_STOCKS[0]
                
                print(f"\nTraining model for {stock_code}...")
                
                # Collect data
                df_raw = collector.download_stock_data(stock_code)
                if df_raw.empty:
                    print(f"Failed to collect data for {stock_code}")
                    return
                
                # Get fundamental data
                fundamental = collector.get_fundamental_data(stock_code)
                
                # Create features
                df_complete = engineer.create_complete_dataset(df_raw, fundamental)
                
                # Prepare for training
                X, y, feature_names = engineer.prepare_features_for_model(df_complete)
                
                print(f"Dataset shape: {X.shape}")
                print(f"Features: {feature_names}")
                
                # Train models
                results = stock_predictor.train_and_evaluate(X, y)
                
                print("\nTraining Results:")
                print("-" * 40)
                for model_name, metrics in results['evaluation'].items():
                    print(f"\n{model_name.upper()}:")
                    print(f"  MAE:  {metrics['mae']:.6f}")
                    print(f"  RMSE: {metrics['rmse']:.6f}")
                    print(f"  R2:   {metrics['r2']:.4f}")
                
                # Save model
                stock_predictor.save_models(stock_code)
                print(f"\nModel saved for {stock_code}")
                break
                
            elif choice == '4':
                print("\nRunning Batch Prediction...")
                import requests
                from config import API_HOST, API_PORT
                
                api_url = f"http://{API_HOST}:{API_PORT}/batch-predict"
                
                try:
                    response = requests.get(api_url)
                    if response.status_code == 200:
                        results = response.json()
                        print("\nPrediction Results:")
                        print("-" * 80)
                        print(f"{'Stock':<12} {'Predicted Return':<18} {'Sentiment':<12} {'Final Score':<12} {'Recommendation'}")
                        print("-" * 80)
                        
                        for result in results['results']:
                            if 'error' not in result:
                                print(f"{result['stock_code']:<12} {result['predicted_return']:>12.4f}     {result['sentiment_score']:>8.3f}   {result['final_score']:>8.3f}   {result['recommendation']}")
                            else:
                                print(f"{result['stock_code']:<12} Error: {result['error']}")
                    else:
                        print(f"API request failed with status {response.status_code}")
                        
                except requests.exceptions.ConnectionError:
                    print("Cannot connect to API. Please start the API server first (Option 1)")
                except Exception as e:
                    print(f"Error: {str(e)}")
                break
                
            elif choice == '5':
                print("\nExiting...")
                break
                
            else:
                print("Invalid choice. Please select 1-5")
                
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()