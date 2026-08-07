# LAPORAN VALIDASI SKRIPSI vs KODE SUMBER

**Dokumen yang divalidasi:** Skripsi Alda Siti Nurlatifah (NIM 2242408)
**Judul:** Implementasi Website Dokumentasi Foto Event Lari dengan Fitur Pencarian Berdasarkan Jenis Event dan Timestamp
**File:** `file_skripsi/Skripsi Alda 2242408 (1).docx`
**Pembanding:** seluruh kode sumber proyek `RUN_EVENT_PHOTO_SYSTEM`
**Tanggal validasi:** 2026-08-07

---

## 1. Metode Validasi

Setiap klaim di skripsi (bab I–V, tabel-tabel, dan diagram) dibandingkan satu-per-satu dengan
implementasi nyata di kode: `config/`, `dashboard/`, `events/`, `photos/`, `galeri/`, `users/`,
script batch di `face_recognition_run_event/`, template HTML, dan `requirements.txt`.

---

## 2. Verdict Ringkas

| Aspek | Hasil |
|---|---|
| Arah/topik penelitian sesuai kode | ✅ Ya (Django + MongoDB, galeri event, cari BIB, face recognition, peta) |
| Klaim teknis utama (Django, MongoDB) | ✅ Benar |
| **BAB IV §4.3 "Lingkungan Implementasi"** | ❌ **SALAH** — menyebut MySQL & Bootstrap, padahal sistem memakai MongoDB & CSS custom |
| **Alur timestamp/EXIF** | ⚠️ Klaim premis inti tidak terlihat di kode (tidak ada ekstraksi EXIF; filter pakai tanggal, bukan "jam:menit") |
| Inkonsistensi internal (hardware, DB) | ⚠️ Ada beberapa kontradiksi antar bab |
| Kelengkapan editorial (TOC, istilah) | ⚠️ TOC berisi placeholder "LUPA NAMA HEHE", DAFTAR ISTILAH kosong |

**Kesimpulan:** Skripsi secara konsep sudah menggambarkan sistem yang benar, namun ada **3 kesalahan
faktual besar** (MySQL/Bootstrap/SQLite) dan beberapa **klaim yang tidak sinkron dengan implementasi
aktual** yang wajib diperbaiki sebelum sidang.

---

## 3. BAGIAN A — Klaim yang BENAR (sesuai implementasi)

| # | Klaim skripsi | Bukti di kode | Status |
|---|---|---|---|
| A1 | Dibangun dengan framework **Django** | `requirements.txt`: `Django==5.2.16`; `manage.py`, `config/settings.py` | ✅ |
| A2 | Basis data **MongoDB** | `config/db.py` (PyMongo), `config/settings.py` `MONGO_URI` → MongoDB Atlas `clustermuti`, db `db_tugasakhir` | ✅ |
| A3 | Web dokumentasi foto event lari (galeri publik) | `galeri/views.py`, `photos/views.py`; template galeri | ✅ |
| A4 | Pencarian berdasarkan **nomor BIB** (fitur pendukung) | `photos/face_views.py`: `bib_search`, `bib_search_api`, `bib_scan` (OCR EasyOCR) | ✅ |
| A5 | Pencarian **Face Recognition** (fitur pendukung) | `photos/face_views.py`, `photos/face_utils.py`, `photos/blazeface_utils.py` (MTCNN & BlazeFace + FaceNet) | ✅ |
| A6 | Admin: login, CRUD event, CRUD jenis event, upload foto, edit metadata foto, lihat galeri, ganti password, logout | `dashboard/admin_urls.py` (seluruh URL admin) | ✅ |
| A7 | KF-10 s.d. KF-16: peta interaktif, checkpoint, route, foto per checkpoint | `events/views.py` (API points/route/photos), `events/event_detail.html` (Leaflet + Leaflet.Editable) | ✅ |
| A8 | Download foto | Template memakai `<a ... download>` (mis. `galeri/foto/foto.html`, `hasil.html`, `photos/*`) | ✅ |
| A9 | Foto disimpan ke media + metadata ke DB, path relatif `lomba_lari/<folder>/<file>` | `batch_embeddings.py` (field `image`), `admin_urls.py` `galeri_photo_upload` | ✅ |
| A10 | Data event: **Bandung Color Run Festival 2026** (17 Mei 2026, Laswi Heritage, Bandung) dan **Tiento Run 2026** (28 Juni 2026, Balai Kota, Bandung) | `photos/face_views.py` `set_event_metadata` | ✅ |
| A11 | Metadata foto: `event_name`, `jenis_event`, `bib_number`, face embedding | Struktur dokumen di `batch_embeddings.py`, `admin_urls.py` | ✅ |
| A12 | Peserta browsing tanpa akun; admin memakai login | Halaman publik tanpa decorator; login hanya untuk admin (`dashboard/views.py`, `admin_urls.py`) | ✅ |
| A13 | MongoDB Atlas sebagai sumber kebenaran, ada sinkronisasi local↔Atlas | `sync_mongo.py`, `backup_mongo.py`, `migrate_local_to_atlas.py` | ✅ |

---

## 4. BAGIAN B — Klaim yang SALAH / TIDAK SESUAI IMPLEMENTASI (wajib diperbaiki)

### B1. ❌ "MySQL digunakan sebagai database management system" (BAB IV §4.3)
Skripsi §4.3 menulis: *"MySQL digunakan sebagai database management system untuk menyimpan data
pengguna, event, dan foto."* Ini **salah total** — sistem memakai **MongoDB** (Atlas). Abstrak & BAB III
juga sudah menulis MongoDB, jadi §4.3 bertentangan dengan skripsi itu sendiri.
- Bukti: `config/settings.py:74-78` (MONGO_URI), `config/db.py`, `requirements.txt` (`pymongo`), tidak ada MySQL.
- **Perbaikan:** ganti MySQL → MongoDB (MongoDB Atlas).

### B2. ❌ "Bootstrap untuk mendukung tampilan yang responsif" (BAB IV §4.3)
Tidak ada satu pun Bootstrap di template. Frontend memakai **CSS custom** (font Poppins, gradasi hijau).
- Bukti: `templates/base.html`, `templates/admin/base_admin.html`; grep `bootstrap` di seluruh `*.html` = 0 hasil.
- **Perbaikan:** tulis CSS custom (tanpa framework / plain CSS), atau benar-benar pakai Bootstrap kalau mau klaim itu.

### B3. ❌ "tersimpan ke dalam database SQLite dan Photo Storage" (BAB III §3.3, deskripsi Flowchart)
Database bisnis adalah **MongoDB**, bukan SQLite. SQLite (`db.sqlite3`) hanya dipakai sebagai contract
Django internal (auth/session), dan per komentar di `settings.py:60-63` **tidak ada data di situ**.
- Bukti: `config/settings.py:60-69`, `config/db.py`.
- **Perbaikan:** tulis "tersimpan ke dalam basis data MongoDB dan Photo Storage".

### B4. ⚠️ Premis "timestamp dari metadata EXIF" (inti judul) tidak terlihat di kode
Skripsi menempatkan **timestamp** (waktu pengambilan dari EXIF) sebagai fitur inti, bahkan batasan
masalah menulis foto dibatasi JPEG *"karena format tersebut mendukung penyimpanan metadata EXIF yang
diperlukan dalam proses pencarian berdasarkan timestamp."* Namun:
- Tidak ada kode yang mengekstrak `DateTimeOriginal`/EXIF untuk mengisi timestamp.
  - `batch_embeddings.py` dan `batch_blazeface_embeddings.py` hanya memakai `ImageOps.exif_transpose`
    (memutar orientasi), bukan membaca waktu.
- Dokumen yang dibuat pipeline batch **tidak punya field `timestamp`** (hanya `id`, `event_name`,
  `image`, `bib_number`, `uploaded_at: None`). Lihat `face_recognition_run_event/batch_embeddings.py:157-163`.
- Galeri filter pakai field `timestamp` (`galeri/views.py:91`) dan UI filter memakai input **tanggal**
  (`<input type="date" name="tanggal">` di `galeri/foto/foto.html:288`), bukan "jam:menit".
- Grep `timestamp` di seluruh proyek: tidak ada satu pun kode yang menulis field timestamp ke `photos_photoevent`.
- **Risiko nyata:** fitur "pencarian berdasarkan timestamp" bisa tidak mengembalikan hasil karena
  datanya tidak terisi. Perlu dicek langsung isi Mongo; kalau kosong, fitur ini harus di-backfill
  (misal dari EXIF) atau klaim skripsi disesuaikan.
- **Perbaikan:** (1) tambahkan ekstraksi EXIF + isi field `timestamp`, atau (2) ubah narasi skripsi
  menjadi pencarian berdasarkan tanggal/folder event yang sesuai implementasi.

### B5. ⚠️ Halaman "Event & Timestamp" yang dideskripsikan tidak sama dengan UI aktual
Skripsi §4.2.3 & test case (Tabel 4.2 no.4-5): *"memilih event … dropdown Jenis Event … mengisi
timestamp dengan format jam:menit … tombol Cari Foto."* Implementasi aktual:
- Halaman galeri (`galeri/foto/foto.html:275-289`) memakai dropdown **"Semua Event" (folder)** +
  **"Semua Jenis Event"** + input **`tanggal` (date)** + tombol **"Filter"**.
- Tidak ada input waktu "jam:menit". (Catatan: commit `bab3d8c` pernah menambah flatpickr time-only,
  tapi template saat ini sudah memakai `input type=date`.)
- **Perbaikan:** sinkronkan deskripsi & test case dengan UI (folder/jenis event + tanggal), atau ubah UI.

### B6. ⚠️ Menu "Kategori" tidak ada di sistem berjalan
Skripsi menulis navigasi berisi "Beranda, Cari Foto, Events, **Kategori**, dan Tentang Kami"
(§4.2.1 dan Tabel 4.2 no.1). Di kode, menu **Kategori di-comment** (`templates/base.html:266`) dan
URL-nya juga di-comment (`dashboard/urls.py:36-40`). Halaman `kategori.html` ada tapi tidak diroute.
- **Perbaikan:** hapus "Kategori" dari skripsi, atau aktifkan kembali menu & halamannya.

### B7. ⚠️ "Tombol Masuk dan Daftar dirancang khusus untuk admin, bukan untuk peserta umum" (§4.2.1)
Registrasi terbuka untuk umum dan membuat **user biasa** (bukan admin); status admin
(`is_staff`/`is_superuser`) tidak di-set lewat register (`dashboard/views.py:81-110`).
Kalimat "khusus untuk admin" tidak akurat — sebaiknya: tombol login/daftar untuk pengguna terdaftar,
admin memakai `/admin/login/`.
- **Perbaikan:** sesuaikan narasi §4.2.1.

### B8. ⚠️ "Empat metode pencarian: Event & Timestamp, Nomor BIB, Wajah, dan Rute/Map Interaktif"
Halaman Cari Foto hanya menyediakan **3 metode** (kartu): Galeri Event, Nomor Bib, Face Recognition
(`dashboard/templates/dashboard/search.html:136-157`). Peta ada di menu **Events** (`/events/map/`),
bukan bagian dari halaman "Cari Foto".
- **Perbaikan:** ubah narasi use case/flowchart menjadi 3 metode pencarian, atau tambahkan pintu masuk peta di halaman Cari Foto.

### B9. ⚠️ Tabel 4.1 no.5: "Menghapus data event … beserta foto-foto yang terhubung dengannya"
Implementasi hanya `events_collection.delete_one(...)` — **foto TIDAK ikut terhapus**.
- Bukti: `dashboard/admin_urls.py:199-202` (event_delete).
- **Perbaikan:** ubah hasil yang diharapkan menjadi "menghapus data event" saja, atau ubah kode agar
  benar-benar menghapus foto terkait (tidak disarankan karena foto galeri di-collection terpisah).

### B10. ⚠️ Data event MILO tidak konsisten
| Sumber | Nama | Tanggal | Lokasi |
|---|---|---|---|
| Skripsi Tabel 1.1 | Milo Activ Indonesia Race **2026** – Bandung Series | Minggu, **19 Juli 2026**, 05:00 | Balai Kota, Bandung |
| Kode (`set_event_metadata`, `batch_embeddings.py:40`) | MILO ACTIV Indonesia Race **2025** | **1 Juni 2025** | Kota Baru Parahyangan, Padalarang |

Kode juga memakai folder `milo_race_2026` yang **tidak punya label** di `EVENT_NAME_MAP`
(akan tampil sebagai "Milo Race 2026"). Perlu ditentukan versi mana yang benar (2025 atau 2026) lalu
dipakai konsisten di skripsi **dan** kode.

### B11. ⚠️ Class Diagram & ERD (3.4.6/3.4.7) digambarkan sebagai model relasional
ERD menampilkan entitas "admin" (username, password), "event", "foto" dengan kardinalitas dan relasi
one-to-many. Implementasi aktual memakai **MongoDB dokumen**: tidak ada entitas "admin" terpisah
(status admin ada di koleksi `users`), tidak ada FK/relasi kunci asing.
- **Perbaikan:** tandai diagram sebagai model konseptual/logical, atau buat diagram dokumen (MongoDB).

---

## 5. BAGIAN C — Inkonsistensi Internal (skripsi vs skripsi)

| # | Lokasi | Masalah |
|---|---|---|
| C1 | Abstrak & BAB III vs BAB IV §4.3 | Abstrak/BAB III: MongoDB. §4.3: MySQL. **Kontradiksi.** |
| C2 | Tabel 3.4 (Hardware) vs §4.3 (Lingkungan) | Tabel 3.4: Lenovo, **i3-1315U (1.20 GHz)**, **RAM 16 GB**, storage 112/238 GB, **Windows 11**. §4.3: **Intel Core i5, RAM 8 GB, SSD 256 GB**. **Kontradiksi.** |
| C3 | Daftar Isi §2.2.2 | Daftar isi menulis **"LUPA NAMA HEHE"** (placeholder, lupa nama), sedangkan isi bab sebenarnya "Proses Terbentuknya Metadata Gambar". **TOC belum di-update.** |
| C4 | DAFTAR ISTILAH | Kosong (tidak ada isi). |
| C5 | Tabel 3.1 | KF-05 s.d. KF-09 (Lihat Galeri, Pencarian Jenis Event, Timestamp, Hasil, Download) dikategorikan sebagai "kebutuhan fungsional **admin**", padahal ini jelas fitur user/peserta. |
| C6 | Batasan masalah | Menulis foto dibatasi JPEG karena EXIF, padahal upload menerima PNG/WebP/BMP/TIFF (kode `bib_scan`, `galeri_photo_upload`). |
| C7 | Test case Tabel 4.2 no.4 | Menulis "mengisi timestamp dengan format jam:menit", tidak sesuai UI aktual (input tanggal). |

---

## 6. BAGIAN D — Minor / Editorial

- Typo: "Kebutuhan Fugsional Admin" (Tabel 3.1), "Analisis kebuhan Fungsional" (Tabel 3.3),
  "Nomer Bib" (Gambar 3.16).
- §4.2.4 "HASIL PENCARIAN" ada teks field-code `02891790` nyangkut sebelum caption (artefak Word).
- Ada istilah "pencarian berdasarkan timestamp" yang dipakai untuk UI galeri — pastikan konsisten
  dengan apa yang sebenarnya diimplementasikan (folder/jenis event + tanggal).

---

## 7. Temuan Teknis Tambahan yang Perlu Disadari (untuk skripsi & demo)

1. **Field `jenis_event` & `timestamp` pada collection galeri (`photos_photoevent`) kemungkinan kosong.**
   - `jenis_event` hanya diisi lewat upload/legacy `photos` & `galeri` lama (bukan pipeline foto event).
   - Akibatnya dropdown "Jenis Event" dan filter tanggal di galeri bisa tidak mengembalikan apa pun
     untuk data hasil batch. **Verifikasi isi MongoDB**; kalau kosong, fitur inti "pencarian jenis
     event & timestamp" butuh data backfill (atau perbaiki narasi).
2. **Judul menekankan "Timestamp", tapi sistem berjalan lebih kuat pada pencarian folder event + BIB + wajah.**
   Pertimbangkan menyesuaikan penekanan agar sesuai hasil demo yang sesungguhnya, atau lengkapi data
   timestamp dari EXIF lalu implementasikan filter waktu yang benar.
3. Skripsi sudah jujur bahwa algoritma face/BIB tidak dibahas (di luar lingkup) — ini **konsisten**
   dengan batasan masalah, jadi tidak perlu diubah, tapi pastikan bab IV tetap menyebut fitur tersebut
   berjalan (sudah benar).

---

## 8. Rekomendasi Perbaikan (Prioritas)

### 🔴 Prioritas Tinggi (wajib — bisa dipersoalkan penguji)
1. §4.3: ganti **MySQL → MongoDB**; hapus klaim **Bootstrap** (tulis "CSS custom").
2. §3.3 flowchart: ganti **SQLite → MongoDB**.
3. Perbaiki **§2.2.2 di daftar isi** ("LUPA NAMA HEHE" → "Proses Terbentuknya Metadata Gambar") —
   update TOC seluruh dokumen (tampaknya TOC belum di-refresh setelah revisi).
4. Konsistenkan **data hardware** antara Tabel 3.4 dan §4.3.
5. Verifikasi & perbaiki **data timestamp/jenis_event** di MongoDB; kalau tidak ada, sesuaikan klaim
   fitur "pencarian timestamp" atau tambahkan backfill EXIF.

### 🟡 Prioritas Sedang
6. Sinkronkan deskripsi UI "Event & Timestamp" (folder/jenis + tanggal, bukan "jam:menit").
7. Hapus/aktifkan **"Kategori"**; samakan dengan kode.
8. Perbaiki kalimat "tombol Masuk/Daftar khusus admin" (§4.2.1).
9. Perjelas "4 metode pencarian" menjadi 3 metode (map bukan metode pencarian).
10. Tabel 4.1 no.5: sesuaikan hasil yang diharapkan (foto tidak ikut terhapus).
11. Konsistenkan data event **MILO 2025 vs 2026** di skripsi dan kode.

### 🟢 Prioritas Rendah
12. Beri keterangan pada ERD/Class Diagram bahwa itu model konseptual (MongoDB document).
13. Rapikan typo & artefak field-code Word; isi DAFTAR ISTILAH.
14. Perbaiki pengkategorian KF-05..09 (fitur user, bukan admin).

---

*Laporan ini dibuat otomatis dengan membandingkan isi skripsi terhadap kode sumber pada kondisi
repository saat ini (commit `6ba4e91`). Perubahan kode setelah tanggal ini dapat membuat sebagian
temuan perlu ditinjau ulang.*
