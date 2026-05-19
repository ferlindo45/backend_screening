# Analisis Proyek: Stock Screening System LQ45

## 1. Penjelasan Proyek
Proyek ini adalah sistem screening saham untuk indeks LQ45 di Bursa Efek Indonesia (BEI). Sistem ini menggabungkan Analisis Teknikal, Fundamental, dan Sentimen menggunakan Machine Learning.

**Fitur Utama:**
- **Data Collection:** Mengambil data historis dan fundamental dari Yahoo Finance (`yfinance`).
- **Sentiment Analysis:** Mengambil berita dari Google News RSS dan menganalisis sentimen menggunakan model BERT (Transformers) dan algoritma berbasis aturan (Rule-based) dalam Bahasa Indonesia.
- **Machine Learning:** Memprediksi return saham menggunakan model Random Forest/XGBoost berdasarkan fitur teknikal dan fundamental.
- **API Server:** Dibangun dengan FastAPI, mendukung caching, monitoring sistem (`psutil`), dan proteksi API Key.

---

## 2. Kekurangan & Rekomendasi (Koreksi)

### A. Struktur Kode & Konfigurasi
*   **Masalah:** Variabel seperti `COMPANY_NAMES` dan `NEGATIVE_KEYWORDS` di `api/main.py` sangat panjang dan membuat file sulit dibaca.
*   **Koreksi:** Pindahkan pemetaan nama perusahaan dan kamus sentimen ke file konfigurasi terpisah (misalnya `config/constants.py`) atau simpan di database/JSON.

### B. Kualitas Data (Reliability)
*   **Masalah:** Fungsi `get_fundamental_data` mengembalikan data "dummy" jika Yahoo Finance gagal. Ini berbahaya karena model akan memberikan prediksi berdasarkan data palsu.
*   **Koreksi:** Implementasikan logging yang lebih ketat atau gunakan sumber data cadangan. Jangan memberikan rekomendasi "BUY/SELL" jika data fundamental yang digunakan adalah data dummy.

### C. Efisiensi & Performa
*   **Masalah:** Pengambilan data berita dan harga dilakukan secara berurutan untuk setiap request. Meskipun menggunakan `run_in_threadpool`, ini bisa menjadi bottleneck jika banyak pengguna mengakses bersamaan.
*   **Koreksi:** Gunakan `asyncio.gather` untuk menjalankan request I/O secara paralel. Optimalkan `lru_cache` agar lebih efektif.

### D. Manajemen Model (Memory Usage)
*   **Masalah:** Semua model (45+ saham) dimuat ke memori saat startup. Jika model cukup besar, ini akan memakan banyak RAM.
*   **Koreksi:** Pertimbangkan untuk memuat model secara "on-demand" dengan cache terbatas atau menggunakan model tunggal yang di-train secara global untuk seluruh LQ45 (Global Model).

### E. Keamanan
*   **Masalah:** API Key didefinisikan secara default di kode (`your-secret-api-key-here`).
*   **Koreksi:** Selalu gunakan `.env` dan jangan pernah menyertakan key default di source code.

---

## 3. Saran Pengembangan Selanjutnya
1.  **Database Integration:** Gunakan database (PostgreSQL/MongoDB) untuk menyimpan hasil screening harian daripada mengandalkan cache memori saja.
2.  **Dashboard UI:** Buat antarmuka web (React/Next.js) untuk memvisualisasikan hasil screening.
3.  **Backtesting:** Tambahkan modul untuk menguji seberapa akurat prediksi model terhadap data masa lalu.
