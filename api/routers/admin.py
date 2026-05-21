import logging
import asyncio
import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Optional, Any

from api.database import get_db
from models.db_models import Screening
from config import API_KEY, LQ45_STOCKS
from services.feature_engineering import FeatureEngineer
from train_all_lq45 import train_stock

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["Admin API"]
)

# API key dependency
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_admin_key(api_key: str = Depends(api_key_header)):
    """Verify admin secret API key"""
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Akses ditolak: API Key Admin tidak valid.")
    return api_key

# Keep track of active training jobs
training_jobs = {
    'status': 'idle',  # 'idle' or 'running'
    'progress': 0,
    'total': 0,
    'current_stock': '',
    'logs': []
}

def run_bulk_training(stock_list: List[str]):
    """Background task to train multiple stocks sequentially"""
    global training_jobs
    training_jobs['status'] = 'running'
    training_jobs['progress'] = 0
    training_jobs['total'] = len(stock_list)
    training_jobs['logs'] = [f"Memulai training untuk {len(stock_list)} saham..."]
    
    engineer = FeatureEngineer()
    models_dir = "models/saved_models"
    
    for i, code in enumerate(stock_list, 1):
        training_jobs['current_stock'] = code
        training_jobs['progress'] = i
        training_jobs['logs'].append(f"[{i}/{len(stock_list)}] Memulai training saham {code}...")
        
        try:
            # Run the synchronous training script
            predictor = train_stock(code, engineer, models_dir)
            if predictor:
                training_jobs['logs'].append(f"✓ Saham {code} sukses dilatih dan disimpan ke DB.")
            else:
                training_jobs['logs'].append(f"✗ Saham {code} gagal dilatih (data tidak cukup).")
        except Exception as e:
            training_jobs['logs'].append(f"✗ Error melatih saham {code}: {str(e)}")
            
    training_jobs['status'] = 'idle'
    training_jobs['current_stock'] = ''
    training_jobs['logs'].append("Proses training massal selesai!")

@router.post("/train")
async def trigger_training(
    stock_code: str, 
    background_tasks: BackgroundTasks, 
    api_key: str = Depends(verify_admin_key)
):
    """
    Trigger training model AI untuk saham tertentu (misal: BBRI.JK) atau 'ALL' untuk semua saham.
    Proses berjalan di background agar tidak timeout.
    """
    global training_jobs
    if training_jobs['status'] == 'running':
        raise HTTPException(status_code=400, detail="Ada proses training yang sedang berjalan. Mohon tunggu.")
        
    if stock_code.upper() == 'ALL':
        background_tasks.add_task(run_bulk_training, LQ45_STOCKS)
        return {
            "status": "started",
            "message": f"Training massal untuk semua ({len(LQ45_STOCKS)}) saham LQ45 telah dimulai di background."
        }
    else:
        if not stock_code.endswith('.JK'):
            stock_code = f"{stock_code}.JK"
            
        background_tasks.add_task(run_bulk_training, [stock_code])
        return {
            "status": "started",
            "message": f"Training untuk saham {stock_code} telah dimulai di background."
        }

@router.get("/training-status")
async def get_training_status(api_key: str = Depends(verify_admin_key)):
    """
    Mendapatkan status real-time dari proses training yang berjalan di background.
    """
    return training_jobs

@router.get("/status")
async def get_system_status(db: Session = Depends(get_db), api_key: str = Depends(verify_admin_key)):
    """
    Mendapatkan statistik model dan status database untuk Admin Dashboard.
    """
    try:
        total_stocks = len(LQ45_STOCKS)
        trained_count = db.query(Screening).filter(Screening.is_trained == True).count()
        trained_stocks = [s.stock_code for s in db.query(Screening).filter(Screening.is_trained == True).all()]
        
        # Check files on disk
        models_dir = "models/saved_models"
        model_files = []
        if os.path.exists(models_dir):
            model_files = [f for f in os.listdir(models_dir) if f.endswith(".pkl")]
            
        return {
            "timestamp": datetime.now().isoformat(),
            "total_lq45_configured": total_stocks,
            "trained_stocks_in_db": trained_count,
            "trained_stocks_list": trained_stocks,
            "model_files_on_disk": len(model_files),
            "database_status": "connected"
        }
    except Exception as e:
        logger.error(f"Error in /admin/status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
