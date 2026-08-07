# LAPORAN PROYEK — RUN_EVENT_PHOTO_SYSTEM

**Website Dokumentasi Foto Event Lari** (Proyek Skripsi / Tugas Akhir)
Tanggal laporan: 2026-08-07

---

## 1. Ringkasan Eksekutif

`RUN_EVENT_PHOTO_SYSTEM` adalah aplikasi web berbasis **Django 5.2** untuk dokumentasi
foto event lari. Fitur utamanya:

1. **Galery foto publik** — browsing foto event lari dengan filter event, jenis event, dan tanggal.
2. **Cari foto via Nomor BIB** — input nomor bib peserta → tampilkan foto-fotonya (dengan
   dukungan OCR untuk *scan* nomor bib dari gambar).
3. **Cari foto via Face Recognition** — upload selfie → sistem mencari wajah paling mirip
   di seluruh galeri. Ada **dua pipeline**:
   - **MTCNN + FaceNet** (pipeline utama)
   - **BlazeFace (MediaPipe) + FaceNet** (eksperimen, threshold lebih ketat)
4. **Peta interaktif event** — admin membuat checkpoint (START, KM 1, dst.), route, dan
   upload foto per checkpoint (Leaflet).
5. **Admin panel** — dashboard statistik, CRUD event/jenis-event/foto/galeri, ubah password.

**Data disimpan di MongoDB Atlas** (clustermuti) sebagai sumber kebenaran, diakses langsung
lewat PyMongo (tanpa ORM). Redis (Memurai localhost) dipakai sebagai cache hasil face-search.

Repositori ini juga memuat **dua proyek pendamping**:
- `face_recognition_run_event/` — proyek Django "mirror" berisi script batch embedding,
  benchmark, dan utilitas data.
- `ocr-validator/` — proyek PHP untuk validasi hasil OCR (deteksi nomor BIB).

---

## 2. Struktur Direktori Utama

```
RUN_EVENT_PHOTO_SYSTEM/
├── config/            # Settings Django, URL root, koneksi MongoDB (db.py), auth backend
├── dashboard/         # Halaman publik + SELURUH admin (admin_urls.py) + templates admin
├── events/            # CRUD event + API peta interaktif (checkpoint, route, foto)
├── photos/            # Face recognition, BIB search, BIB scan (OCR), BlazeFace
├── users/             # Login / register / logout (re-export dari dashboard)
├── galeri/            # Galeri foto publik dengan filter
├── templates/         # base.html publik + template admin (RunSnap Admin)
├── static/            # CSS admin custom
├── media/             # Foto event asli (lomba_lari/), face crops, map photos, dll.
├── sessions/          # Session file-based Django
├── file_skripsi/      # Dokumen skripsi (docx) — di-gitignore
├── backup/            # Backup MongoDB — di-gitignore
├── ocr-validator/     # Proyek PHP pendamping (tidak ikut laporan detail)
├── face_recognition_run_event/  # Proyek mirror batch/benchmark (tidak ikut laporan detail)
├── venv/              # Environment utama (Python 3.10.11)
├── venv_blaze/        # Environment eksperimen BlazeFace
├── manage.py          # Entry point Django
├── requirements.txt   # Deps main app
├── requirements_blaze.txt  # Deps venv_blaze
└── *.py (root)        # Script utilitas: backup, sync, migrasi, debug
```

---

## 3. Teknologi & Dependensi

### 3.1 Stack utama
| Bagian | Teknologi |
|---|---|
| Framework | Django 5.2.16 |
| Database utama | MongoDB Atlas (via PyMongo 4.17) |
| Database Django internal | SQLite (hanya untuk contract auth/session, data nyata di Mongo) |
| Session | File-based (`sessions/`) |
| Cache | Redis via `django-redis` (Memurai di `127.0.0.1:6379/0`, prefix `run_event_photo`, TTL 3600) |
| Face detection | MTCNN (`mtcnn==1.0.0`) & MediaPipe BlazeFace (`mediapipe==0.10.14`) |
| Face embedding | DeepFace `0.0.93` + model **Facenet** (embedding 128 dimensi) |
| OCR | EasyOCR `1.7.2` (model `['en','id']`, CPU) |
| Peta | Leaflet 1.9.4 + Leaflet.Editable (CDN) |
| Frontend | HTML/CSS custom (Poppins, tema hijau), sedikit JS vanilla; flatpickr untuk input waktu |

### 3.2 Package penting di `requirements.txt` (ringkasan)
- Web: `Django`, `django-extensions`, `django-redis`, `Flask` + `flask-cors` (dipakai proyek pendamping)
- AI/ML: `tensorflow 2.15.1`, `keras 2.15.0`, `deepface`, `mtcnn`, `retina-face`, `mediapipe`,
  `easyocr`, `opencv-python`, `numpy`, `pandas`, `scipy`, `matplotlib`, `Pillow`
- DB/utilitas: `pymongo`, `redis`, `python-dotenv`, `gunicorn`, `requests`, `beautifulsoup4`
- `requirements_blaze.txt` hampir identik, beda kecil: `opencv-contrib-python` (bukan `opencv-python`),
  `Pillow 10.4.0`, `pymongo 4.10.1`, `h5py 3.16.0`.

> Catatan: kedua requirements adalah hasil `pip freeze` dari masing-masing venv (lihat komentar
> header file). Keduanya memuat package berat seperti TensorFlow dan digabung satu file.

### 3.3 Lingkungan
- `venv/` — main app (Python 3.10.11 sesuai header requirements.txt)
- `venv_blaze/` — eksperimen BlazeFace batch (lihat README.MD langkah setup)

---

## 4. Arsitektur

### 4.1 Konsep
- **MongoDB = single source of truth.** Semua data bisnis (user, event, foto, embedding,
  peta) di MongoDB. Django ORM tidak dipakai untuk data bisnis — semua models.py hanya
  berisi komentar "Models diganti pake PyMongo langsung via config/db.py".
- **Dua pipeline face recognition paralel** (MTCNN vs BlazeFace) yang masing-masing
  punya collection tersendiri (`*_blaze` vs non-blaze) agar bisa dibandingkan/di-benchmark.
- **Auth manual via session** — login memvalidasi user di MongoDB, lalu menulis
  `request.session['user_id']` dsb. Ada juga `MongoAuthBackend` untuk kompatibilitas Django auth.
- **Cache Redis** untuk hasil face-search — pencarian gambar yang sama tidak diproses ulang
  (key berbasis md5 nama+ukuran file + threshold).

### 4.2 Alur Data — Batch Indexing (Offline)
Dilakukan oleh script di proyek pendamping `face_recognition_run_event/`
(`batch_embeddings.py` untuk MTCNN, `batch_blazeface_embeddings.py` untuk BlazeFace):

```
[media/lomba_lari/<event>/...]
      → baca gambar
      → EXIF transpose (orientasi benar)
      → resize (jika terlalu besar)
      → DETEKSI WAJAH
           ├─ MTCNN (pipeline utama)          ├─ BlazeFace via MediaPipe
           │   bbox/facial_area               │   bbox + confidence
      → crop wajah (+ padding)
      → simpan crop → media/face_crops/  atau media/blaze_face_crops/
      → embedding FaceNet (128 dimensi)
      → simpan ke MongoDB Atlas
           ├─ photos_photoevent       + photos_faceembedding       (MTCNN)
           └─ photos_photoevent_blaze + photos_faceembedding_blaze (BlazeFace)
```

### 4.3 Alur Data — Face Search (Runtime)
```
[User upload selfie]
      → EXIF fix
      → deteksi wajah + embedding FaceNet
      → bandingkan cosine similarity vs semua embedding di MongoDB
      → filter threshold
      → urutkan similarity terbesar → terkecil
      → pagination (12 foto/halaman)
      → cache hasil di Redis (TTL 1 jam)
      → tampilkan ke web (/photos/face-search/)
```

Pipeline BlazeFace: selfie diproses dengan **pipeline yang sama persis** dengan batch
(BlazeFaceProcessor min_confidence 0.1, model_selection 1, padding 0.2, crop max 400px,
embedding `detector_backend='skip'`) supaya embedding konsisten.

### 4.4 Alur Data — BIB Scan (OCR)
```
[Upload gambar peserta]
      → EasyOCR readtext (detail=0, decoder greedy)
      → ekstrak token alfanumerik yang mirip BIB (2–6 char, wajib ada angka)
      → normalize (uppercase, buang separator)
      → cocokkan ke DB (foto yg punya bib_number sama; toleransi leading-zero)
      → group hasil per BIB, batasi 30 foto per BIB
```

### 4.5 Alur Data — BIB Search
- Normalisasi input (`_norm_bib`): uppercase + buang non-alphanumeric.
- Scan collection `photos_photoevent` + legacy `photos`, dukung bentuk nilai
  `'51012'`, `'051012'`, `'51,012'`, atau list.
- Opsional filter per event (folder `lomba_lari/<folder>/`).
- **Feature toggle `USE_EVENT_SELECTION_FOR_BIB`**: `True` = pilih event dulu lalu BIB
  (flow baru); `False` = BIB langsung (flow lama).
- Ada endpoint JSON live-search `/photos/bib-search-api/?q=...&event=...` (max 60 hasil).

---

## 5. Konfigurasi Django (`config/settings.py`)

- `INSTALLED_APPS`: events, photos, users, dashboard, galeri (+ Django internal contenttypes,
  sessions, messages, staticfiles). Tanpa `django.contrib.auth` dan `admin`.
- `AUTHENTICATION_BACKENDS`: custom `config.auth_backend.MongoAuthBackend`.
- `DATABASES`: SQLite (`db.sqlite3`) — hanya contract, data di Mongo.
- `MONGO_URI` / `MONGO_DB_NAME`: dari env var, default **MongoDB Atlas clustermuti**
  database `db_tugasakhir`. **Credential hardcoded di kode** (lihat bagian Keamanan).
- `SESSION_ENGINE = file`, `SESSION_FILE_PATH = sessions/`.
- `CACHES`: Redis `redis://127.0.0.1:6379/0`, prefix `run_event_photo`, TIMEOUT 3600.
- `DEBUG = True`, `ALLOWED_HOSTS = []`.
- Media root: `media/`; static dirs: `static/`.

### 5.1 Koneksi MongoDB (`config/db.py`)
Koneksi tunggal `MongoClient(settings.MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000)`.
Collection yang diakses langsung:

| Collection | Fungsi |
|---|---|
| `events` | Event lari (CRUD admin) |
| `photos` | Foto legacy (upload admin awal) |
| `galeri` | Foto galeri legacy |
| `users` | User (username, email, password hash Django) |
| `map_points` | Checkpoint peta (START, KM 1, dst.) |
| `map_routes` | Geometry route (polyline) per event |
| `map_point_photos` | Foto per checkpoint |
| `event_types` | Jenis event standalone (name + order) |
| `counters` | Auto-increment ID (`get_next_id`) |

Helper: `create_user`, `get_user_by_username`, `authenticate_user`, `verify_password`
(hash pakai `django.contrib.auth.hashers`), `get_event_types` (fallback distinct dari events).

### 5.2 Auth backend (`config/auth_backend.py`)
`MongoAuthBackend` membuat objek `DjangoUser` in-memory dari data Mongo untuk memenuhi
kontrak Django. Namun flow login utama (`dashboard/views.py` dan `dashboard/admin_urls.py`)
memakai session manual — bukan `django.contrib.auth`.

---

## 6. Aplikasi Per Modul

### 6.1 `dashboard` — halaman publik + admin
- `views.py`: `home_view` (beranda), `dasboart_view` (dashboard admin: total foto/event,
  jumlah per jenis event, 5 upload terbaru), `login_view`, `register_view`, `logout_view`,
  `search_view`, `tentang_kami_view`, `events_view`.
- `admin_urls.py` — **pusat seluruh admin**:
  - Login/logout admin, ganti password.
  - CRUD event (`events/`, `add/`, `edit/<id>/`, `delete/<id>/`).
  - CRUD event types (`event-types/`).
  - CRUD foto legacy (`photos/`, upload/edit/delete) — collection `photos`.
  - **Galeri foto event** (`galeri-foto/`) — collection `photos_photoevent`:
    - List + filter folder + cari, pagination 25/halaman.
    - Edit metadata (event_name, bib_number).
    - Upload: simpan file ke `media/lomba_lari/<event>/` → **OCR bib otomatis** (EasyOCR)
      → **embedding wajah BlazeFace** → **embedding wajah MTCNN** (FaceProcessor) →
      insert ke collection foto + embedding. ID baru = max(id)+1 disinkronkan ke counter.
    - Hapus (metadata + file media).
  - URL prefix semua admin: `admin/` (dari `config/urls.py`).

### 6.2 `events` — event + peta interaktif
- `views.py`:
  - `event_list` (filter q/date), `event_add`, `event_detail`, `event_map_view`.
  - **API peta** (JSON, admin-only utk tulis):
    - `api_get_points` (GET), `api_add_point` (POST), `api_update_point` (PUT),
      `api_delete_point` (DELETE), `api_reset_points`.
    - `api_get_route` / `api_save_route` (geometry polyline per event).
    - **Foto per checkpoint**: `api_get_point_photos`, `api_upload_point_photo` (multi-file,
      disimpan ke `media/map_photos/`), `api_delete_point_photo`, `api_delete_point_all_photos`.
  - Proteksi: decorator `admin_required_api` cek session + role staff/superuser.
- `forms.py`: `EventForm` (event_type ChoiceField tetap, timestamp datetime-local, location).
- Template `events/event_detail.html`: Leaflet + Leaflet.Editable untuk tambah titik,
  edit route, dan upload foto per checkpoint.

### 6.3 `photos` — face recognition & BIB
- `views.py`: `photo_list` (galeri dari collection `photos`).
- `face_views.py` (inti AI, ~1222 baris):
  - Koleksi yang dipakai: `photos_photoevent`, `photos` (legacy), `photos_faceembedding`,
    `photos_photoevent_blaze`, `photos_faceembedding_blaze`.
  - Threshold: **MTCNN `THRESHOLD = 0.50`**, **BlazeFace `BLAZE_THRESHOLD = 0.35`** (lebih ketat).
  - `PhotoObj` — wrapper hasil pencarian dengan URL image (mapping folder), metadata event
    (hardcoded: Tiento Run 2026, MILO 2025, Color Run 2026, Car Free Day, Kemerdekaan, UI ECO Run).
  - `cari_foto_mirip_generic` — inti pencarian: load semua foto + embedding, hitung cosine
    distance, simpan skor TERBAIK per foto, filter threshold, sort descending.
  - `face_search` — pipeline MTCNN (POST selfie + cache Redis + pagination).
  - `bib_search` — flow event-select + BIB (toggle `USE_EVENT_SELECTION_FOR_BIB`).
  - `bib_search_api` — live JSON search.
  - `bib_scan` — OCR EasyOCR → cocokkan BIB → group hasil.
  - `test_ai_blaze` — face search pipeline BlazeFace (URL `/photos/face-search/` saat ini
    diarahkan ke sini).
  - `cari_serupa_blaze(photo_id)` — "cari foto sejenis" dari referensi foto, dengan filter
    event, hasil di-cache Redis TTL 12096000 (140 hari).
  - `_extract_blaze_embedding` — deteksi BlazeFace → crop max 400px → embedding Facenet `skip`.
  - Optimasi: `_attach_face_crops_batch` (satu query `$in` untuk semua face crop, hindari
    N+1 saat pagination).
- `face_utils.py`: `FaceProcessor` — deteksi MediaPipe FaceDetection (model_selection 1,
  min_confidence 0.5, padding 30px) + embedding Facenet (`detector_backend='skip'`) +
  normalisasi + cosine similarity. Dipakai juga oleh admin upload (MTCNN).
- `blazeface_utils.py`: `BlazeFaceProcessor` — deteksi via `mp.solutions.face_detection`
  (klasik) atau MediaPipe Tasks API (perlu env `MEDIAPIPE_FACE_DETECTOR_MODEL`). Termasuk
  `crop_faces` dan `draw_boxes` (bbox debug). Padding bbox 20%.
- `utils.py`: `add_watermark` (tulis teks "Run Event 2026" di gambar).
- `forms.py`: `PhotoForm` (event_id hidden + image).

### 6.4 `galeri` — galeri publik
- `views.py`:
  - `_folder_event`, `_image_url`, `_folder_label`, `_list_folders`, `_list_jenis_event`.
  - `_build_query` — filter: `folder` (regex path image `^lomba_lari/<folder>/`),
    `jenis` (jenis_event), `tanggal` (range timestamp 1 hari).
  - `foto_user` (`/galeri/foto/`) dan `hasil` (`/galeri/hasil/`) — tampilkan semua foto
    dari `photos_photoevent`, pagination 25/halaman.
- `forms.py`: `FotoForm` — nama_event, gambar, timestamp (datetime-local), jenis_event
  (choices dari `get_event_types()` dengan fallback 5 tipe default).

### 6.5 `users`
- `views.py` hanya re-export dari `dashboard.views` (`login_view`, `register_view`, `logout_view`).
- URL: `/login/`, `/register/`, `/logout/`.

---

## 7. URL Map (ringkas)

**Publik**
- `/` — beranda
- `/search/` — halaman cari foto
- `/events/` — halaman events; `/events/map/` — peta interaktif
- `/galeri/foto/`, `/galeri/hasil/` — galeri publik
- `/photos/` — daftar foto
- `/photos/face-search/` — **face search (BlazeFace)**
- `/photos/bib-search/` — BIB search (flow event-select)
- `/photos/bib-search-api/` — JSON live BIB search
- `/photos/bib-scan/` — scan BIB via OCR
- `/cari-serupa/<photo_id>/` — cari foto sejenis (BlazeFace)
- `/login/`, `/register/`, `/logout/`
- `/tentang-kami/`

**Admin (semua di bawah `/admin/`)**
- `/admin/` — dashboard admin
- `/admin/login/`, `/admin/logout/`, `/admin/change-password/`
- `/admin/events/` + add/edit/delete
- `/admin/event-types/` + add/edit/delete
- `/admin/photos/` + upload/edit/delete, `/admin/foto/`
- `/admin/galeri-foto/` + upload/edit/delete

**Events API (peta)**
- `/events/api/points/`, add, update, delete, reset
- `/events/api/route/`, save
- `/events/api/points/<id>/photos/`, upload, delete-all, delete

---

## 8. Script Utilitas di Root (Python)

| Script | Fungsi |
|---|---|
| `backup_mongo.py` | Backup SEMUA collection local + Atlas → `backup/mongo_backup_<ts>/{local,atlas}/<col>.json` (bytes di-base64) |
| `sync_mongo.py` | Sinkronisasi 2 arah: union collection foto & embedding (dedup by `id` / `(photo_id, face_image)`), tulis ke Atlas lalu mirror ke local. Collection lain (events/users/dst.) dipreserve dari Atlas |
| `migrate_data.py` | Migrasi SQLite → MongoDB (auth_user→users, events_event→events, galeri_foto→galeri) |
| `migrate_local_to_atlas.py` | Push dokumen `photos_photoevent` yang belum ada di Atlas (tanpa hapus data Atlas) |
| `reset_passwords.py` | Reset password semua user jadi `admin123` |
| `debug_login.py`, `debug_login2.py` | Debug autentikasi (cek user Mongo, verifikasi hash pbkdf2) |
| `test_login.py`, `test_mongodb.py`, `test_check.py`, `_admintest.py`, `_admintest2.py` | Test manual login/koneksi/URL |
| `_dupcheck.py`, `_dupcheck2.py` | Cek duplikasi dokumen di collection |
| `_find_missing.py` | Bandingkan backup vs DB, cari record hilang (hanya ambil ID) |
| `_restore.py`, `_restore2.py`, `_restore_id1.py` | Restore record dari backup JSON (mis. id 1 yang terhapus) |
| `gt_check.txt` | Output log cek ground-truth (berisi "Total foto di Mongo: 1211") |
| `server.log`, `server_err.log` | Log server (kosong) |
| `urls_list.txt` | Daftar URL proyek (dokumentasi manual) |
| `note_revisi` | Catatan revisi: 1) OCR tidak deteksi BIB + waktu OCR 62 detik + info redundan; 2) tampilan BIB sebaiknya tampilkan grid 25 foto default |

---

## 9. Media & Data

`media/lomba_lari/` berisi **7 event** (folder), total **±1205 file foto (~7,9 GB)**:
- `carfreeday`, `colorun`, `kemerdekaan`, `milo`, `milo_race_2026`, `tientorun`, `ui_ecorun`

Folder lain: `face_crops/` (crop wajah + selfie), `blaze_face_crops/`, `map_photos/`
(foto per checkpoint), `foto/`, `photos/`, `bandungcolorrun/`, `images/`, `logo/`, `temp/`.

> Data foto asli disimpan di `media/lomba_lari/<event>/`. Collection Mongo menyimpan path
> relatif (`lomba_lari/<event>/<file>`) pada field `image`. Folder ini di-gitignore.

---

## 10. Proyek Pendamping (ringkasan singkat)

### 10.1 `face_recognition_run_event/` (mirror Django + script batch)
Proyek ini tidak discan detail (sesuai permintaan). Dari struktur file terlihat isinya:
- `batch_embeddings.py` — batch indexing **MTCNN + FaceNet** ke Mongo.
- `batch_blazeface_embeddings.py` — batch indexing **BlazeFace + FaceNet** ke collection `*_blaze`.
- `batch_ocr.py`, `colab_batch_ocr.py` — batch OCR BIB.
- `benchmark_*.py`, `benchmark_skripsi.py`, `generate_summary_chart.py` — benchmark & chart.
- `compare_detectors.py`, `test_blazeface.py`, `test_face.py` — uji detektor.
- `check_gt_mapping.py`, `add_gt_photos.py`, `import_semua.py` — utilitas data/ground-truth.
- `model_diagram.dot` — diagram pipeline (Graphviz).
- Menggunakan venv yang sama (dipanggil dengan `venv\Scripts\python.exe`).
- Sinkronisasi local↔Atlas: jalankan `backup_mongo.py` lalu `sync_mongo.py` (lihat README).

### 10.2 `ocr-validator/` (PHP + Python OCR)
Proyek PHP untuk validasi/deteksi nomor BIB: `index.php`, `upload.php`, `results.php`,
`detect_bib_with_box.php`, `detect_rombongan.php`, `export_excel.php`, `easy_ocr*.py`
(EasyOCR), `detect_face.py`, `db_config.php`, `database.sql`. Tidak discan detail.

---

## 11. Riwayat Git (15 commit terakhir)

Commit terakhir (urutan menurun) menunjukkan arah pengembangan:
1. `6ba4e91` gilaaaa tak masuk logika
2. `a2b3549` package easy ocr
3. `f4be2ad` punya arif
4. `67a128b` apa aja dah
5. `ff77c5a` njirrrr
6. `567076e` Activate Redis cache + remove redundant success message
7. `ed26d30` Fix face-search: total count across pages + batch face-crop queries
8. `17253cc` Fix threshold BlazeFace 0.35 (lebih ketat)
9. `d4bb07b` Fix urutkan hasil face-search dari similarity terbesar
10. `c7c510d` Feat face-search pakai pipeline BlazeFace
11. `349cd17` Fix back button event-types kembali ke dashboard
12. `890b92d` Feat tambah baris Event type di menu GALERI dashboard admin
13. `47efd02` Feat nama event + jenis event standalone table
14. `bab3d8c` Feat ganti input timestamp di galeri/foto ke flatpickr time-only
15. `b740072` Feat foto per checkpoint di peta interaktif

Branch: `main` (lokal), remote `origin/main` + `origin/bini-gw`.

---

## 12. Temuan / Catatan Penting

### 12.1 Potensi risiko keamanan
- **Credential MongoDB Atlas di-hardcode** di `config/settings.py`, `config/db.py`,
  `backup_mongo.py`, `sync_mongo.py`, `migrate_local_to_atlas.py`, `test_mongodb.py`,
  `_find_missing.py`, `_restore_id1.py`. File sync/backup sengaja di-gitignore, tapi
  settings.py **ter-commit**.
- `DEBUG = True` dan `ALLOWED_HOSTS = []` — tidak untuk production.
- `tlsAllowInvalidCertificates=True` pada koneksi Mongo.

> Untuk laporan skripsi, biasanya diperlukan bagian "analisis" — kalau mau, bagian di atas
> bisa dipakai sebagai bahan pembahasan (security, N+1 query yang sudah dioptimasi batch,
> perbandingan akurasi MTCNN vs BlazeFace threshold 0.50 vs 0.35).

### 12.2 Optimasi yang sudah diterapkan
- Batch face-crop query (`$in`) untuk menghindari N+1 saat pagination face-search.
- Cache Redis untuk hasil face-search (key md5 file + threshold) dan cari-serupa (TTL 140 hari).
- Pagination 12 foto/halaman (face), 25/halaman (galeri).
- BIB search API dibatasi max 60 hasil.

### 12.3 Optimasi yang mungkin belum
- Face search melakukan **full scan semua embedding** di Python (tanpa vector index).
  Untuk dataset besar ini O(n) per pencarian dan berat di CPU. Kandidat perbaikan:
  vector search MongoDB Atlas, FAISS, atau pre-filter per event.
- `set_event_metadata` / folder→nama event di-hardcode (bisa diganti lookup DB).

---

## 13. Cara Menjalankan (ringkas)

```bash
# Main app (Python 3.10.11)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver   # memakai MongoDB Atlas clustermuti + Redis localhost

# Pipeline BlazeFace (batch indexing) — venv terpisah
python -m venv venv_blaze
venv_blaze\Scripts\activate
pip install -r requirements_blaze.txt
python face_recognition_run_event/batch_blazeface_embeddings.py

# Sinkronisasi local <-> Atlas (diurutkan)
python backup_mongo.py
python sync_mongo.py
```

> Syarat runtime: MongoDB Atlas terhubung (Internet), Redis/Memurai aktif di `127.0.0.1:6379`,
> dan folder `media/lomba_lari/` berisi foto event.

---

## 14. Kesimpulan

Proyek ini adalah aplikasi Django untuk dokumentasi foto event lari dengan:
1. **Galery + filter** berbasis MongoDB (PyMongo, tanpa ORM).
2. **Pencarian foto via nomor BIB** (manual + OCR EasyOCR).
3. **Face recognition** dengan dua pipeline yang bisa dibandingkan (MTCNN+FaceNet dan
   BlazeFace+FaceNet), lengkap dengan benchmark, threshold, cache Redis, dan pagination.
4. **Peta interaktif event** (Leaflet) dengan checkpoint, route, dan foto per checkpoint.
5. **Admin panel lengkap** termasuk upload foto yang otomatis melakukan OCR bib +
   deteksi wajah + embedding.

Data disinkronkan antara MongoDB lokal dan Atlas dengan script backup/sync, menjadikan
Atlas sebagai sumber kebenaran untuk konsumsi web app dan proyek face recognition.
