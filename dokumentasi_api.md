# 📘 Dokumentasi Integrasi API: Stock Screening System LQ45 (v5.1)

Dokumentasi ini berisi rincian **semua endpoint aktif** di backend Python AI Engine, lengkap dengan **Struktur JSON Response** untuk mempermudah integrasi Frontend Laravel.

> ⚠️ **PENTING:** Semua data screening, fundamental, teknikal, dan sentimen sudah tersimpan di database MySQL Python. Frontend Laravel **tidak** perlu melakukan perhitungan apapun — cukup panggil endpoint lalu tampilkan datanya.

---

## 1. Standar Integrasi & Keamanan

| Item | Nilai |
|---|---|
| **Base URL** | `http://127.0.0.1:8000` |
| **Format Response** | JSON |
| **Auth Publik** | Tidak perlu API Key |
| **Auth Admin** | Header `X-API-Key: [API_KEY]` |
| **CORS** | Sudah diaktifkan untuk `localhost:3000` dan `localhost:8000` |

---

## 2. Endpoint Publik (Tanpa API Key)

### 🏠 2.1 Health Check
`GET /`

Gunakan endpoint ini untuk mengecek apakah Python Engine sedang online atau offline.

**Response JSON:**
```json
{
  "status": "healthy",
  "timestamp": "2026-05-20T06:00:00",
  "database": "connected",
  "trained_models_count": 63,
  "version": "4.0.0"
}
```

**Cara pakai di Laravel:** Panggil setiap 60 detik via Alpine.js untuk menampilkan indikator "Engine Online/Offline" di header.

---

### 🚀 2.2 Realtime Stock Prices (Landing Page)
`GET /public/realtime`

Mengambil harga saham terkini dari Yahoo Finance (auto-cache 5 menit). Cocok untuk landing page marquee/ticker.

**Response JSON (Array):**
```json
[
  {
    "stock_code": "BBRI.JK",
    "company_name": "Bank Rakyat Indonesia",
    "current_price": 4500.00,
    "prev_close": 4450.00,
    "daily_change": 50.00,
    "daily_change_pct": 1.12,
    "volume": 125000000.0,
    "last_updated": "2026-05-20T15:30:00"
  }
]
```

---

### 📊 2.3 Screening Leaderboard (Tabel Utama)
`GET /public/screening`

Daftar seluruh saham yang sudah di-training AI, **diurutkan dari skor tertinggi**. Ini adalah endpoint utama untuk halaman Screening.

**Response JSON (Array):**
```json
[
  {
    "stock_code": "BBRI.JK",
    "company_name": "Bank Rakyat Indonesia",
    "current_price": 4500.00,
    "fair_value": 5200.00,
    "upside_potential": 15.55,
    "margin_of_safety": {
      "percentage": 15.55,
      "level": "Safe",
      "action": "Buy"
    },
    "recommendation": "STRONG BUY",
    "final_score": 82.5,
    "fundamental_score": 85.0,
    "technical_score": 75.0,
    "sentiment_score": 80.0,
    "sentiment_label": "Positive",
    "news_analyzed": 10,
    "quality_passed": true,
    "raw_metrics": {
      "roe": 15.50,
      "per": 12.30,
      "rsi": 45.50
    },
    "summary_rationale": "Rekomendasi STRONG BUY (Score: 82.5). Fundamental: Positive, Teknikal: Positive, Sentimen: Positive.",
    "last_updated": "2026-05-20T15:30:00"
  }
]
```

**Catatan untuk Laravel:** Field `raw_metrics` berisi ringkasan ROE, PER, dan RSI untuk ditampilkan langsung di tabel list tanpa perlu membuka halaman detail.

---

### 📈 2.4 Detail Analisis Saham (Halaman Detail)
`GET /public/analyze/{stock_code}`

**Endpoint terpenting.** Mengembalikan laporan lengkap 3 Pilar (Fundamental, Teknikal, Sentimen) beserta seluruh angka perhitungan mentahnya. Satu panggilan ini sudah cukup untuk merender seluruh halaman detail saham.

> Parameter `{stock_code}` menerima format `BBRI.JK` atau `BBRI` (otomatis ditambahkan `.JK`).

**Response JSON:**
```json
{
  "stock_code": "BBRI.JK",
  "company_name": "Bank Rakyat Indonesia",
  "current_price": 4500.00,
  "recommendation": "STRONG BUY",
  "final_score": 82.5,

  "fundamental": {
    "score": 85.0,
    "status": "Safe",
    "raw_metrics": {
      "roe": 15.50,
      "per": 12.30,
      "der": 1.20,
      "eps": 350.50,
      "dividend_yield": 0.0450
    },
    "details": {
      "fair_value": 5200.00,
      "upside": 15.55,
      "valuation_status": "Undervalued",
      "valuation_methods_used": ["PER", "PBV"],
      "valuation_method_weights": {"PER": 0.6, "PBV": 0.4},
      "quality_passed": true,
      "quality_reasons": []
    },
    "rationale": "Saham Bank Rakyat Indonesia memiliki status valuasi Undervalued dengan Upside Potential 15.55%. Hasil pemeriksaan kualitas fundamental: LULUS."
  },

  "technical": {
    "score": 75.0,
    "status": "Positive",
    "raw_indicators": {
      "rsi": 45.50,
      "macd": 1.2500,
      "ma20": 4450.00,
      "ma50": 4300.00
    },
    "details": {
      "prediction_trend": "Bullish"
    },
    "rationale": "Skor teknikal terprediksi AI adalah 75.0/100. Tren indikasi teknikal jangka menengah menunjukkan sinyal hibrida."
  },

> **📌 Catatan `technical.score` untuk Developer:**
> Nilai ini adalah **probabilitas BUY** dari ML Classifier (Random Forest + XGBoost + Logistic Regression ensemble), bukan angka abstrak.
> - Score **≥ 70** → Classifier dominan prediksi BUY → tampilkan badge `Bullish` (hijau)
> - Score **40–69** → Sinyal campuran → tampilkan badge `Neutral` (kuning)
> - Score **< 40** → Classifier dominan prediksi HOLD/SELL → tampilkan badge `Bearish` (merah)
> 
> Model dilatih dengan 22 fitur: return, MA5/20/50, RSI, MACD, Bollinger Bands, volume_ratio, OBV, ATR, golden_cross, sentiment_score, ROE, PER, DER, EPS, dividend.

  "sentiment": {
    "score": 80.0,
    "status": "Positive",
    "details": {
      "news_analyzed": 10,
      "top_headlines": [
        "BBRI Cetak Laba Rekor Sepanjang Masa",
        "Dividen Jumbo BBRI Siap Dibagikan",
        "Analis: BBRI Masih Undervalued"
      ]
    },
    "rationale": "Sentimen pasar berlabel Positive berdasarkan analisis 10 artikel berita terbaru."
  },

  "summary_rationale": "Rekomendasi STRONG BUY (Score: 82.5). Fundamental: Positive, Teknikal: Positive, Sentimen: Positive. Faktor pendorong utama adalah valuasi harga wajar Rp5200.",
  "last_updated": "2026-05-20T15:30:00"
}
```

### Peta Penggunaan Data di Halaman Detail

| Data JSON | Digunakan Untuk |
|---|---|
| `fundamental.score` | Gauge chart skor fundamental |
| `fundamental.raw_metrics.*` | Tabel ROE, PER, DER, EPS, Dividend Yield |
| `fundamental.details.fair_value` | Kartu Harga Wajar |
| `fundamental.details.upside` | Badge Upside Potential |
| `fundamental.details.valuation_status` | Badge Undervalued/Overvalued |
| `fundamental.details.quality_passed` | Indikator kualitas (hijau/merah) |
| `technical.score` | Gauge chart skor teknikal |
| `technical.raw_indicators.*` | Tabel RSI, MACD, MA20, MA50 |
| `technical.details.prediction_trend` | Badge Bullish/Bearish |
| `sentiment.score` | Gauge chart skor sentimen |
| `sentiment.details.news_analyzed` | Jumlah berita dianalisis |
| `sentiment.details.top_headlines` | Daftar judul berita |
| `sentiment.status` | Label Positive/Negative/Neutral |
| `summary_rationale` | Paragraf narasi AI |

---

## 3. Endpoint Admin (Wajib Header `X-API-Key`)

### ⚙️ 3.1 System Status
`GET /admin/status`

Statistik sistem: berapa saham terdaftar, berapa yang sudah di-training.

**Response JSON:**
```json
{
  "timestamp": "2026-05-20T15:30:00",
  "total_lq45_configured": 63,
  "trained_stocks_in_db": 63,
  "trained_stocks_list": ["AADI.JK", "ADRO.JK", "BBRI.JK", "..."],
  "model_files_on_disk": 189,
  "database_status": "connected"
}
```

---

### 🤖 3.2 Trigger Training
`POST /admin/train?stock_code=ALL`

Memulai proses training AI untuk semua saham di background. Kirim `stock_code=BBRI.JK` untuk training individual.

**Response JSON:**
```json
{
  "status": "started",
  "message": "Training massal untuk semua (63) saham LQ45 telah dimulai di background."
}
```

**Error jika training sudah berjalan (HTTP 400):**
```json
{
  "detail": "Ada proses training yang sedang berjalan. Mohon tunggu."
}
```

---

### ⏳ 3.3 Training Progress (Polling)
`GET /admin/training-status`

Polling endpoint ini setiap 2-3 detik untuk menampilkan progress bar di dashboard admin.

**Response JSON (saat running):**
```json
{
  "status": "running",
  "progress": 15,
  "total": 63,
  "current_stock": "BBRI.JK",
  "logs": [
    "Memulai training untuk 63 saham...",
    "[1/63] Memulai training saham AADI.JK...",
    "✓ Saham AADI.JK sukses dilatih dan disimpan ke DB.",
    "[15/63] Memulai training saham BBRI.JK..."
  ]
}
```

**Response JSON (saat idle / selesai):**
```json
{
  "status": "idle",
  "progress": 0,
  "total": 0,
  "current_stock": "",
  "logs": ["Proses training massal selesai!"]
}
```

**Cara menghitung persentase di Laravel:**
```javascript
let percentage = Math.round((data.progress / data.total) * 100);
```

---

## 4. Tabel Database Python (Referensi)

Tabel-tabel berikut ada di **database MySQL Python** (`python_api_db`). Laravel **tidak** perlu membuat migrasi untuk tabel-tabel ini, tapi perlu tahu strukturnya untuk memahami data yang dikembalikan API.

### 4.1 `screenings` — Hasil Screening AI
| Kolom | Tipe | Keterangan |
|---|---|---|
| stock_code | VARCHAR(20) PK | Kode saham (misal: BBRI.JK) |
| company_name | VARCHAR(100) | Nama perusahaan |
| current_price | FLOAT | Harga terakhir |
| fair_value | FLOAT | Harga wajar hasil kalkulasi |
| upside_potential | FLOAT | Persentase potensi kenaikan |
| mos_percentage | FLOAT | Margin of Safety (%) |
| mos_level | VARCHAR(50) | Level keamanan (Safe/Risky) |
| mos_action | VARCHAR(100) | Aksi rekomendasi (Buy/Hold/Sell) |
| valuation_status | VARCHAR(50) | Status valuasi (Undervalued/Overvalued) |
| recommendation | VARCHAR(50) | Rekomendasi akhir (STRONG BUY, dll) |
| final_score | FLOAT | Skor akhir gabungan (0-100) |
| fundamental_score | FLOAT | Skor fundamental (0-100) |
| technical_score | FLOAT | Skor teknikal (0-100) |
| sentiment_score | FLOAT | Skor sentimen (0-100) |
| fund_roe, fund_per, fund_der, fund_eps, fund_dividend | FLOAT | Data fundamental mentah dari CSV |
| tech_rsi, tech_macd, tech_ma20, tech_ma50 | FLOAT | Indikator teknikal mentah |
| is_trained | BOOLEAN | Apakah model sudah dilatih |
| last_updated | DATETIME | Terakhir diperbarui |

### 4.2 `news_sentiments` — Berita & Pelabelan Sentimen
| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INT PK | Auto increment |
| stock_code | VARCHAR(20) | Kode saham |
| title | VARCHAR(255) | Judul berita |
| date | VARCHAR(100) | Tanggal berita |
| source | VARCHAR(100) | Sumber berita |
| url | TEXT | Link ke berita asli |
| description | TEXT | Cuplikan isi berita |
| sentiment_score | FLOAT | Skor sentimen (0.0 - 1.0) |
| sentiment_label | VARCHAR(50) | Label: Positive / Negative / Neutral |

### 4.3 `stock_prices_realtime` — Cache Harga Real-time
| Kolom | Tipe | Keterangan |
|---|---|---|
| stock_code | VARCHAR(20) PK | Kode saham |
| company_name | VARCHAR(100) | Nama perusahaan |
| current_price | FLOAT | Harga terakhir |
| prev_close | FLOAT | Harga penutupan sebelumnya |
| daily_change | FLOAT | Perubahan harga (Rp) |
| daily_change_pct | FLOAT | Perubahan harga (%) |
| volume | FLOAT | Volume transaksi |
| last_updated | DATETIME | Terakhir diperbarui |

---

**Dokumentasi Versi 5.1** | *Diperbarui: 20 Mei 2026*
