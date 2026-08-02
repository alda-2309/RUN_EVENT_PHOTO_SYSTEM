import os
import time
import tempfile
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from pymongo import MongoClient
from deepface import DeepFace

from photos.blazeface_utils import BlazeFaceProcessor

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')

BASE_DIR = os.path.dirname(__file__)
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
CROP_DIR = os.path.join(MEDIA_ROOT, 'blaze_face_crops')
BBOX_DEBUG_DIR = os.path.join(MEDIA_ROOT, 'blaze_bbox_debug')
MONGO_URI = os.environ.get(
    'MONGO_URI',
    'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority'
)
NUM_WORKERS = 4

EVENT_DIRS = {
    'colorun': os.path.join(MEDIA_ROOT, 'lomba_lari', 'colorun'),
    'kemerdekaan': os.path.join(MEDIA_ROOT, 'lomba_lari', 'kemerdekaan'),
    'milo': os.path.join(MEDIA_ROOT, 'lomba_lari', 'milo'),
    'milo_race_2026': os.path.join(MEDIA_ROOT, 'lomba_lari', 'milo_race_2026'),
    'tientorun': os.path.join(MEDIA_ROOT, 'lomba_lari', 'tientorun'),
    'carfreeday': os.path.join(MEDIA_ROOT, 'lomba_lari', 'carfreeday'),
    'ui_ecorun': os.path.join(MEDIA_ROOT, 'lomba_lari', 'ui_ecorun'),
}

EVENT_NAME_MAP = {
    'colorun': 'Bandung Color Run Festival 2026',
    'kemerdekaan': 'Independence Day Fun Run 2026',
    'milo': 'MILO ACTIV Indonesia Race 2025',
    'tientorun': 'Tiento Run 2026',
    'carfreeday': 'Car Free Day Fun',
    'ui_ecorun': 'Vokasi UI ECO Run',
}

processor = BlazeFaceProcessor(min_detection_confidence=0.1, model_selection=1)


def l2_normalize(x):
    return x / np.sqrt(np.maximum(np.sum(np.square(x), axis=-1, keepdims=True), 1e-6))


def build_local_photo_docs(koleksi_foto):
    koleksi_foto.delete_many({})
    docs = []
    next_id = 1
    for event_folder, folder_path in EVENT_DIRS.items():
        if not os.path.exists(folder_path):
            continue
        for fname in sorted(os.listdir(folder_path)):
            if not fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                continue
            doc = {
                'id': next_id,
                'event_name': EVENT_NAME_MAP.get(event_folder, event_folder),
                'image': f'lomba_lari/{event_folder}/{fname}',
                'bib_number': '',
                'uploaded_at': None,
            }
            docs.append((next_id, event_folder, os.path.join(folder_path, fname), fname, doc))
            next_id += 1
    if docs:
        koleksi_foto.insert_many([d[4] for d in docs])
    return docs


def process_one(photo_tuple):
    photo_id, event_folder, img_path, filename = photo_tuple
    try:
        detections = processor.detect_faces(img_path)
        if not detections:
            return {'photo_id': photo_id, 'status': 'ok', 'faces': [], 'count': 0}

        orig_img = ImageOps.exif_transpose(Image.open(img_path)).convert('RGB')
        faces = []

        for idx, det in enumerate(detections):
            bbox = det['bbox']
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            if w <= 0 or h <= 0:
                continue

            crop = orig_img.crop((x, y, x + w, y + h))
            max_crop = 400
            if max(crop.size) > max_crop:
                cr = max_crop / max(crop.size)
                crop = crop.resize((int(crop.width * cr), int(crop.height * cr)), Image.LANCZOS)

            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                crop.save(tmp.name, 'JPEG', quality=90)
                tmp_crop_path = tmp.name

            try:
                emb = DeepFace.represent(
                    img_path=tmp_crop_path,
                    model_name='Facenet',
                    detector_backend='skip',
                    enforce_detection=False,
                )
            finally:
                if os.path.exists(tmp_crop_path):
                    os.unlink(tmp_crop_path)

            if not emb:
                continue

            vec = np.array(emb[0]['embedding'], dtype=np.float32)
            vec = l2_normalize(vec)

            os.makedirs(CROP_DIR, exist_ok=True)
            crop_filename = f"blaze_{photo_id}_{idx}.jpg"
            crop_path = os.path.join(CROP_DIR, crop_filename)
            crop.save(crop_path, format='JPEG', quality=90)

            faces.append({
                'photo_id': photo_id,
                'image': f'lomba_lari/{event_folder}/{filename}',
                'event_name': EVENT_NAME_MAP.get(event_folder, event_folder),
                'detector': 'blazeface',
                'bbox_json': bbox,
                'embedding_data': vec.tobytes(),
                'face_image': f'blaze_face_crops/{crop_filename}',
                'confidence': det['confidence'],
            })

        if detections:
            os.makedirs(BBOX_DEBUG_DIR, exist_ok=True)
            debug_img = orig_img.copy()
            draw = ImageDraw.Draw(debug_img)
            for det in detections:
                bbox = det['bbox']
                x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
                draw.rectangle([x, y, x + w, y + h], outline='lime', width=3)
                draw.text((x, max(0, y - 12)), f"{det['confidence']:.2f}", fill='lime')

            debug_filename = f"bbox_{event_folder}_{filename}".replace(' ', '_')
            debug_img.save(os.path.join(BBOX_DEBUG_DIR, debug_filename), format='JPEG', quality=90)

        return {
            'photo_id': photo_id,
            'status': 'ok',
            'count': len(faces),
            'faces': faces,
        }
    except Exception as e:
        return {
            'photo_id': photo_id,
            'status': 'error',
            'error': str(e),
        }


if __name__ == '__main__':
    print('=== BATCH BLAZEFACE EMBEDDING (FaceNet) ===')

    client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=30000)
    db = client['db_tugasakhir']

    koleksi_foto = db['photos_photoevent_blaze']
    koleksi_wajah = db['photos_faceembedding_blaze']

    koleksi_wajah.delete_many({})
    print('Cleared old BlazeFace embeddings')

    local_docs = build_local_photo_docs(koleksi_foto)
    all_photos = [(pid, event_folder, img_path, filename) for pid, event_folder, img_path, filename, _doc in local_docs]
    total = len(all_photos)
    print(f'Photos: {total} | Workers: {NUM_WORKERS}')

    start = time.time()
    success = no_face = errors = 0

    with Pool(NUM_WORKERS) as pool:
        for i, result in enumerate(pool.imap(process_one, all_photos)):
            pid = result.get('photo_id')
            status = result.get('status')

            if status == 'error':
                errors += 1
                print(f'[{i+1}/{total}] ID={pid} ERROR: {result.get("error","")[:100]}')
                continue

            faces = result.get('faces', [])
            if faces:
                for face in faces:
                    koleksi_wajah.insert_one(face)
                success += 1
            else:
                no_face += 1

            elapsed = time.time() - start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            if (i + 1) % 50 == 0 or (i + 1) == total:
                print(f'[PROGRESS] {i+1}/{total} | OK={success} | no_face={no_face} | err={errors} | ETA={int(eta)}s')
            else:
                print(f'[{i+1}/{total}] ID={pid} faces={result.get("count", 0)} OK={success} no_face={no_face} err={errors} ETA={int(eta)}s')

    elapsed = time.time() - start
    print()
    print('=== DONE (BLAZEFACE) ===')
    print(f'Total: {total} | Success: {success} | No face: {no_face} | Errors: {errors}')
    print(f'Time: {int(elapsed)}s ({elapsed/total if total else 0:.1f}s/photo)')
    print(f'Photos in DB: {koleksi_foto.count_documents({})}')
    print(f'Embeddings in DB: {koleksi_wajah.count_documents({})}')
