# Rangkuman Project: Stock Screening System LQ45 (Python API)

Proyek ini adalah sebuah sistem *screening* saham untuk indeks LQ45 yang dibangun menggunakan Python. Sistem ini mengintegrasikan pengumpulan data pasar secara real-time, analisis fundamental, analisis sentimen berita (NLP), dan prediksi harga saham menggunakan Machine Learning. Sistem ini menyediakan antarmuka berbasis API menggunakan FastAPI dan menyimpan data dalam database MySQL.

Berikut adalah analisis dan rangkuman dari masing-masing komponen utama dalam proyek ini:

## 1. File Utama (Root Directory)
*   **`run.py`**: Merupakan *entry point* utama berbasis CLI (Command Line Interface). File ini memberikan menu interaktif bagi pengguna untuk:
    1. Menjalankan server API (FastAPI).
    2. Menjalankan proses pengumpulan data saja.
    3. Menjalankan *pipeline* pelatihan model (Training).
    4. Menjalankan prediksi secara *batch*.
*   **`setup.py`**: Skrip instalasi untuk menyiapkan *environment*. Skrip ini bertugas menginstal paket-paket dari `requirements.txt`, mengunduh korpus NLTK yang dibutuhkan untuk NLP, membuat direktori yang diperlukan, dan menguji modul-modul yang diinstal.
*   **`train_all_lq45.py`**: Skrip khusus untuk melakukan pelatihan model secara massal (*batch training*) untuk seluruh saham LQ45 sekaligus. Skrip ini juga secara otomatis akan membuat visualisasi/grafik akurasi dari berbagai algoritma Machine Learning yang digunakan (seperti Random Forest, XGBoost, Linear Regression, dan Ensemble).
*   **`requirements.txt`**: Daftar dependensi Python yang dibutuhkan, mencakup *library* data science (pandas, numpy, scikit-learn, xgboost), *deep learning*/NLP (transformers, torch, nltk), *web framework* (fastapi, uvicorn), *database* (sqlalchemy, pymysql), dan *web scraping* (beautifulsoup4).

## 2. Direktori `api/` (Aplikasi FastAPI)
Direktori ini berisi kode untuk server API yang siap untuk *production* (Production Ready V4.0).
*   **`main.py`**: File utama aplikasi FastAPI. Mengatur *routing*, CORS, *middleware*, dan *startup event* untuk koneksi database. File ini juga menyediakan *endpoints legacy* yang tampaknya dirancang untuk kompatibilitas mundur dengan *frontend* berbasis Laravel.
*   **`database.py`**: Berisi konfigurasi dan koneksi ke database MySQL menggunakan SQLAlchemy.
*   **`routers/`**: Direktori yang memisahkan endpoint API menjadi modul-modul terpisah (misalnya `public` untuk akses publik dan `admin` untuk fungsi manajemen/pelatihan dengan proteksi API Key).

## 3. Direktori `services/` (Core Logic)
Ini adalah jantung dari sistem yang berisi berbagai layanan (services) untuk memproses data:
*   **`data_collector.py`**: Bertugas mengambil data historis harga saham (kemungkinan via Yahoo Finance) dan data fundamental.
*   **`feature_engineering.py`**: Melakukan pemrosesan data, menggabungkan data fundamental, dan membuat fitur-fitur teknikal yang akan dimasukkan ke dalam model ML.
*   **`fundamental_analysis.py`**: Melakukan perhitungan nilai wajar (*fair value*), potensi kenaikan (*upside potential*), dan *margin of safety*.
*   **`ml_model.py`**: Mendefinisikan arsitektur model Machine Learning (StockPredictor), melatih model, dan melakukan evaluasi performa (MAE, RMSE, R2).
*   **`sentiment_analysis.py`**: Melakukan analisis sentimen terhadap berita-berita terkait saham menggunakan NLP.
*   **`screening_service.py`**: Layanan orkestrasi yang menggabungkan hasil dari model ML, fundamental, dan sentimen menjadi skor akhir (Screening Score) lalu menyimpannya ke database.

## 4. Direktori `models/` (Struktur Data & Model ML)
*   **`db_models.py`**: Mendefinisikan struktur tabel database menggunakan SQLAlchemy ORM (seperti tabel `Screening`, `NewsSentiment`, dan `StockPriceRealtime`).
*   **`saved_models/`**: Direktori tempat menyimpan model Machine Learning yang telah dilatih (dalam format `.pkl`) beserta metadatanya agar bisa digunakan sewaktu-waktu tanpa harus melatih ulang.
*   **`charts/`**: Direktori keluaran (output) untuk menyimpan grafik visualisasi performa model yang di-generate oleh `train_all_lq45.py`.

## 5. Direktori `config/` & `utils/`
*   **`config/constants.py` dkk**: Menyimpan pengaturan konfigurasi global, konstanta, dan mungkin memuat variabel lingkungan (*environment variables* seperti `API_PORT`, `LQ45_STOCKS`, dll).
*   **`utils/helpers.py` & `preprocessing.py`**: Kumpulan fungsi-fungsi bantuan dan utilitas prapemrosesan data yang sering digunakan di berbagai bagian aplikasi.

## Kesimpulan
Proyek ini memiliki arsitektur yang cukup matang dan modular. Pemisahan antara *data collection*, *machine learning*, *business logic*, dan antarmuka API dilakukan dengan baik. Sistem ini juga dirancang untuk dapat melayani *request* secara cepat dengan melakukan prapelatihan model dan prapemrosesan data fundamental dan harga yang disimpan di database MySQL.
