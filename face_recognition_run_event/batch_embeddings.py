import os
import sys
import time
import tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from io import BytesIO
from multiprocessing import Pool, cpu_count
from pymongo import MongoClient
from deepface import DeepFace

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

BASE_DIR = os.path.dirname(__file__)
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
CROP_DIR = os.path.join(MEDIA_ROOT, 'face_crops')
BBOX_DEBUG_DIR = os.path.join(MEDIA_ROOT, 'bbox_debug')
MAX_RESIZE = 800
NUM_WORKERS = 4

MONGO_URI = os.environ.get(
    'MONGO_URI',
    'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority'
)

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

def l2_normalize(x):
    return x / np.sqrt(np.maximum(np.sum(np.square(x), axis=-1, keepdims=True), 1e-6))

def iter_local_images():
    for event_folder, folder_path in EVENT_DIRS.items():
        if not os.path.exists(folder_path):
            continue
        for fname in os.listdir(folder_path):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                yield event_folder, os.path.join(folder_path, fname), fname

def process_one(photo_tuple):
    photo_id, event_folder, img_path, filename = photo_tuple
    try:
        orig_img = ImageOps.exif_transpose(Image.open(img_path)).convert('RGB')
        orig_w, orig_h = orig_img.size

        resize_factor = 1.0
        if max(orig_w, orig_h) > MAX_RESIZE:
            resize_factor = MAX_RESIZE / max(orig_w, orig_h)
            resized_img = orig_img.resize((int(orig_w * resize_factor), int(orig_h * resize_factor)), Image.LANCZOS)
        else:
            resized_img = orig_img

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            resized_img.save(tmp.name, 'JPEG', quality=90)
            tmp_path = tmp.name

        results = DeepFace.represent(
            img_path=tmp_path,
            model_name='Facenet',
            detector_backend='mtcnn',
            enforce_detection=False
        )
        os.unlink(tmp_path)

        faces = []
        count = 0
        debug_img = orig_img.copy()
        debug_draw = ImageDraw.Draw(debug_img)
        for res in results:
            vec = np.array(res['embedding'], dtype=np.float32)
            vec = l2_normalize(vec)
            bbox = res.get('facial_area', {})
            rx, ry, rw, rh = bbox.get('x', 0), bbox.get('y', 0), bbox.get('w', 0), bbox.get('h', 0)

            ox = int(rx / resize_factor) if resize_factor < 1.0 else rx
            oy = int(ry / resize_factor) if resize_factor < 1.0 else ry
            ow = int(rw / resize_factor) if resize_factor < 1.0 else rw
            oh = int(rh / resize_factor) if resize_factor < 1.0 else rh

            if ow <= 0 or oh <= 0:
                continue

            area_pct = (ow * oh) / (orig_w * orig_h) * 100
            if area_pct > 80:
                continue

            pad_x, pad_y = int(ow * 0.2), int(oh * 0.2)
            x1 = max(0, ox - pad_x)
            y1 = max(0, oy - pad_y)
            x2 = min(orig_w, ox + ow + pad_x)
            y2 = min(orig_h, oy + oh + pad_y)

            debug_draw.rectangle((x1, y1, x2, y2), outline='red', width=4)
            debug_draw.text((x1, max(0, y1 - 15)), f'{count}', fill='red')

            face_crop = orig_img.crop((x1, y1, x2, y2))
            max_crop = 400
            if max(face_crop.size) > max_crop:
                cr = max_crop / max(face_crop.size)
                face_crop = face_crop.resize((int(face_crop.width * cr), int(face_crop.height * cr)), Image.LANCZOS)

            buffer = BytesIO()
            face_crop.save(buffer, format='JPEG', quality=90)
            crop_filename = f"face_{event_folder}_{filename}_{count}.jpg".replace(' ', '_')
            crop_path = os.path.join(CROP_DIR, crop_filename)
            with open(crop_path, 'wb') as f:
                f.write(buffer.getvalue())

            faces.append({
                'photo_id': None,
                'event_folder': event_folder,
                'filename': filename,
                'image': f'lomba_lari/{event_folder}/{filename}',
                'event_name': EVENT_NAME_MAP.get(event_folder, event_folder),
                'bbox_json': {'x': ox, 'y': oy, 'w': ow, 'h': oh},
                'embedding_data': vec.tobytes(),
                'face_image': f'face_crops/{crop_filename}',
            })
            count += 1

        os.makedirs(BBOX_DEBUG_DIR, exist_ok=True)
        debug_filename = f"bbox_{event_folder}_{filename}".replace(' ', '_')
        debug_img.save(os.path.join(BBOX_DEBUG_DIR, debug_filename), format='JPEG', quality=90)

        return {'photo_id': photo_id, 'event_folder': event_folder, 'filename': filename, 'status': 'ok', 'faces': faces, 'count': count}
    except Exception as e:
        return {'photo_id': photo_id, 'event_folder': event_folder, 'filename': filename, 'status': 'error', 'error': str(e)}

def build_local_photo_docs(koleksi_foto):
    """Buat data foto di Mongo lokal langsung dari folder media."""
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

if __name__ == '__main__':
    print(f"=== BATCH EMBEDDING (MTCNN, {NUM_WORKERS} workers) ===")

    client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=30000)
    db = client['db_tugasakhir']
    koleksi_foto = db['photos_photoevent']
    koleksi_wajah = db['photos_faceembedding']

    koleksi_wajah.delete_many({})
    print("Cleared old embeddings")

    os.makedirs(CROP_DIR, exist_ok=True)

    local_docs = build_local_photo_docs(koleksi_foto)
    all_photos = [(pid, event_folder, img_path, filename) for pid, event_folder, img_path, filename, _doc in local_docs]
    total = len(all_photos)
    print(f"Photos: {total} | Workers: {NUM_WORKERS}")

    start = time.time()
    success = no_face = errors = 0

    with Pool(NUM_WORKERS) as pool:
        for i, result in enumerate(pool.imap(process_one, all_photos)):
            pid = result['photo_id']
            status = result['status']

            if status == 'path_missing':
                errors += 1
                print(f"[{i+1}/{total}] ID={pid} PATH_MISSING")
            elif status == 'error':
                errors += 1
                print(f"[{i+1}/{total}] ID={pid} ERROR: {result.get('error','')[:80]}")
            else:
                faces = result['faces']
                if faces:
                    for face in faces:
                        face['photo_id'] = pid
                        koleksi_wajah.insert_one(face)
                    success += 1
                else:
                    no_face += 1

                elapsed = time.time() - start
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (total - i - 1) / rate if rate > 0 else 0
                print(f"[{i+1}/{total}] ID={pid} faces={result['count']} OK={success} no_face={no_face} err={errors} ETA={int(eta)}s")

    elapsed = time.time() - start
    print()
    print(f"=== DONE ===")
    print(f"Total: {total} | Success: {success} | No face: {no_face} | Errors: {errors}")
    print(f"Time: {int(elapsed)}s ({elapsed/total:.1f}s/photo)")
    print(f"Photos in DB: {koleksi_foto.count_documents({})}")
    print(f"Embeddings in DB: {koleksi_wajah.count_documents({})}")
