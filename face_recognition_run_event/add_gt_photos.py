# add_gt_photos.py
# ====================================================================
# MENAMBAHKAN FOTO GROUND TRUTH BARU KE MongoDB
# (foto yang belum ada di DB tapi harusnya jadi ground truth)
#
# Foto yang ditambahkan (id 1206+):
#   - milo1_race_2026.jpeg, milo2_race_2026.jpeg  -> berisi Fian + Ira
#   - Tiento_Run (baru 1..4).jpeg                  -> milik Dida
#
# CARA PAKAI (dipanggil 2x, dari venv berbeda):
#   ..\venv\Scripts\python.exe add_gt_photos.py MTCNN
#   ..\venv_blaze\Scripts\python.exe add_gt_photos.py BLAZEFACE
#
# Deteksi MTCNN     : DeepFace represent pada gambar utuh (detector mtcnn)
# Deteksi BlazeFace : MediaPipe deteksi -> crop terbesar -> FaceNet skip
# ====================================================================

import argparse
import hashlib
import os
import sys
import tempfile
from collections import defaultdict

import numpy as np

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django  # noqa: E402
django.setup()

from core.mongo_db import (  # noqa: E402
    koleksi_foto, koleksi_wajah,
    koleksi_foto_blaze, koleksi_wajah_blaze,
)

GT_ROOT = os.path.join(BASE_DIR, 'media', 'ground_truth')

# Foto ground truth yang BELUM ada di DB (hasil check_gt_mapping.py)
# (folder, nama file, event_folder untuk image path)
NEW_GT_PHOTOS = [
    ('Fian (D)', 'milo1_race_2026.jpeg', 'milo_race_2026'),
    ('Fian (D)', 'milo2_race_2026.jpeg', 'milo_race_2026'),
    ('Dida (C)', 'Tiento_Run (baru 1).jpeg', 'tientorun'),
    ('Dida (C)', 'Tiento_Run (baru 2).jpeg', 'tientorun'),
    ('Dida (C)', 'Tiento_Run (baru 3).jpeg', 'tientorun'),
    ('Dida (C)', 'Tiento_Run (baru 4).jpeg', 'tientorun'),
]


def l2_normalize(x):
    norm = np.linalg.norm(x)
    return x / norm if norm > 0 else x


def md5_of_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def extract_mtcnn(img_path):
    """Embedding semua wajah via DeepFace MTCNN pada gambar utuh."""
    from PIL import Image, ImageOps
    from deepface import DeepFace

    img = ImageOps.exif_transpose(Image.open(img_path)).convert('RGB')
    w, h = img.size
    if max(w, h) > 800:
        f = 800 / max(w, h)
        img = img.resize((int(w * f), int(h * f)), Image.LANCZOS)
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        img.save(tmp.name, 'JPEG', quality=90)
        tmp_path = tmp.name
    try:
        results = DeepFace.represent(
            img_path=tmp_path,
            model_name='Facenet',
            detector_backend='mtcnn',
            enforce_detection=False,
        )
    finally:
        os.unlink(tmp_path)
    if not results:
        return []
    out = []
    for r in results:
        vec = np.array(r['embedding'], dtype=np.float32)
        out.append(l2_normalize(vec))
    return out


def extract_blazeface(img_path):
    """Embedding wajah via BlazeFace: deteksi -> crop tiap wajah -> FaceNet skip."""
    from PIL import Image
    from deepface import DeepFace
    from photos.blazeface_utils import BlazeFaceProcessor

    proc = BlazeFaceProcessor(min_detection_confidence=0.1, model_selection=1)
    dets = proc.detect_faces(img_path)
    if not dets:
        return []
    img = Image.open(img_path).convert('RGB')
    out = []
    for det in dets:
        bbox = det['bbox']
        crop = img.crop((bbox['x'], bbox['y'], bbox['x'] + bbox['w'], bbox['y'] + bbox['h']))
        if max(crop.size) > 400:
            cr = 400 / max(crop.size)
            crop = crop.resize((int(crop.width * cr), int(crop.height * cr)), Image.LANCZOS)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            crop.save(tmp.name, 'JPEG', quality=90)
            tmp_path = tmp.name
        try:
            emb = DeepFace.represent(
                img_path=tmp_path,
                model_name='Facenet',
                detector_backend='skip',
                enforce_detection=False,
            )
        finally:
            os.unlink(tmp_path)
        if emb:
            vec = np.array(emb[0]['embedding'], dtype=np.float32)
            out.append(l2_normalize(vec))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('detector', choices=['MTCNN', 'BLAZEFACE'])
    args = parser.parse_args()
    is_mtcnn = args.detector == 'MTCNN'

    if is_mtcnn:
        foto_col = koleksi_foto
        wajah_col = koleksi_wajah
    else:
        foto_col = koleksi_foto_blaze
        wajah_col = koleksi_wajah_blaze

    extractor = extract_mtcnn if is_mtcnn else extract_blazeface

    print("=" * 70)
    print(f"TAMBAH FOTO GROUND TRUTH BARU -> DETEKTOR: {args.detector}")
    print(f"Foto di DB sebelum: {foto_col.count_documents({})}")
    print(f"Embedding sebelum : {wajah_col.count_documents({})}")
    print("=" * 70)

    # Cari id maksimum
    max_id = max((d.get('id', 0) for d in foto_col.find({}, {'id': 1})), default=0)
    print(f"ID maksimum saat ini: {max_id}")

    # Cek duplikat hash antar folder (mis. milo1 di Fian & Ira)
    hash_map = defaultdict(list)
    for folder, fname, _ev in NEW_GT_PHOTOS:
        path = os.path.join(GT_ROOT, folder, fname)
        h = md5_of_file(path)
        hash_map[h].append((folder, fname))

    print("\nCek duplikat hash:")
    for h, files in hash_map.items():
        if len(files) > 1:
            print(f"  DUPLIKAT: {files}")
        else:
            print(f"  OK: {files[0]}")

    # Dedup: hanya tambahkan satu foto per hash (foto yang sama dipakai
    # sebagai ground truth untuk Fian dan Ira sekaligus)
    seen_hashes = set()
    to_add = []
    for folder, fname, ev in NEW_GT_PHOTOS:
        path = os.path.join(GT_ROOT, folder, fname)
        h = md5_of_file(path)
        if h in seen_hashes:
            print(f"  [SKIP DUPLIKAT] {folder}/{fname}")
            continue
        seen_hashes.add(h)
        to_add.append((folder, fname, ev))

    print(f"\nFoto baru yang akan ditambahkan: {len(to_add)}")
    for folder, fname, ev in to_add:
        print(f"  + {fname} (dari {folder}) -> lomba_lari/{ev}/{fname}")

    # Idempotensi: skip foto yang image path-nya sudah ada di DB
    existing_paths = {d.get('image') for d in foto_col.find({}, {'image': 1})}
    before = len(to_add)
    to_add = [(f, fn, ev) for f, fn, ev in to_add
              if f'lomba_lari/{ev}/{fn}' not in existing_paths]
    skipped = before - len(to_add)
    if skipped:
        print(f"  [SKIP SUDAH ADA] {skipped} foto sudah ada di DB, dilewati.")
    if not to_add:
        print("Semua foto ground truth sudah ada di DB. Tidak ada yang ditambahkan.")
        return

    # Tambahkan foto + embedding
    id_counter = max_id
    summary = []
    for folder, fname, ev in to_add:
        id_counter += 1
        new_id = id_counter
        src_path = os.path.join(GT_ROOT, folder, fname)
        image_path = f'lomba_lari/{ev}/{fname}'

        # Insert doc foto
        foto_doc = {
            'id': new_id,
            'event_name': 'Ground Truth Tambahan',
            'image': image_path,
            'bib_number': '',
            'uploaded_at': None,
        }
        foto_col.insert_one(foto_doc)

        # Hitung embedding
        embeddings = extractor(src_path)
        print(f"\n  [{new_id}] {fname}: {len(embeddings)} wajah terdeteksi")

        for idx, vec in enumerate(embeddings):
            wajah_doc = {
                'photo_id': new_id,
                'image': image_path,
                'event_name': 'Ground Truth Tambahan',
            }
            if is_mtcnn:
                wajah_doc['face_image'] = f'face_crops/gt_{new_id}_{idx}.jpg'
            else:
                wajah_doc['face_image'] = f'blaze_face_crops/gt_{new_id}_{idx}.jpg'
                wajah_doc['detector'] = 'blazeface'
            wajah_doc['bbox_json'] = {}
            wajah_doc['embedding_data'] = vec.tobytes()
            wajah_col.insert_one(wajah_doc)

        summary.append((new_id, fname, folder, len(embeddings)))

    print("\n" + "=" * 70)
    print("RINGKASAN PENAMBAHAN")
    print("=" * 70)
    print(f"{'ID':<6}{'File':<30}{'Subjek Folder':<14}{'Faces'}")
    print("-" * 60)
    for new_id, fname, folder, n in summary:
        print(f"{new_id:<6}{fname:<30}{folder:<14}{n}")
    print("-" * 60)
    print(f"Foto di DB setelah : {foto_col.count_documents({})}")
    print(f"Embedding setelah  : {wajah_col.count_documents({})}")
    print("\nPeta ground truth baru untuk pengujian:")
    for new_id, fname, folder, n in summary:
        if 'milo' in fname:
            print(f"  id={new_id} ({fname}) -> GT untuk Fian + Ira")
        else:
            print(f"  id={new_id} ({fname}) -> GT untuk Dida")


if __name__ == '__main__':
    main()
