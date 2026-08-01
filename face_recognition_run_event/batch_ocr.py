#!/usr/bin/env python3
# batch_ocr.py - Integrasi EasyOCR untuk Ekstraksi Nomor BIB ke MongoDB

import os
import sys
import re
import time
import cv2
import warnings
warnings.filterwarnings('ignore')

# Setup path agar bisa import dari config django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    import django
    django.setup()
    from config.db import db
    print("SUCCESS: Berhasil terhubung ke MongoDB via Django Config")
except Exception as e:
    print("WARNING: Gagal terhubung via Django config, mencoba koneksi local MongoDB...")
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
        db = client['db_tugasakhir']
        print("SUCCESS: Berhasil terhubung ke local MongoDB")
    except Exception as err:
        print("ERROR: Gagal terhubung ke MongoDB:", err)
        sys.exit(1)

koleksi_foto = db['photos_photoevent']

# ============================================
# INITIALIZE EASYOCR
# ============================================
print("Memuat model EasyOCR (English & Indonesian)...")
try:
    import easyocr
    reader = easyocr.Reader(['en', 'id'], gpu=False, verbose=False)
    print("Model EasyOCR berhasil dimuat!")
except ImportError:
    print("EasyOCR tidak terinstal di environment ini.")
    sys.exit(1)

def extract_bib_numbers(text):
    """Ekstrak angka 2-4 digit (BIB)"""
    # Mencari angka mandiri berukuran 2 hingga 4 digit
    numbers = re.findall(r'\b\d{2,4}\b', text)
    return list(set(numbers))  # Hapus duplikat

def find_local_image_path(image_field_value):
    """Mencari path fisik file gambar di media directory"""
    # Bersihkan nama file dari path
    filename = os.path.basename(image_field_value)
    
    # Deteksi folder event berdasarkan nama file / path
    event_folder = ""
    clean_path = image_field_value.lower()
    if 'tiento' in clean_path:
        event_folder = 'tientorun'
    elif 'colorun' in clean_path or 'color' in clean_path:
        event_folder = 'colorun'
    elif 'carfree' in clean_path or 'cfd' in clean_path:
        event_folder = 'carfreeday'
    elif 'milo_race_2026' in clean_path:
        event_folder = 'milo_race_2026'
    elif 'milo' in clean_path:
        event_folder = 'milo'
    elif 'merdeka' in clean_path or 'kemerdekaan' in clean_path:
        event_folder = 'kemerdekaan'
    elif 'ui_eco' in clean_path or 'ecorun' in clean_path:
        event_folder = 'ui_ecorun'

    # Daftarkan kemungkinan lokasi path
    possible_paths = [
        # Path relatif dari root/media
        os.path.join(BASE_DIR, 'media', 'lomba_lari', event_folder, filename),
        os.path.join(BASE_DIR, 'media', image_field_value),
        # Path relatif dari face_recognition_run_event/media
        os.path.join(BASE_DIR, 'face_recognition_run_event', 'media', 'lomba_lari', event_folder, filename),
        os.path.join(BASE_DIR, 'face_recognition_run_event', 'media', image_field_value),
        # Path langsung
        image_field_value
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.path.isfile(path):
            return path
            
    return None

def process_batch_ocr():
    # Ambil semua foto di database
    photos = list(koleksi_foto.find())
    total = len(photos)
    print(f"Ditemukan {total} foto di database untuk diproses.")
    
    processed = 0
    updated = 0
    errors = 0
    start_time = time.time()
    
    for idx, photo in enumerate(photos):
        photo_id = photo.get('id') or photo.get('_id')
        image_field = photo.get('image', '')
        
        # Cari path fisik
        img_path = find_local_image_path(image_field)
        if not img_path:
            print(f"[{idx+1}/{total}] File tidak ditemukan untuk ID {photo_id}: {image_field}")
            errors += 1
            continue
            
        try:
            # Load gambar
            img = cv2.imread(img_path)
            if img is None:
                print(f"[{idx+1}/{total}] ERROR pada ID {photo_id}: cv2.imread gagal membaca image.")
                errors += 1
                continue

            # Resize gambar jika terlalu besar (mencegah crafter 0-width bbox crash)
            h, w = img.shape[:2]
            max_dim = 1500
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            # Jalankan OCR
            ocr_start = time.time()
            result = reader.readtext(
                img,
                detail=0,
                paragraph=False,
                decoder='greedy',
                beamWidth=1
            )
            ocr_duration = time.time() - ocr_start
            
            full_text = ' '.join(result) if result else ''
            bib_list = extract_bib_numbers(full_text)
            bib_str = ', '.join(sorted(bib_list))
            
            # Update database
            koleksi_foto.update_one(
                {'_id': photo['_id']},
                {'$set': {'bib_number': bib_str}}
            )
            
            processed += 1
            if bib_list:
                updated += 1
                print(f"[{idx+1}/{total}] OK ID {photo_id} | Waktu: {ocr_duration:.2f}s | Terdeteksi BIB: [{bib_str}]")
            else:
                print(f"[{idx+1}/{total}] OK ID {photo_id} | Waktu: {ocr_duration:.2f}s | Tidak ada BIB terdeteksi")
                
        except Exception as e:
            print(f"[{idx+1}/{total}] ERROR pada ID {photo_id}: {e}")
            errors += 1
            
    duration = time.time() - start_time
    print("\n" + "="*40)
    print("PROSES BATCH OCR SELESAI")
    print(f"Total Foto Diproses: {processed}/{total}")
    print(f"Foto dengan BIB Terupdate: {updated}")
    print(f"Error / File Lewat: {errors}")
    print(f"Total Waktu: {duration:.2f} detik ({duration/max(1, processed):.2f}s/foto)")
    print("="*40)

if __name__ == '__main__':
    process_batch_ocr()
