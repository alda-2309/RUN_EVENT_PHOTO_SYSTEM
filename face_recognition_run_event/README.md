# MUTI - Face Recognition Photo Search

Sistem pencarian foto berbasis pengenalan wajah untuk event lari. Upload selfie, aplikasi akan mencari foto Anda di galeri event.

## Tech Stack

- **Backend**: Django 4.2 + Djongo (MongoDB Atlas)
- **AI**: DeepFace (Facenet) + MTCNN face detector
- **Database**: MongoDB Atlas
- **Cache**: Redis

## Persiapan

### 1. Clone Repository

```bash
git clone https://github.com/ElvinMustianto/muti.git
cd muti
```

### 2. Buat Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
```

### 3. Install Dependencies

```bash
pip install django==4.2
pip install djongo==1.2.31
pip install deepface
pip install mtcnn
pip install opencv-python
pip install pymongo
pip install redis
pip install numpy
pip install Pillow
pip install django-redis
```

### 4. Install Redis (diperlukan untuk caching)

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt install redis-server
sudo systemctl start redis
```

**Windows:**
Download dari https://redis.io/download, lalu jalankan `redis-server.exe`

### 5. Jalankan Server

```bash
python manage.py runserver 0.0.0.0:8000
```

Buka browser: **http://localhost:8000**

## Cara Penggunaan

1. Buka halaman utama di browser
2. Upload foto selfie Anda
3. Tunggu proses pencarian
4. Lihat hasil foto yang mirip dengan wajah Anda
5. Klik foto untuk melihat detail event

## Struktur Project

```
muti/
├── core/                    # Settings Django
│   ├── settings.py          # Konfigurasi utama
│   ├── urls.py              # URL routing
│   └── mongo_db.py          # Koneksi MongoDB
├── photos/                  # App utama
│   ├── views.py             # Logic pencarian wajah
│   ├── models.py            # Model data
│   ├── templates/           # Template HTML
│   └── admin.py             # Admin panel
├── media/                   # Folder foto & crops
│   ├── lomba_lari/          # Foto event lari
│   └── face_crops/          # Hasil crop wajah
├── manage.py
└── batch_embeddings.py      # Script batch generate embedding
```

## Environment Variables

MongoDB Atlas connection sudah dikonfigurasi di `core/mongo_db.py`. Jika ingin mengganti, edit file tersebut:

```python
MONGO_URI = 'mongodb+srv://<user>:<password>@<cluster>.mongodb.net/<database>'
```

Koneksi default semua script (batch, benchmark, OCR) diarahkan ke **MongoDB Atlas clustermuti**
sebagai sumber kebenaran. Bisa di-override via env var `MONGO_URI` (misal untuk ngetes local):

```bash
# pakai local (kalau mau testing)
set MONGO_URI=mongodb://localhost:27017
python batch_embeddings.py

# default: Atlas
python batch_embeddings.py
```

## Sinkronisasi Data (Local <-> Atlas)

Data di database `db_tugasakhir` disinkronkan dua arah antara local MongoDB dan Atlas clustermuti.
Script di root proyek (bukan di folder ini):

- `sync_mongo.py` — gabung semua collection foto & embedding dari local + Atlas (union, tidak menghapus
  data), tulis ke Atlas lalu mirror ke local. Juga menyalin collection web app (events, users, galeri, dll)
  dari Atlas ke local.
- `backup_mongo.py` — dump seluruh collection local + Atlas ke `backup/mongo_backup_<timestamp>/` (JSON).
- `migrate_local_to_atlas.py` — utilitas narik data `photos_photoevent` dari local ke Atlas (hanya yang
  belum ada, tanpa menghapus).

Jalankan backup dulu sebelum sync:

```bash
python backup_mongo.py
python sync_mongo.py
```

## Notes

- Foto event harus diletakkan di `media/lomba_lari/<nama_event>/`
- Embedding wajah di-generate via script `batch_embeddings.py`
- Threshold similarity default: 50% (bisa diatur di `photos/views.py`)
