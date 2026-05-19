"""
Train ALL LQ45 stocks at once with Accuracy Visualization
Run this once, then predictions will be instant!
"""

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import joblib
import os
import time
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
from services.feature_engineering import FeatureEngineer
from services.ml_model import StockPredictor

warnings.filterwarnings('ignore')

# LQ45 Stock List
LQ45_STOCKS_FULL = [
    'AADI.JK', 'ADRO.JK', 'AKRA.JK', 'AMRT.JK', 'ANTM.JK',
    'ARTO.JK', 'ASII.JK', 'BBCA.JK', 'BBRI.JK', 'BBTN.JK',
    'BDMN.JK', 'BBNI.JK', 'BMRI.JK', 'BRIS.JK', 'BRPT.JK',
    'BSDE.JK', 'BUKA.JK', 'BYAN.JK', 'CPIN.JK', 'ERAA.JK',
    'EXCL.JK', 'GGRM.JK', 'GOTO.JK', 'HRUM.JK', 'ICBP.JK',
    'INCO.JK', 'INDF.JK', 'INKP.JK', 'INTP.JK', 'ISAT.JK',
    'ITMG.JK', 'JPFA.JK', 'KLBF.JK', 'MDKA.JK', 'MEDC.JK',
    'MIKA.JK', 'MNCN.JK', 'PGAS.JK', 'PTBA.JK', 'PTPP.JK',
    'PWON.JK', 'SMGR.JK', 'SMRA.JK', 'TBIG.JK', 'TINS.JK',
    'TKIM.JK', 'TLKM.JK', 'TOWR.JK', 'UNTR.JK', 'UNVR.JK'
]

# Store all training results for visualization
training_results_data = []

def create_accuracy_charts(results_data, output_dir="models/charts"):
    """Create comprehensive accuracy charts from training results"""
    os.makedirs(output_dir, exist_ok=True)
    
    if not results_data:
        print("No results data to visualize")
        return
    
    # Convert to DataFrame for easier analysis
    df_results = pd.DataFrame(results_data)
    
    # 1. Model Performance Comparison
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('LQ45 Stock Prediction Model Performance', fontsize=16, fontweight='bold')
    
    models = ['random_forest', 'xgboost', 'linear_regression', 'ensemble']
    model_names = ['Random Forest', 'XGBoost', 'Linear Regression', 'Ensemble']
    colors = ['#2ecc71', '#3498db', '#e74c3c', '#9b59b6']
    
    # R2 Distribution
    ax1 = axes[0, 0]
    r2_data = [[r['evaluation'][m]['r2'] for r in results_data if m in r['evaluation']] for m in models]
    bp = ax1.boxplot(r2_data, labels=model_names, patch_artist=True)
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color); patch.set_alpha(0.7)
    ax1.axhline(y=0, color='red', linestyle='--')
    ax1.set_title('Model R² Score Distribution (Higher is Better)')
    ax1.grid(True, alpha=0.3)
    
    # MAE Distribution
    ax2 = axes[0, 1]
    mae_data = [[r['evaluation'][m]['mae'] for r in results_data if m in r['evaluation']] for m in models]
    bp2 = ax2.boxplot(mae_data, labels=model_names, patch_artist=True)
    for patch, color in zip(bp2['boxes'], colors):
        patch.set_facecolor(color); patch.set_alpha(0.7)
    ax2.set_title('Model MAE Distribution (Lower is Better)')
    ax2.grid(True, alpha=0.3)
    
    # RMSE Distribution
    ax3 = axes[1, 0]
    rmse_data = [[r['evaluation'][m]['rmse'] for r in results_data if m in r['evaluation']] for m in models]
    bp3 = ax3.boxplot(rmse_data, labels=model_names, patch_artist=True)
    for patch, color in zip(bp3['boxes'], colors):
        patch.set_facecolor(color); patch.set_alpha(0.7)
    ax3.set_title('Model RMSE Distribution (Lower is Better)')
    ax3.grid(True, alpha=0.3)
    
    # Summary Bar
    ax4 = axes[1, 1]
    avg_r2 = [np.mean(d) for d in r2_data]
    ax4.bar(model_names, avg_r2, color=colors, alpha=0.8)
    ax4.set_title('Average R² Score per Model')
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '1_model_performance_comparison.png'), dpi=150)
    plt.close()
    
    # 2. Leaderboard
    fig, ax = plt.subplots(figsize=(10, 8))
    results_data.sort(key=lambda x: x['evaluation']['ensemble']['r2'], reverse=True)
    top_20 = results_data[:20]
    ax.barh([r['stock_code'] for r in top_20], [r['evaluation']['ensemble']['r2'] for r in top_20], color='#2ecc71')
    ax.set_title('Top 20 Stocks by Ensemble R² Score')
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '2_top_stocks_leaderboard.png'), dpi=150)
    plt.close()
    
    print(f"📊 Accuracy charts saved to: {output_dir}")

def train_stock(stock_code, engineer, models_dir):
    """Train model for a single stock"""
    global training_results_data
    print(f"\nTraining {stock_code}...")
    
    try:
        ticker = yf.Ticker(stock_code)
        df = ticker.history(period="5y")
        if df.empty or len(df) < 100:
            print(f"⚠ Skip {stock_code}: Insufficient data")
            return None
        
        df.reset_index(inplace=True)
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        
        try:
            info = ticker.info
            fundamental = {
                'roe': info.get('returnOnEquity', 0.15) * 100,
                'per': info.get('trailingPE', 15.0),
                'der': info.get('debtToEquity', 0.8),
                'eps': info.get('trailingEps', 500),
                'dividend': info.get('dividendYield', 0.03)
            }
        except:
            fundamental = {'roe': 15.0, 'per': 12.0, 'der': 0.8, 'eps': 750, 'dividend': 0.035}
        
        df_complete = engineer.create_complete_dataset(df, fundamental, None)
        if df_complete.empty or len(df_complete) < 50:
            print(f"⚠ Skip {stock_code}: Failed feature engineering")
            return None
            
        X, y, feature_names = engineer.prepare_features_for_model(df_complete)
        predictor = StockPredictor()
        results = predictor.train_and_evaluate(X, y)
        
        training_results_data.append({
            'stock_code': stock_code,
            'evaluation': results['evaluation'],
            'train_size': results['train_size'],
            'test_size': results['test_size'],
            'feature_count': len(feature_names)
        })
        
        for name, model in predictor.trained_models.items():
            joblib.dump(model, os.path.join(models_dir, f"{name}_{stock_code}.pkl"))
        
        metadata = {'stock_code': stock_code, 'trained_date': datetime.now().isoformat(), 'samples': len(X), 'evaluation': results['evaluation']}
        with open(os.path.join(models_dir, f"metadata_{stock_code}.json"), 'w') as f:
            json.dump(metadata, f, indent=2)
            
        print(f"  ✓ Success: Ensemble R²={results['evaluation']['ensemble']['r2']:.4f}")
        return predictor
    except Exception as e:
        print(f"  ✗ Error: {str(e)[:50]}")
        return None

def main():
    print("="*70)
    print("BATCH TRAINING LQ45 STOCKS")
    print("="*70)
    
    models_dir = "models/saved_models"
    charts_dir = "models/charts"
    os.makedirs(models_dir, exist_ok=True)
    
    engineer = FeatureEngineer()
    trained_stocks = []
    start_time = time.time()
    
    for i, stock_code in enumerate(LQ45_STOCKS_FULL, 1):
        print(f"[{i}/{len(LQ45_STOCKS_FULL)}] ", end="")
        if train_stock(stock_code, engineer, models_dir):
            trained_stocks.append(stock_code)
        time.sleep(1)
    
    elapsed = (time.time() - start_time) / 60
    create_accuracy_charts(training_results_data, charts_dir)
    
    with open(os.path.join(models_dir, "trained_stocks.json"), 'w') as f:
        json.dump({'trained_stocks': trained_stocks, 'date': datetime.now().isoformat(), 'duration_min': elapsed}, f, indent=2)
    
    print("\n" + "="*70)
    print(f"DONE! Trained {len(trained_stocks)} stocks in {elapsed:.1f} minutes.")
    print("="*70)

if __name__ == "__main__":
    if input("\nStart training all LQ45 stocks? (yes/no): ").lower() == 'yes':
        main()