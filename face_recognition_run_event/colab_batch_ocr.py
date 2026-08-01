# -*- coding: utf-8 -*-
"""colab_batch_ocr.py

Original file is located at:
    https://colab.research.google.com/drive/1...

Petunjuk Penggunaan di Google Colab:
1. Pastikan Anda telah mengaktifkan GPU T4 di Colab:
   - Klik menu: Runtime -> Change runtime type
   - Pilih Hardware accelerator: T4 GPU
   - Klik Save
2. Pastikan tunnel ngrok TCP ke MongoDB lokal Anda aktif (ngrok tcp 27017).
3. Upload folder "lomba_lari" ke Google Drive Anda.
4. Jalankan script ini di Google Colab.
"""

# =====================================================================
# STEP 1: Mount Google Drive & Install Dependensi
# =====================================================================
from google.colab import drive
import os
import sys

# Mount Google Drive
print("Mengakses Google Drive...")
drive.mount('/content/drive')

# Install library yang diperlukan di Google Colab
print("Menginstal library pendukung...")
!pip install easyocr pymongo dnspython opencv-python-headless tqdm
!apt-get -qq install unrar > /dev/null 2>&1

# =====================================================================
# STEP 2: Konfigurasi Path Google Drive & MongoDB (via ngrok TCP tunnel)
# =====================================================================
import re
import time
import cv2
import easyocr
from pymongo import MongoClient
from tqdm import tqdm

# !!! SESUAIKAN PATH BERDASARKAN LETAK FOLDER DI DRIVE ANDA !!!
# Contoh jika folder 'lomba_lari' ditaruh langsung di My Drive:
DRIVE_LOMBA_LARI_DIR = "/content/drive/MyDrive/lomba_lari"

# Connection String ke MongoDB lokal via tunnel ngrok TCP (tanpa auth)
# Format: mongodb://host:port/db
MONGO_URI = "mongodb://0.tcp.ap.ngrok.io:21120/db_tugasakhir"
DB_NAME = "db_tugasakhir"

# Hubungkan ke MongoDB
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    koleksi_foto = db['photos_photoevent']
    print(f"SUCCESS: Berhasil terhubung ke MongoDB: {DB_NAME}")
    print(f"Jumlah dokumen saat ini: {koleksi_foto.count_documents({})}")
except Exception as e:
    print("ERROR: Gagal terhubung ke MongoDB:", e)
    sys.exit(1)

# =====================================================================
# STEP 3: Load Model EasyOCR dengan GPU
# =====================================================================
print("Memuat model EasyOCR di GPU...")
try:
    # gpu=True memaksimalkan kecepatan ekstraksi menggunakan GPU Colab
    reader = easyocr.Reader(['en', 'id'], gpu=True, verbose=False)
    print("SUCCESS: Model EasyOCR di GPU berhasil dimuat!")
except Exception as e:
    print("WARNING: Gagal meload EasyOCR dengan GPU:", e)
    print("Mencoba fallback menggunakan CPU...")
    reader = easyocr.Reader(['en', 'id'], gpu=False, verbose=False)

# =====================================================================
# STEP 4: Helper Functions
# =====================================================================
def extract_bib_numbers(text):
    """Ekstrak angka 2-4 digit (BIB)"""
    numbers = re.findall(r'\b\d{2,4}\b', text)
    return list(set(numbers))

def extract_all_rar_files(root_dir):
    """
    Cari semua file .rar di dalam root_dir (level manapun) dan
    ekstrak ke folder dengan nama sama (tanpa ekstensi .rar) di
    lokasi yang sama, kalau belum pernah diekstrak sebelumnya.
    Contoh: 'lomba_lari.rar' -> folder 'lomba_lari/'
            'Milo Race 2026.rar' -> folder 'Milo Race 2026/'
    """
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.lower().endswith('.rar'):
                rar_path = os.path.join(dirpath, fname)
                extract_dir = os.path.join(dirpath, os.path.splitext(fname)[0])

                if os.path.isdir(extract_dir) and os.listdir(extract_dir):
                    print(f"Lewati (sudah ada isinya): {extract_dir}")
                    continue

                os.makedirs(extract_dir, exist_ok=True)
                print(f"Mengekstrak: {rar_path} -> {extract_dir}")
                os.system(f'unrar x -y "{rar_path}" "{extract_dir}/" > /dev/null 2>&1')

def build_file_index(root_dir):
    """
    Scan SEMUA subfolder di root_dir secara rekursif (tidak peduli
    nama foldernya apa/berapa level), lalu bikin index:
        nama_file -> [list path lengkap yang ketemu]
    Ini menghindari perlunya menebak nama folder event.
    """
    index = {}
    duplicate_names = set()
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            if fname not in index:
                index[fname] = [full_path]
            else:
                index[fname].append(full_path)
                duplicate_names.add(fname)

    print(f"Index dibuat: {len(index)} nama file unik ditemukan di '{root_dir}'")
    if duplicate_names:
        print(f"PERHATIAN: {len(duplicate_names)} nama file muncul di lebih dari satu folder "
              f"(mis. hasil rename kamera yang generik). Untuk nama-nama ini, "
              f"file pertama yang ditemukan akan dipakai kecuali ada petunjuk folder di data.")
    return index

def find_drive_image_path(image_field_value, file_index):
    """
    Cari lokasi fisik file berdasarkan nama file saja (basename),
    lookup ke file_index hasil build_file_index(). Tidak bergantung
    pada struktur/nama folder event sama sekali.
    """
    filename = os.path.basename(image_field_value)
    candidates = file_index.get(filename)

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Kalau nama file sama muncul di beberapa folder (duplikat),
    # coba cocokkan dulu pakai potongan folder dari path asli di database
    # sebagai tie-breaker. Kalau gak ada yang cocok, pakai kandidat pertama.
    clean_path = image_field_value.lower().replace('\\', '/')
    path_parts = [p for p in clean_path.split('/') if p and p != filename.lower()]

    for cand in candidates:
        cand_lower = cand.lower()
        if any(part in cand_lower for part in path_parts):
            return cand

    return candidates[0]

# =====================================================================
# STEP 5: Jalankan Ekstraksi Batch OCR
# =====================================================================
def start_colab_ocr():
    # Ekstrak dulu semua .rar yang belum diekstrak (lomba_lari.rar, Milo Race 2026.rar, dll)
    print("Mengecek & mengekstrak file .rar di Drive (jika ada)...")
    extract_all_rar_files(DRIVE_LOMBA_LARI_DIR)

    # Bangun index nama_file -> path lengkap, scan rekursif semua subfolder
    print("Membangun index file foto (rekursif, tanpa perlu tau struktur foldernya)...")
    file_index = build_file_index(DRIVE_LOMBA_LARI_DIR)

    photos = list(koleksi_foto.find())
    total = len(photos)

    processed = 0
    updated = 0
    errors = 0
    start_time = time.time()

    print("\nMemulai pemrosesan batch OCR pelari...")

    # Menggunakan progress bar tqdm
    for photo in tqdm(photos, desc="Processing Photos"):
        photo_id = photo.get('id') or photo.get('_id')
        image_field = photo.get('image', '')

        img_path = find_drive_image_path(image_field, file_index)
        if not img_path:
            errors += 1
            continue

        try:
            # Baca gambar menggunakan OpenCV
            img = cv2.imread(img_path)
            if img is None:
                errors += 1
                continue

            # Resize gambar jika dimensinya terlalu besar agar proses GPU makin secepat kilat
            h, w = img.shape[:2]
            max_dim = 1500
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            # Ekstraksi Teks dengan EasyOCR (GPU)
            result = reader.readtext(
                img,
                detail=0,
                paragraph=False,
                decoder='greedy',
                beamWidth=1
            )

            full_text = ' '.join(result) if result else ''
            bib_list = extract_bib_numbers(full_text)
            bib_str = ', '.join(sorted(bib_list))

            # Update nomor dada di MongoDB
            koleksi_foto.update_one(
                {'_id': photo['_id']},
                {'$set': {'bib_number': bib_str}}
            )

            processed += 1
            if bib_list:
                updated += 1

        except Exception as e:
            errors += 1

    duration = time.time() - start_time
    print("\n" + "="*50)
    print("PROSES BATCH OCR DI COLAB SELESAI")
    print(f"Total Foto Berhasil Diproses : {processed}/{total}")
    print(f"Foto Berhasil Diisi BIB      : {updated}")
    print(f"Gagal/File Tidak Ditemukan   : {errors}")
    print(f"Total Waktu Pengerjaan       : {duration:.2f} detik")
    if processed > 0:
        print(f"Rata-rata per Foto           : {duration/processed:.3f} detik/foto")
    print("="*50)

# Jalankan fungsi utama
if __name__ == '__main__':
    start_colab_ocr()