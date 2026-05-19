# 🧠 MASTER PROMPT — Frontend Laravel 13: Stock Screening System LQ45

> **Tujuan:** Prompt ini bersifat komprehensif dan sekali-generate-jadi. Ikuti urutan fase secara berurutan. Jangan skip fase apapun.

---

## 📐 KONTEKS SISTEM

Kamu adalah senior full-stack developer Laravel 13. Kamu sedang membangun **frontend lengkap** untuk sistem **Stock Screening LQ45 berbasis AI** yang terdiri dari 3 lapisan:

- **Layer 1 (Browser):** UI Blade + Alpine.js + Tailwind CSS
- **Layer 2 (Laravel 13):** Router, Middleware, Controller, Service, Queue, Cache
- **Layer 3 (Python AI Engine):** `http://127.0.0.1:8000` — 15 endpoint aktif

Sistem ini sudah memiliki Python AI Engine yang berjalan. Tugasmu adalah membangun **seluruh sisi Laravel** dari nol: database, service, controller, view, sampai panel admin — tanpa menyentuh engine.

---

## 🎨 DESIGN SYSTEM (WAJIB DIIKUTI)

### Palet Warna Status Saham
```
Excellent  → bg-emerald-500  → STRONG BUY   (≥ 80 score)
Good       → bg-blue-500     → ACCUMULATE   (60–79 score)
Neutral    → bg-amber-500    → HOLD         (40–59 score)
Warning    → bg-orange-500   → REDUCE       (20–39 score)
Danger     → bg-rose-500     → SELL         (< 20 score)
```

### Tema UI
- **Mode:** Dark theme dominan, background `#0f1117`, card `#1a1d27`
- **Font:** `Inter` untuk body, `JetBrains Mono` untuk angka/ticker
- **Komponen:** Tailwind CSS + Alpine.js (sudah di-inject lewat CDN atau mix)
- **Chart:** Chart.js untuk grafik harga/performa
- **Animasi:** Transisi halus 150–300ms, skeleton loading untuk data async

---

## 🗃️ FASE 1 — DATABASE & MIGRATION

Buat semua migration file berikut dengan urutan yang benar:

### 1.1 Tabel `stocks`
```
- id (bigint, PK)
- code (varchar 10, unique) → contoh: "BBCA", "TLKM"
- name (varchar 100)
- sector (varchar 50)
- is_active (boolean, default true)
- last_price (decimal 15,2, nullable)
- price_updated_at (timestamp, nullable)
- timestamps
```

### 1.2 Tabel `analysis_cache`
```
- id (bigint, PK)
- stock_code (varchar 10, indexed)
- endpoint_type (varchar 50) → nilai: 'full_analysis', 'fundamental', 'fair_value', 'news', 'sentiment', 'stock_info'
- raw_json (longtext)
- created_at (timestamp)
- expired_at (timestamp, indexed)
```
> Index composite: `(stock_code, endpoint_type)`

### 1.3 Tabel `user_portfolios`
```
- id (bigint, PK)
- user_id (FK → users)
- stock_code (varchar 10)
- stock_name (varchar 100)
- buy_price (decimal 15,2)
- quantity (integer)
- buy_date (date)
- notes (text, nullable)
- timestamps
```

### 1.4 Tabel `portfolio_snapshots`
```
- id (bigint, PK)
- user_id (FK → users)
- snapshot_date (date)
- total_invested (decimal 15,2)
- total_current_value (decimal 15,2)
- total_pnl (decimal 15,2)
- total_pnl_percent (decimal 8,4)
- detail_json (longtext) → array saham + harga saat snapshot
- timestamps
```

### 1.5 Modifikasi Tabel `users` (bawaan Laravel)
```
Tambah kolom:
- role (enum: 'user', 'admin', default 'user')
- avatar (varchar, nullable)
```

### 1.6 Seeder Data
Buat `StocksSeeder` yang mengisi **45 saham LQ45 lengkap** dengan code, name, dan sector. Gunakan data LQ45 periode terbaru (BBCA, BBRI, BMRI, TLKM, ASII, dst — lengkapi semua 45 saham).

---

## ⚙️ FASE 2 — SERVICE LAYER

### 2.1 `StockApiService` (HTTP Client ke Engine)
File: `app/Services/StockApiService.php`

```php
// Implementasi penuh berdasarkan dokumentasi API:
// Config dari: config('services.stock_engine.url') dan .key

// Method yang WAJIB ada:
getFullReport(string $code): array
getMarketOverview(?string $codes = null): array
getFundamental(string $code): array
getFairValue(string $code): array
getNews(string $code): array
getStockInfo(string $code): array
getStockSentiment(string $code): array
predict(array $data): array
trainModel(string $code): array
analyzeSentiment(string $text): array
getStockData(string $code): array
getSystemHealth(): array
clearCache(): array
getDebugFeatures(string $code): array
checkHealth(): array

// Semua method harus:
// 1. Wrap dalam try-catch
// 2. Return array dengan struktur: ['success' => bool, 'data' => ..., 'error' => string|null]
// 3. Log error via Log::error() jika gagal
// 4. Timeout 60 detik
```

### 2.2 `StockAnalysisService` (Caching Logic)
File: `app/Services/StockAnalysisService.php`

Logika cache berlapis:
```
Request data saham
  → Cek Redis cache dulu (Laravel Cache)
    HIT → return data Redis
    MISS → Cek tabel analysis_cache MySQL
      HIT (expired_at > now()) → simpan ke Redis (TTL pendek) → return
      MISS → Call StockApiService
        → Simpan ke analysis_cache MySQL
        → Simpan ke Redis
        → Return data
```

TTL per tipe data:
```
full_analysis  → MySQL: 60 menit,  Redis: 10 menit
fundamental    → MySQL: 120 menit, Redis: 15 menit
fair_value     → MySQL: 120 menit, Redis: 15 menit
news           → MySQL: 15 menit,  Redis: 5 menit
sentiment      → MySQL: 15 menit,  Redis: 5 menit
stock_info     → MySQL: 5 menit,   Redis: 2 menit
market_overview → MySQL: 30 menit, Redis: 5 menit
```

Method yang wajib ada:
```php
getFullAnalysis(string $code): array
getMarketOverview(): array
getFundamental(string $code): array
getFairValue(string $code): array
getNews(string $code): array
getStockInfo(string $code): array
getSentiment(string $code): array
invalidateCache(string $code): void  // Hapus semua cache untuk 1 saham
invalidateAllCache(): void
```

### 2.3 `PortfolioService`
File: `app/Services/PortfolioService.php`

```php
// Kalkulasi performa portfolio user
calculatePortfolioSummary(int $userId): array
// Return: total_invested, total_current_value, total_pnl, total_pnl_percent, best_performer, worst_performer

getPortfolioWithCurrentPrices(int $userId): array
// Gabungkan data portfolio dari DB + harga terkini dari StockAnalysisService

takeSnapshot(int $userId): void
// Simpan snapshot harian ke tabel portfolio_snapshots

getPerformanceHistory(int $userId, int $days = 30): array
// Ambil data portfolio_snapshots untuk chart performa
```

---

## 🚦 FASE 3 — ROUTING

File: `routes/web.php`

```php
// Public routes
Route::get('/', [DashboardController::class, 'redirect']);
Route::get('/login', ...);
Route::get('/register', ...);

// Authenticated routes
Route::middleware(['auth'])->group(function () {
    Route::get('/dashboard', [DashboardController::class, 'index'])->name('dashboard');
    
    // Stock routes
    Route::prefix('stock')->name('stock.')->group(function () {
        Route::get('/', [StockController::class, 'index'])->name('index');
        Route::get('/{code}', [StockController::class, 'show'])->name('show');
        Route::get('/{code}/fundamental', [StockController::class, 'fundamental'])->name('fundamental');
        Route::get('/{code}/fairvalue', [StockController::class, 'fairvalue'])->name('fairvalue');
        Route::get('/{code}/news', [StockController::class, 'news'])->name('news');
    });
    
    // Portfolio routes
    Route::prefix('portfolio')->name('portfolio.')->group(function () {
        Route::get('/', [PortfolioController::class, 'index'])->name('index');
        Route::post('/add', [PortfolioController::class, 'store'])->name('store');
        Route::put('/{id}', [PortfolioController::class, 'update'])->name('update');
        Route::delete('/{id}', [PortfolioController::class, 'destroy'])->name('destroy');
    });
    
    // Admin routes
    Route::middleware(['role:admin'])->prefix('admin')->name('admin.')->group(function () {
        Route::get('/dashboard', [AdminController::class, 'index'])->name('index');
        Route::get('/metrics', [AdminController::class, 'metrics'])->name('metrics');
        Route::post('/clear-cache', [AdminController::class, 'clearCache'])->name('clear-cache');
        Route::post('/train-model/{code}', [AdminController::class, 'trainModel'])->name('train-model');
        Route::get('/debug/{code}', [AdminController::class, 'debug'])->name('debug');
    });
});

// API routes (untuk AJAX request dari frontend)
Route::prefix('api')->middleware(['auth', 'throttle:60,1'])->group(function () {
    Route::get('/stock/{code}/info', [StockController::class, 'apiInfo']);
    Route::get('/market/overview', [DashboardController::class, 'apiOverview']);
    Route::post('/sentiment/analyze', [StockController::class, 'apiSentiment']);
    Route::get('/portfolio/summary', [PortfolioController::class, 'apiSummary']);
});
```

---

## 🎮 FASE 4 — CONTROLLER

### 4.1 `DashboardController`
File: `app/Http/Controllers/DashboardController.php`

```php
// Method index():
// 1. Panggil StockAnalysisService->getMarketOverview()
// 2. Sortir berdasarkan score tertinggi
// 3. Hitung statistik: berapa STRONG BUY, HOLD, SELL
// 4. Pass ke view: $stocks, $stats, $lastUpdated
// 5. Cache seluruh halaman dengan Laravel Cache (key: 'dashboard_view', ttl: 30 menit)

// Method apiOverview():
// Return JSON untuk live-update via AJAX polling setiap 5 menit
```

### 4.2 `StockController`
File: `app/Http/Controllers/StockController.php`

```php
// show($code):
// 1. Validate $code ada di tabel stocks
// 2. Panggil getFullAnalysis() — ini menghasilkan data 3 pilar lengkap
// 3. Panggil getNews() secara paralel jika memungkinkan
// 4. Pass ke view dengan tab: Overview | Fundamental | Fair Value | Berita | Sentimen

// fundamental($code), fairvalue($code), news($code):
// Digunakan jika user klik tab individual — return partial view atau JSON

// apiSentiment():
// Terima POST { text: string }
// Panggil StockApiService->analyzeSentiment()
// Return JSON { score, label, confidence }
```

### 4.3 `PortfolioController`
File: `app/Http/Controllers/PortfolioController.php`

```php
// index():
// 1. Ambil semua portfolio user dari DB
// 2. Enrich dengan harga terkini via StockAnalysisService->getStockInfo()
// 3. Kalkulasi PnL per saham dan total
// 4. Ambil performance history untuk chart

// store():
// Validasi: stock_code (exists di stocks), buy_price, quantity, buy_date
// Simpan ke user_portfolios
// Return redirect dengan flash success

// destroy($id):
// Policy check: portfolio harus milik auth user
// Soft delete atau hard delete
```

### 4.4 `AdminController`
File: `app/Http/Controllers/AdminController.php`

```php
// index():
// Overview sistem: total stocks, cache hit rate, engine status

// metrics():
// Real-time dari StockApiService->getSystemHealth()
// Return JSON jika request AJAX, view jika biasa

// clearCache():
// 1. Panggil StockApiService->clearCache() ke engine
// 2. Panggil StockAnalysisService->invalidateAllCache() (Redis + MySQL)
// 3. Return redirect dengan flash

// trainModel($code):
// Dispatch ke Queue Job: TrainModelJob
// Return immediately dengan pesan "training dimulai"
```

---

## 💼 FASE 5 — QUEUE JOBS

### 5.1 `TrainModelJob`
File: `app/Jobs/TrainModelJob.php`

```php
// Constructor: terima $stockCode
// Handle:
// 1. Log::info("Starting training for {$stockCode}")
// 2. Panggil StockApiService->trainModel($stockCode)
// 3. Setelah selesai, invalidate cache untuk stock tersebut
// 4. Kirim notifikasi (database notification) ke admin
// 5. Log::info("Training complete for {$stockCode}")

// Config: queue 'ai-training', timeout 600 detik, retry 1 kali
```

### 5.2 `RefreshDashboardCacheJob`
File: `app/Jobs/RefreshDashboardCacheJob.php`

```php
// Jalankan getMarketOverview() di background
// Paksa refresh cache (bypass existing cache)
// Queue: 'cache-refresh', timeout 120 detik

// Di-schedule setiap 30 menit via App\Console\Kernel atau routes/console.php
```

### 5.3 `TakePortfolioSnapshotJob`
File: `app/Jobs/TakePortfolioSnapshotJob.php`

```php
// Loop semua user yang punya portfolio
// Panggil PortfolioService->takeSnapshot($userId)
// Di-schedule setiap hari jam 17:00 WIB (09:00 UTC)
```

---

## 🛡️ FASE 6 — MIDDLEWARE

### 6.1 `RoleMiddleware`
File: `app/Http/Middleware/RoleMiddleware.php`

```php
// Cek $request->user()->role === 'admin'
// Jika bukan, abort(403)
// Register alias 'role' di bootstrap/app.php
```

---

## 🖥️ FASE 7 — VIEWS (BLADE)

Buat semua view dengan tema **dark, profesional, finance dashboard**. Gunakan Tailwind CSS. Setiap halaman harus ada skeleton loading state.

### 7.1 Layout Utama: `layouts/app.blade.php`

Komponen yang harus ada:
```
[Sidebar Kiri - Fixed]
  Logo + nama sistem
  Nav: Dashboard | Pasar | Portofolio
  Nav admin (kondisional)
  User avatar + nama + logout

[Header Top]
  Search bar (autocomplete saham LQ45)
  Notifikasi
  Clock WIB real-time

[Main Content Area]
  Slot konten
  
[Footer mini]
  Versi sistem | Status engine (hijau/merah)
```

Tambahkan komponen kecil di header: **indikator status engine** yang memanggil `/api/health` setiap 60 detik via Alpine.js — tampilkan dot hijau "Engine Online" atau merah "Engine Offline".

---

### 7.2 Dashboard: `dashboard/index.blade.php`

**Bagian A — Stats Bar (4 kartu)**
```
Total Saham LQ45 | STRONG BUY hari ini | Rata-rata Score Pasar | Terakhir diperbarui
```

**Bagian B — Filter & Sort**
```
Filter: Semua | STRONG BUY | ACCUMULATE | HOLD | REDUCE | SELL
Sort: Score Tertinggi | Score Terendah | Abjad A-Z | Sektor
Search: input teks filter nama/kode saham
```

**Bagian C — Grid Kartu Saham**

Setiap kartu menampilkan:
```
[Badge Sektor]         [Kode Saham] [Nama Saham]
[Badge Rekomendasi]    Score: ██████░░ 74/100
Harga: Rp 9.250        Δ +1.2%
3 Pilar Mini:
  Fundamental [████░] 82  Teknikal [███░░] 68  Sentimen [██░░░] 71
[Tombol: Detail →]
```

Kartu harus responsif: 4 kolom desktop, 2 tablet, 1 mobile.

Klik kartu → navigate ke `/stock/{code}`.

**Bagian D — Live Update**
Alpine.js polling setiap 5 menit ke `/api/market/overview` untuk refresh data tanpa reload halaman.

---

### 7.3 Detail Saham: `stock/show.blade.php`

**Header Saham**
```
Kode | Nama | Sektor
Harga terkini | Perubahan % | Badge rekomendasi
Score keseluruhan (besar, dengan progress ring)
```

**Tab Navigator**
```
[Overview] [Fundamental] [Fair Value] [Berita & Sentimen] [Data Historis]
```

**Tab 1 — Overview**
```
Score 3 Pilar:
  [Fundamental 50%] Gauge chart → score + deskripsi
  [Teknikal 30%]    Gauge chart → score + deskripsi
  [Sentimen 20%]    Gauge chart → score + deskripsi

Ringkasan AI:
  Paragraf narasi dari engine tentang kondisi saham ini

Rekomendasi Aksi:
  Box besar dengan warna status + teks rekomendasi + alasan
```

**Tab 2 — Fundamental**
```
Tabel metrik:
ROE | PER | PBV | DER | EPS | Revenue Growth | Net Profit Margin | Cashflow

Setiap metrik:
  Nama | Nilai | Benchmark Sektor | Status (hijau/kuning/merah)

Keterangan singkat tentang arti masing-masing metrik
```

**Tab 3 — Fair Value**
```
4 Metode Valuasi (card per metode):
  DCF Value        | Hasil: Rp X.XXX | Margin of Safety: +12%
  PBV Intrinsic    | Hasil: Rp X.XXX | Status: Undervalued
  DDM Value        | Hasil: Rp X.XXX | Status: Overvalued
  Excess Returns   | Hasil: Rp X.XXX | Status: Fair

Harga Pasar Sekarang vs Rata-rata Fair Value
Kesimpulan: Undervalued / Fairly Valued / Overvalued
```

**Tab 4 — Berita & Sentimen**
```
Skor Sentimen Agregat (gauge besar: Positif/Netral/Negatif)
Jumlah berita dianalisis

List berita terbaru:
  [Judul Berita] [Sumber] [Waktu]
  [Skor Sentimen per artikel: badge warna]
  [Preview 2 baris] [Tombol: Baca selengkapnya →]

Analisis Sentimen Manual:
  Textarea input teks bebas
  Tombol "Analisis"
  Hasil: score + label + confidence (muncul di bawah tanpa reload)
```

**Tab 5 — Data Historis**
```
Pilihan periode: 1M | 3M | 6M | 1Y
Chart.js line chart: Harga OHLCV
Tabel data historis dengan scroll
```

---

### 7.4 Portofolio: `portfolio/index.blade.php`

**Header Summary (4 kartu)**
```
Total Investasi | Nilai Saat Ini | Total PnL (Rp) | Total PnL (%)
Warna kartu PnL: hijau jika positif, merah jika negatif
```

**Chart Performa**
```
Line chart: nilai portfolio 30 hari terakhir
Dari tabel portfolio_snapshots
```

**Tabel Posisi**
```
Kolom: Saham | Lot/Lembar | Harga Beli | Harga Sekarang | Nilai Saat Ini | PnL Rp | PnL % | Aksi
Baris total di bawah
Inline edit: klik nilai untuk edit langsung
Tombol per baris: Edit | Hapus
```

**Modal Tambah Saham**
```
Trigger: Tombol "+ Tambah Posisi"
Form di modal:
  Dropdown autocomplete kode saham (dari tabel stocks)
  Harga Beli (Rp)
  Jumlah Lot (1 lot = 100 lembar, tampilkan auto-konversi)
  Tanggal Beli
  Catatan (opsional)
Submit via AJAX, update tabel tanpa reload
```

---

### 7.5 Admin Panel: `admin/index.blade.php`

**Bagian A — System Status**
```
Card: CPU Usage | RAM Usage | Status Model (Loaded/Not Loaded)
Data dari /metrics, auto-refresh setiap 30 detik via Alpine.js
```

**Bagian B — Cache Management**
```
Statistik cache:
  Total record di analysis_cache | Cache yang masih valid | Cache expired
  
Tombol aksi:
  [Bersihkan Semua Cache] → konfirmasi modal → POST /admin/clear-cache
  
Tabel cache per saham:
  Kode | Tipe | Dibuat | Expired | Status | Aksi (hapus per item)
```

**Bagian C — Model Training**
```
Tabel saham LQ45 dengan kolom:
  Kode | Nama | Status Model | Terakhir Dilatih | Aksi

Aksi: [Train Ulang] → dispatch TrainModelJob → tampilkan "Training dimulai..."
Filter: belum dilatih | sudah dilatih | error
```

**Bagian D — Debug Tools**
```
Input kode saham + Tombol "Debug Feature Extraction"
Tampilkan hasil JSON dari /debug/features/{code}
Format JSON tree yang bisa di-expand/collapse (Alpine.js)
```

---

## 🧩 FASE 8 — KOMPONEN BLADE REUSABLE

Buat komponen berikut sebagai Blade Components (`resources/views/components/`):

### `stock-card.blade.php`
Props: `$stock` (array dengan semua data)
Render kartu saham seperti di dashboard

### `recommendation-badge.blade.php`
Props: `$recommendation` (string: STRONG BUY, dll), `$size` (sm/md/lg)
Render badge dengan warna yang sesuai

### `score-gauge.blade.php`
Props: `$score` (0-100), `$label`, `$color`
Render semi-circle progress gauge dengan SVG

### `metric-table-row.blade.php`
Props: `$name`, `$value`, `$benchmark`, `$status`
Render satu baris tabel fundamental

### `skeleton-card.blade.php`
Render skeleton loading untuk satu stock card (animasi pulse)

### `alert-flash.blade.php`
Render flash message: success / error / warning
Auto-dismiss setelah 4 detik

---

## ⚡ FASE 9 — ALPINE.JS INTERACTIONS

Implementasikan interaksi berikut tanpa full page reload:

### Dashboard Filter & Sort
```javascript
// Alpine component: x-data="dashboardFilter()"
// State: activeFilter, sortBy, searchQuery, stocks[]
// Computed: filteredStocks berdasarkan state di atas
// Watch: searchQuery → filter nama/kode secara lokal
```

### Live Search Saham (Autocomplete)
```javascript
// Di header, input search
// Ketik 2+ karakter → fetch dari data stocks yang sudah di-pass ke JS
// Tampilkan dropdown hasil, klik → navigate ke halaman detail
```

### Tab Navigation di Detail Saham
```javascript
// x-data="{ activeTab: 'overview' }"
// Ganti konten tab tanpa reload
// Lazy load tab Fundamental, Fair Value jika belum pernah dibuka
// (fetch AJAX ke endpoint masing-masing, cache hasilnya di JS state)
```

### Analisis Sentimen Manual
```javascript
// Submit form → fetch POST ke /api/sentiment/analyze
// Tampilkan loading spinner
// Inject hasil (score, label) ke DOM tanpa reload
```

### Portfolio Inline Edit
```javascript
// Klik nilai qty/harga → transform cell jadi input
// Enter/blur → AJAX PUT /portfolio/{id}
// Update nilai PnL di baris dan total secara langsung
```

---

## 🔧 FASE 10 — KONFIGURASI

### 10.1 `config/services.php` — Tambahkan:
```php
'stock_engine' => [
    'url' => env('STOCK_ENGINE_URL', 'http://127.0.0.1:8000'),
    'key' => env('STOCK_ENGINE_API_KEY'),
],
```

### 10.2 `.env` — Tambahkan variabel:
```
STOCK_ENGINE_URL=http://127.0.0.1:8000
STOCK_ENGINE_API_KEY=your_api_key_here

# Redis untuk cache dan queue
CACHE_DRIVER=redis
SESSION_DRIVER=redis
QUEUE_CONNECTION=redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# Queue worker config
QUEUE_RETRY_AFTER=700
```

### 10.3 Scheduler di `routes/console.php`:
```php
use Illuminate\Support\Facades\Schedule;

// Refresh dashboard cache setiap 30 menit
Schedule::job(new RefreshDashboardCacheJob)->everyThirtyMinutes();

// Snapshot portfolio setiap hari jam 17:00 WIB
Schedule::job(new TakePortfolioSnapshotJob)->dailyAt('17:00')->timezone('Asia/Jakarta');

// Bersihkan cache yang sudah expired dari DB setiap jam
Schedule::call(function () {
    \DB::table('analysis_cache')->where('expired_at', '<', now())->delete();
})->hourly();
```

### 10.4 Queue Worker Setup:
```bash
# Jalankan worker untuk semua queue
php artisan queue:work redis --queue=ai-training,cache-refresh,default --timeout=700
```

---

## 📋 FASE 11 — ERROR HANDLING & FALLBACK

Terapkan strategi berikut di seluruh codebase:

### Jika Engine Offline
```
Tampilkan data dari cache lama (expired sekalipun) dengan banner:
"⚠️ Data mungkin tidak terbaru. Engine AI sedang tidak tersedia."
Tombol: "Coba Lagi"
```

### Jika Cache Kosong & Engine Offline
```
Tampilkan halaman error khusus: resources/views/errors/engine-offline.blade.php
Konten: ilustrasi, pesan ramah, tombol refresh
```

### Rate Limiting Response
```
Jika user melebihi batas API internal, tampilkan:
"Terlalu banyak permintaan. Tunggu sebentar."
Dengan countdown timer otomatis menggunakan Alpine.js
```

### Timeout Handler
```
Semua AJAX call di frontend harus punya timeout 30 detik
Jika timeout: tampilkan notifikasi toast + opsi retry
```

---

## ✅ CHECKLIST AKHIR SEBELUM SELESAI

Pastikan semua item ini sudah diimplementasikan:

**Database**
- [ ] Semua 5 migration sudah dibuat dengan benar
- [ ] Semua foreign key dan index sudah terpasang
- [ ] Seeder 45 saham LQ45 sudah lengkap

**Backend**
- [ ] `StockApiService` — semua 15 method, ada try-catch & logging
- [ ] `StockAnalysisService` — double cache layer (Redis + MySQL)
- [ ] `PortfolioService` — kalkulasi PnL & history
- [ ] Semua 4 controller sudah ada dengan method lengkap
- [ ] 3 Queue Jobs sudah ada dan terdaftar
- [ ] Scheduler sudah dikonfigurasi
- [ ] `RoleMiddleware` sudah terdaftar sebagai alias

**Frontend**
- [ ] Layout dengan sidebar, header (search + status engine), footer
- [ ] Dashboard dengan grid kartu saham + filter/sort + live update
- [ ] Detail saham dengan 5 tab dan semua konten per tab
- [ ] Portofolio dengan chart + tabel + modal tambah
- [ ] Admin panel dengan semua 4 bagian
- [ ] Semua 6 komponen Blade reusable
- [ ] Semua 5 Alpine.js interaction sudah berjalan

**Konfigurasi**
- [ ] `config/services.php` sudah diupdate
- [ ] `.env.example` sudah diupdate dengan variabel baru
- [ ] Queue dan Scheduler sudah berjalan
- [ ] Redis sudah dikonfigurasi

---

## 📁 STRUKTUR FOLDER AKHIR

```
app/
├── Http/
│   ├── Controllers/
│   │   ├── DashboardController.php
│   │   ├── StockController.php
│   │   ├── PortfolioController.php
│   │   └── AdminController.php
│   └── Middleware/
│       └── RoleMiddleware.php
├── Jobs/
│   ├── TrainModelJob.php
│   ├── RefreshDashboardCacheJob.php
│   └── TakePortfolioSnapshotJob.php
├── Models/
│   ├── Stock.php
│   ├── AnalysisCache.php
│   ├── UserPortfolio.php
│   └── PortfolioSnapshot.php
└── Services/
    ├── StockApiService.php
    ├── StockAnalysisService.php
    └── PortfolioService.php

database/
├── migrations/
│   ├── xxxx_create_stocks_table.php
│   ├── xxxx_create_analysis_cache_table.php
│   ├── xxxx_create_user_portfolios_table.php
│   └── xxxx_create_portfolio_snapshots_table.php
└── seeders/
    └── StocksSeeder.php

resources/views/
├── layouts/
│   └── app.blade.php
├── components/
│   ├── stock-card.blade.php
│   ├── recommendation-badge.blade.php
│   ├── score-gauge.blade.php
│   ├── metric-table-row.blade.php
│   ├── skeleton-card.blade.php
│   └── alert-flash.blade.php
├── dashboard/
│   └── index.blade.php
├── stock/
│   └── show.blade.php
├── portfolio/
│   └── index.blade.php
├── admin/
│   └── index.blade.php
└── errors/
    └── engine-offline.blade.php

routes/
├── web.php
└── console.php
```

---

> **📌 CATATAN UNTUK AI:**
> Generate semua file secara berurutan sesuai fase. Mulai dari Fase 1 (Migration), lanjut ke Fase 2 (Service), dst.
> Jangan skip fase apapun. Setiap file harus lengkap, bukan placeholder.
> Gunakan PHP 8.2+, Laravel 13 syntax, dan Tailwind CSS untuk semua styling.
> Dark theme dengan palet warna yang sudah ditentukan di atas wajib konsisten di semua view.