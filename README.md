# Stock Screening System LQ45 (API)

Sistem *screening* saham untuk indeks LQ45 menggunakan Python (FastAPI), Machine Learning, NLP (Analisis Sentimen), dan database MySQL.

## Persyaratan Sistem (Prerequisites)

Sebelum menjalankan proyek ini di komputer/laptop lain, pastikan perangkat tersebut sudah memiliki perangkat lunak berikut:

1. **Python 3.9+**: [Download Python](https://www.python.org/downloads/)
2. **Git**: [Download Git](https://git-scm.com/downloads)
3. **MySQL Server** (Misalnya melalui XAMPP atau WAMP): Untuk menjalankan database MySQL lokal.
4. **C++ Build Tools** (Khusus OS Windows): Terkadang dibutuhkan saat proses kompilasi *library* data science oleh `pip`.

---

## Panduan Instalasi dan Menjalankan Proyek

Ikuti langkah-langkah di bawah ini secara berurutan:

### 1. Clone Repositori (Unduh Proyek)
Buka terminal (Command Prompt / PowerShell / Git Bash) di folder/direktori tempat Anda ingin menaruh proyek ini, lalu jalankan:
```bash
git clone https://github.com/ferlindo45/backend_screening.git
cd backend_screening
```

### 2. Konfigurasi Database MySQL
1. Nyalakan server MySQL Anda (Jika Anda menggunakan XAMPP, tekan tombol **Start** pada modul MySQL di *XAMPP Control Panel*).
2. Sistem ini dirancang untuk **secara otomatis** mencoba membuat database bernama `python_api_db` beserta seluruh tabelnya ketika dijalankan pertama kali. Anda hanya perlu memastikan informasi *login* MySQL-nya sudah benar di tahap selanjutnya.

### 3. Konfigurasi Environment Variables (`.env`)
Duplikasi file pengaturan bawaan (Jika di Windows, Anda bisa melakukan *copy-paste* file `.env.example` lalu me-rename hasilnya menjadi `.env`). Jika melalui terminal:
```bash
cp .env.example .env
```
Buka file `.env` yang baru dibuat dengan teks editor (seperti Notepad atau VS Code). Sesuaikan pengaturan di bagian *Database* jika konfigurasi MySQL Anda berbeda (secara default di XAMPP, password kosong):
```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=python_api_db
```

### 4. Setup Python Environment dan Dependensi
Sangat direkomendasikan menggunakan *Virtual Environment* agar dependensi/library Python proyek ini tidak bentrok dengan proyek lain di laptop Anda.

1. **Buat virtual environment:**
   ```bash
   python -m venv .venv
   ```
2. **Aktifkan virtual environment:**
   * **Windows (Command Prompt):**
     ```cmd
     .\.venv\Scripts\activate.bat
     ```
   * **Windows (PowerShell):**
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   * **Mac/Linux:**
     ```bash
     source .venv/bin/activate
     ```

3. **Install Dependensi & Konfigurasi Awal:**
   Pastikan Anda sudah mengaktifkan *venv* (biasanya ada tanda `(.venv)` di awal baris terminal). Lalu jalankan skrip instalasi yang akan menginstal seluruh *library*, mengunduh data NLTK (untuk NLP), dan membuat folder yang dibutuhkan:
   ```bash
   python setup.py
   ```

### 5. Menjalankan Aplikasi
Proyek ini memiliki menu interaktif berbasis teks (CLI). Untuk menjalankannya, ketik:
```bash
python run.py
```

Anda akan melihat menu seperti berikut:
```text
============================================================
STOCK SCREENING SYSTEM LQ45
============================================================

Options:
1. Run API Server (FastAPI)
2. Run Data Collection Only
3. Run Training Pipeline
4. Run Batch Prediction
5. Exit
```

*   Pilih **opsi `1`** lalu tekan Enter untuk menyalakan Server API.
*   Server akan berjalan dan bisa diakses di `http://localhost:8000`.
*   Untuk melihat dan menguji *Endpoint* API secara langsung, buka dokumentasi interaktif Swagger UI di `http://localhost:8000/docs`.

---

## Pelatihan Model Massal (Opsional)
Jika Anda ingin melatih model Machine Learning untuk **seluruh 45 saham LQ45 secara langsung** dan membuat grafik evaluasinya, buka terminal baru (jangan lupa aktifkan `.venv`), lalu jalankan:
```bash
python train_all_lq45.py
```
*(Catatan: Proses ini membutuhkan waktu beberapa menit tergantung kecepatan komputer dan koneksi internet Anda).*

---

## Troubleshooting Umum (Penyelesaian Masalah)
*   **Error `pip install` (Building wheel failed):** Ini umum terjadi di Windows. Solusinya, *download* dan *install* [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/), centang "Desktop development with C++", lalu coba ulangi `python setup.py`.
*   **Database Error (Access Denied / Cannot Connect):** Periksa kembali isian `MYSQL_USER` dan `MYSQL_PASSWORD` di file `.env`. Pastikan server MySQL di XAMPP benar-benar sedang berjalan (berwarna hijau).
*   **Peringatan *Execution Policy* di PowerShell:** Jika muncul teks merah saat mengaktifkan *venv* di PowerShell, buka PowerShell dengan mode **Run as Administrator**, lalu ketik `Set-ExecutionPolicy Unrestricted -Force`. Setelah itu coba aktifkan lagi.

  
