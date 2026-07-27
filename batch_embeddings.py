import os
import sys
import time
import tempfile
import numpy as np
from PIL import Image
from io import BytesIO
from multiprocessing import Pool, cpu_count
from pymongo import MongoClient
from deepface import DeepFace

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

MEDIA_ROOT = '/Users/macos/Downloads/aplikasi_photo_manajemen/media'
CROP_DIR = os.path.join(MEDIA_ROOT, 'face_crops')
MAX_RESIZE = 800
NUM_WORKERS = 4

MONGO_URI = 'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority'

def l2_normalize(x):
    return x / np.sqrt(np.maximum(np.sum(np.square(x), axis=-1, keepdims=True), 1e-6))

def resolve_image_path(image_name):
    if not image_name:
        return None
    fname = os.path.basename(image_name)
    candidates = [
        os.path.join(MEDIA_ROOT, image_name),
        os.path.join(MEDIA_ROOT, 'lomba_lari', image_name),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    if 'lomba_lari/' in image_name:
        direct = os.path.join(MEDIA_ROOT, image_name)
        if os.path.exists(direct):
            return direct
    for subdir in ['tientorun','colorun','carfreeday','milo','kemerdekaan','ui_ecorun']:
        alt = os.path.join(MEDIA_ROOT, 'lomba_lari', subdir, fname)
        if os.path.exists(alt):
            return alt
        alt2 = os.path.join(MEDIA_ROOT, subdir, fname)
        if os.path.exists(alt2):
            return alt2
    return None

def process_one(photo_tuple):
    photo_id, image_name = photo_tuple
    try:
        img_path = resolve_image_path(image_name)
        if not img_path or not os.path.exists(img_path):
            return {'photo_id': photo_id, 'status': 'path_missing'}

        orig_img = Image.open(img_path)
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
        for res in results:
            vec = np.array(res['embedding'], dtype=np.float32)
            vec = l2_normalize(vec)
            bbox = res['facial_area']
            rx, ry, rw, rh = bbox['x'], bbox['y'], bbox['w'], bbox['h']

            ox = int(rx / resize_factor) if resize_factor < 1.0 else rx
            oy = int(ry / resize_factor) if resize_factor < 1.0 else ry
            ow = int(rw / resize_factor) if resize_factor < 1.0 else rw
            oh = int(rh / resize_factor) if resize_factor < 1.0 else rh

            area_pct = (ow * oh) / (orig_w * orig_h) * 100
            if area_pct > 80:
                continue

            pad_x, pad_y = int(ow * 0.2), int(oh * 0.2)
            x1 = max(0, ox - pad_x)
            y1 = max(0, oy - pad_y)
            x2 = min(orig_w, ox + ow + pad_x)
            y2 = min(orig_h, oy + oh + pad_y)

            face_crop = orig_img.crop((x1, y1, x2, y2))
            max_crop = 400
            if max(face_crop.size) > max_crop:
                cr = max_crop / max(face_crop.size)
                face_crop = face_crop.resize(
                    (int(face_crop.width * cr), int(face_crop.height * cr)),
                    Image.LANCZOS
                )

            buffer = BytesIO()
            face_crop.save(buffer, format='JPEG', quality=90)
            crop_filename = f"face_{photo_id}_{count}.jpg"
            crop_path = os.path.join(CROP_DIR, crop_filename)
            with open(crop_path, 'wb') as f:
                f.write(buffer.getvalue())

            faces.append({
                'photo_id': photo_id,
                'bbox_json': {'x': ox, 'y': oy, 'w': ow, 'h': oh},
                'embedding_data': vec.tobytes(),
                'face_image': f'face_crops/{crop_filename}',
            })
            count += 1

        return {'photo_id': photo_id, 'status': 'ok', 'faces': faces, 'count': count}
    except Exception as e:
        return {'photo_id': photo_id, 'status': 'error', 'error': str(e)}

if __name__ == '__main__':
    print(f"=== BATCH EMBEDDING (MTCNN, {NUM_WORKERS} workers) ===")

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=30000)
    db = client['db_tugasakhir']
    koleksi_foto = db['photos_photoevent']
    koleksi_wajah = db['photos_faceembedding']

    koleksi_wajah.delete_many({})
    print("Cleared old embeddings")

    os.makedirs(CROP_DIR, exist_ok=True)

    all_photos = [(p['id'], p.get('image', '')) for p in koleksi_foto.find()]
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
    print(f"Embeddings in DB: {koleksi_wajah.count_documents({})}")
