# 📘 Dokumentasi Integrasi API: Stock Screening System LQ45 (Full Data Schema)

Dokumentasi ini berisi rincian **15 Endpoint** lengkap dengan **Struktur JSON Response** untuk mempermudah integrasi Frontend Laravel 13.

---

## 1. Standar Integrasi & Keamanan

- **Base URL:** `http://127.0.0.1:8000`
- **Header Wajib:** 
  - `X-API-Key: [API_KEY_ANDA]`
  - `Accept: application/json`

---

## 2. Katalog Lengkap 15 Endpoint (JSON Schema)

### 🚀 1. Full Comprehensive Analysis
`GET /analyze/{stock_code}`
*Laporan lengkap 3 Pilar (Fundamental 50%, Teknikal 30%, Sentimen 20%).*

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "company_name": "Bank Rakyat Indonesia",
  "current_price": 4500.0,
  "recommendation": "STRONG BUY",
  "final_score": 82.5,
  "fundamental": {
    "score": 85.0,
    "status": "Positive",
    "details": {
      "fair_value": 5200.0,
      "upside": 15.5,
      "per": 12.5,
      "pbv": 2.1,
      "roe": 18.2,
      "der": 0.8,
      "industry_benchmarking": { "status": "BETTER", "sector_avg_roe": 14.5 }
    },
    "rationale": "..."
  },
  "technical": {
    "score": 70.0,
    "status": "Positive",
    "details": {
      "rsi": 45.2,
      "macd": "Bullish",
      "trend": "Bullish",
      "support": 4300.0,
      "resistance": 4700.0,
      "risk": { "volatility_annual": 25.4, "risk_level": "Low" }
    },
    "rationale": "..."
  },
  "sentiment": {
    "score": 90.0,
    "status": "Positive",
    "details": { "news_count": 12, "top_headlines": ["...", "..."] },
    "rationale": "..."
  },
  "summary_rationale": "...",
  "last_updated": "2024-05-15T22:30:00"
}
```

---

### 📊 2. Batch Predict (Dashboard Overview)
`GET /batch-predict?stock_codes=BBRI.JK,TLKM.JK`
*Analisis massal untuk dashboard utama.*

**Response JSON:**
```json
{
  "timestamp": "2024-05-15T22:30:00",
  "total_stocks_analyzed": 2,
  "results": [
    {
      "stock_code": "BBRI.JK",
      "predicted_return": 0.015,
      "sentiment_score": 0.75,
      "sentiment_label": "Positive",
      "news_analyzed": 10,
      "final_score": 82.5,
      "recommendation": "STRONG BUY",
      "is_dummy_data": false
    }
  ]
}
```

---

### 📈 3. Deep Fundamental Analysis
`GET /fundamental-analysis/{stock_code}`
*Detail metrik keuangan mendalam.*

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "current_price": 4500.0,
  "eps_ttm": 450.0,
  "per_ttm": 10.0,
  "roe": 18.2,
  "pbv": 2.1,
  "fair_value": 5200.0,
  "upside_potential": 15.5,
  "margin_of_safety": { "percentage": 15.5, "level": "Safe", "action": "Buy" },
  "fundamental_recommendation": { "score": 85, "label": "Positive" },
  "sector": "Financial",
  "last_updated": "..."
}
```

---

### 💎 4. Fair Value & Valuation Details
`GET /fair-value/{stock_code}`
*Perbandingan berbagai metode perhitungan harga wajar.*

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "current_price": 4500.0,
  "fair_value": 5200.0,
  "fair_value_dcf": 5300.0,
  "fair_value_per": 5100.0,
  "fair_value_pbv": 4900.0,
  "fair_value_ddm": 5050.0,
  "valuation_method_weights": { "dcf": 50, "per": 30, "pbv": 20 },
  "margin_of_safety": { "percentage": 15.5, "level": "High" },
  "dcf_valid": true,
  "last_updated": "..."
}
```

---

### 📰 5. Stock News Feed
`GET /stock-news/{stock_code}`
*Daftar berita beserta analisis sentimen per artikel.*

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "company_name": "Bank Rakyat Indonesia",
  "overall_sentiment_score": 0.75,
  "news_analyzed": 15,
  "news_items": [
    {
      "title": "BBRI Cetak Laba Rekor",
      "date": "2024-05-15",
      "source": "CNBC",
      "url": "http://...",
      "sentiment_score": 0.9,
      "sentiment_label": "Positive"
    }
  ]
}
```

---

### 🔍 6. Quick Stock Info
`GET /stock-info/{stock_code}`
*Data ringkas untuk sidebar atau tooltip.*

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "company_name": "Bank Rakyat Indonesia",
  "current_price": 4500.0,
  "daily_change_percent": 1.25,
  "volatility_annual": 25.4,
  "sentiment_score": 0.75,
  "latest_news": [ { "title": "...", "sentiment": "Positive" } ],
  "fundamental_metrics": { "roe": 18.2, "per": 10.0, "der": 0.8 },
  "last_updated": "..."
}
```

---

### 📢 7. Quick Sentiment Score
`GET /stock-sentiment/{stock_code}`
*Hanya skor sentimen dan jumlah berita.*

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "company_name": "Bank Rakyat Indonesia",
  "sentiment_score": 0.75,
  "sentiment_label": "Positive",
  "news_analyzed": 12,
  "last_updated": "..."
}
```

---

### 🤖 8. ML Return Prediction
`POST /predict` (Body: `{"stock_code": "BBRI.JK"}`)
*Prediksi return spesifik menggunakan model AI.*

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "predictions": { "ensemble": 0.015, "random_forest": 0.014 },
  "sentiment_score": 0.75,
  "final_score": 82.5,
  "recommendation": "STRONG BUY"
}
```

---

### 🎓 9. Train Model Pipeline
`POST /train-model` (Body: `{"stock_code": "BBRI.JK"}`)
*Melatih ulang model AI untuk saham tertentu.*

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "evaluation": {
    "random_forest": { "mae": 0.001, "rmse": 0.002, "r2": 0.85 },
    "ensemble": { "mae": 0.001, "r2": 0.87 }
  },
  "feature_importance": { "ma20": 0.15, "rsi": 0.12, "sentiment": 0.1 },
  "train_size": 450,
  "message": "Model training completed successfully"
}
```

---

### ✍️ 10. Manual Sentiment Analysis
`POST /sentiment` (Body: `{"text": "Harga saham BBCA diprediksi naik..."}`)
*Analisis sentimen teks bebas.*

**Response JSON:**
```json
{
  "text": "Harga saham BBCA diprediksi naik...",
  "sentiment": { "positive": 0.85, "neutral": 0.1, "negative": 0.05 },
  "sentiment_score": 0.8
}
```

---

### 🗄️ 11. Historical Stock Data
`GET /get-stock-data?stock_codes=BBRI.JK`
*Mengambil data historis OHLCV.*

**Response JSON:**
```json
[
  {
    "stock_code": "BBRI.JK",
    "total_records": 100,
    "data": [
      { "Date": "2024-05-15", "Open": 4450, "High": 4550, "Low": 4400, "Close": 4500, "Volume": 1000000 }
    ]
  }
]
```

---

### 📈 12. System Metrics
`GET /metrics`
*Monitoring performa server.*

**Response JSON:**
```json
{
  "models_loaded": 45,
  "sentiment_cache_size": 120,
  "price_cache_size": 45,
  "cpu_percent": 12.5,
  "memory_percent": 65.4,
  "memory_used_mb": 1200.5,
  "python_version": "3.10.x"
}
```

---

### 🧹 13. Admin: Clear Cache
`POST /admin/clear-cache`
*Membersihkan memori cache.*

**Response JSON:**
```json
{
  "status": "success",
  "message": "All caches cleared"
}
```

---

### 🛠️ 14. Debug: Feature Extraction
`GET /debug/features/{stock_code}`
*Troubleshooting tahapan ekstraksi data AI.*

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "steps": {
    "1_download": { "status": "OK", "rows": 125 },
    "2_reset_index": { "status": "OK" },
    "3_fundamental": { "status": "OK", "roe": 18.2 },
    "4_sentiment_df": { "status": "OK" },
    "5_complete_dataset": { "status": "OK" }
  },
  "success": true,
  "latest_features_shape": [1, 24]
}
```

---

### 🩺 15. Health Check
`GET /`
*Cek status ketersediaan server.*

**Response JSON:**
```json
{
  "status": "healthy",
  "timestamp": "2024-05-15T22:30:00",
  "available_models": ["BBRI.JK", "TLKM.JK", "..."],
  "models_loaded": true,
  "cache_size": 120,
  "system_stats": { "models_total": 45, "sentiment_cache": 120 }
}
```

---
**Dokumentasi Versi 4.2** | *Complete 15 Endpoints with Full Schemas*
