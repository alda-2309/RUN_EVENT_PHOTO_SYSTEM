import os
import re
import time
import hashlib
import numpy as np
from PIL import Image
from io import BytesIO
from django.shortcuts import render, redirect 
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.core.paginator import Paginator
from deepface import DeepFace
from django.conf import settings
from core.mongo_db import koleksi_foto, koleksi_wajah, koleksi_foto_blaze, koleksi_wajah_blaze
from photos.models import PhotoEvent
from photos.face_utils import FaceProcessor

# ============================================
# KONSTANTA GLOBAL
# ============================================
THRESHOLD = 0.50
ITEMS_PER_PAGE = 12
CACHE_TIMEOUT = 3600

# Instance global FaceProcessor
face_processor = FaceProcessor()

# Alias untuk backward compatibility
l2_normalize = face_processor.normalize_embedding

# ==========================================
# HELPER: Ambil foto dari pymongo sebagai dict sederhana
# ==========================================
class PhotoObj:
    """Wrapper agar object pymongo bisa dipakai seperti Django model di template."""

    def __init__(self, doc):
        self.id = doc.get('id')
        self._id = doc.get('_id')
        self.event_name = doc.get('event_name', '')
        self.image_name = doc.get('image', '')
        self.bib_number = doc.get('bib_number', '')
        self.uploaded_at = doc.get('uploaded_at', '')
        self.similarity = 0
        self.event_location = ''
        self.event_date = ''
        self.face_crop_url = ''
        self._doc = doc

    @property
    def image_url(self):
        image_name = self.image_name
        if not image_name:
            return ''
        nama_file = image_name.split('/')[-1]
        nama_file_lower = nama_file.lower()
        full_name_lower = image_name.lower()
        if 'tiento' in nama_file_lower:
            return f"/media/lomba_lari/tientorun/{nama_file}"
        elif 'colorun' in nama_file_lower or 'color' in nama_file_lower:
            return f"/media/lomba_lari/colorun/{nama_file}"
        elif 'carfree' in nama_file_lower or 'cfd' in nama_file_lower:
            return f"/media/lomba_lari/carfreeday/{nama_file}"
        elif 'milo race 2026' in full_name_lower:
            return f"/media/lomba_lari/milo_race_2026/{nama_file}"
        elif 'milo' in nama_file_lower:
            return f"/media/lomba_lari/milo/{nama_file}"
        elif 'merdeka' in nama_file_lower or 'kemerdekaan' in nama_file_lower:
            return f"/media/lomba_lari/kemerdekaan/{nama_file}"
        elif 'ui_eco' in nama_file_lower or 'ecorun' in nama_file_lower:
            return f"/media/lomba_lari/ui_ecorun/{nama_file}"
        return f"/media/{image_name}"




# ==========================================
# FUNGSI HELPER: RANKING PENCARIAN WAJAH (dipakai upload baru & cari-serupa)
# ==========================================
def _cari_foto_mirip_generic(query_vec, threshold_real, koleksi_foto_ref, koleksi_wajah_ref, exclude_photo_id=None):
    all_matches = []
    photos_map = {}

    for p in koleksi_foto_ref.find():
        pid = p.get('id')
        photos_map[pid] = PhotoObj(p)

    for wajah in koleksi_wajah_ref.find():
        photo_obj = photos_map.get(wajah.get('photo_id'))
        if photo_obj is None or photo_obj.id == exclude_photo_id:
            continue
        db_vec = np.frombuffer(wajah.get('embedding_data', b''), dtype=np.float32).copy()
        if db_vec.shape[0] != 128:
            continue
        db_vec = l2_normalize(db_vec)

        similarity, dist_cosine = face_processor.calculate_similarity(query_vec, db_vec)
        similarity_percent = round(float(similarity) * 100, 1)
        photo_obj.similarity = similarity_percent
        all_matches.append({'dist': dist_cosine, 'photo': photo_obj})

    all_matches.sort(key=lambda x: x['dist'])
    return [m['photo'] for m in all_matches if m['dist'] <= threshold_real]


def cari_foto_mirip(query_vec, threshold_real, exclude_photo_id=None):
    return _cari_foto_mirip_generic(query_vec, threshold_real, koleksi_foto, koleksi_wajah, exclude_photo_id)


def cari_foto_mirip_blaze(query_vec, threshold_real, exclude_photo_id=None):
    return _cari_foto_mirip_generic(query_vec, threshold_real, koleksi_foto_blaze, koleksi_wajah_blaze, exclude_photo_id)


def set_event_metadata(photo):
    """Isi nama, lokasi, tanggal tampilan berdasarkan nama folder fisik foto."""
    folder_nama = photo.image_name.lower() if photo.image_name else ""

    if 'tiento' in folder_nama:
        photo.event_name = "Tiento Run 2026"
        photo.event_location = "Balai Kota, Bandung"
        photo.event_date = "28 Juni 2026"
    elif 'milo_race_2026' in folder_nama or 'milo race 2026' in folder_nama:
        photo.event_name = "Milo Race 2026"
        photo.event_location = "-"
        photo.event_date = "-"
    elif 'milo' in folder_nama:
        photo.event_name = "MILO ACTIV Indonesia Race 2025"
        photo.event_location = "Kota Baru Parahyangan, Padalarang"
        photo.event_date = "1 Juni 2025"
    elif 'color' in folder_nama:
        photo.event_name = "Bandung Color Run Festival 2026"
        photo.event_location = "Laswi Heritage, Bandung"
        photo.event_date = "17 Mei 2026"
    elif 'carfreeday' in folder_nama:
        photo.event_name = "Car Free Day Fun"
        photo.event_location = "Jalan H.R. Rasuna Said, Kuningan, Jakarta Selatan"
        photo.event_date = "10 Mei 2026"
    elif 'kemerdekaan' in folder_nama:
        photo.event_name = "Independence Day Fun Run 2026"
        photo.event_location = "Gedung Sate, Bandung"
        photo.event_date = "2026"
    else:
        photo.event_name = "Vokasi UI ECO Run"
        photo.event_location = "Vokasi Universitas Indonesia, Depok"
        photo.event_date = "5 April 2026"

def get_page_range(page_obj, window=1):
    """Menghasilkan daftar nomor halaman di sekitar halaman aktif, misal [2,3,4]."""
    current = page_obj.number
    total = page_obj.paginator.num_pages
    start = max(current - window, 1)
    end = min(current + window, total)
    return range(start, end + 1)


# ==========================================
# 1. FUNGSI PROSES AI BACKGROUND (UNTUK ADMIN.PY)
# ==========================================
def proses_ai_dan_simpan(photo_obj):
    """Proses AI untuk foto yang sudah disimpan via admin.
    photo_obj bisa berupa Django PhotoEvent Model instance atau dict pymongo.
    """
    try:
        # Handle both Django Model instance and pymongo dict
        if hasattr(photo_obj, 'image'):  # Django Model
            img_path = photo_obj.image.path
            photo_id = str(photo_obj.id)
        else:  # pymongo dict
            img_path = os.path.join(settings.MEDIA_ROOT, photo_obj['image'])
            photo_id = str(photo_obj['_id'])

        img_pil = Image.open(img_path)

        # Gunakan FaceProcessor yang konsisten
        results = DeepFace.represent(
            img_path=img_path,
            model_name=face_processor.model_name,
            detector_backend=face_processor.detector_backend,
            enforce_detection=False
        )

        print(f"DEBUG: Jumlah wajah terdeteksi = {len(results)}")

        count = 0
        for res in results:
            vec = np.array(res["embedding"], dtype=np.float32)
            vec = l2_normalize(vec)

            bbox = res["facial_area"]
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            pad_x, pad_y = int(w * 0.2), int(h * 0.2)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(img_pil.width, x + w + pad_x)
            y2 = min(img_pil.height, y + h + pad_y)
            face_crop = img_pil.crop((x1, y1, x2, y2))

            buffer = BytesIO()
            face_crop.save(buffer, format='JPEG', quality=90)
            crop_filename = f"face_{photo_id}_{count}.jpg"
            crop_path = os.path.join(settings.MEDIA_ROOT, 'face_crops', crop_filename)
            os.makedirs(os.path.dirname(crop_path), exist_ok=True)
            with open(crop_path, 'wb') as f:
                f.write(buffer.getvalue())

            koleksi_wajah.insert_one({
                'photo_id': photo_id,
                'bbox_json': bbox,
                'embedding_data': vec.tobytes(),
                'face_image': f'face_crops/{crop_filename}',
            })
            count += 1
        return True, count
    except Exception as e:
        print(f"Error AI pada {photo_obj}: {e}")
        return False, 0


# ==========================================
# 2. VIEW UTAMA PENCARIAN WAJAH (MURNI AI)
# ==========================================
def _handle_search_request(request, koleksi_foto_ref, koleksi_wajah_ref, search_func):
    if request.method == 'POST' and request.FILES.get('foto'):
        file_foto = request.FILES['foto']

        file_info_string = file_foto.name + str(file_foto.size)
        file_hash = hashlib.md5(file_info_string.encode('utf-8')).hexdigest()

        threshold_real = THRESHOLD

        cache_key = f"ai_search_{file_hash}_{threshold_real}"

        request.session['last_search_cache_key'] = cache_key

        temp_name = f"temp_{file_foto.name}"
        temp_path = default_storage.save(temp_name, file_foto)
        full_path = os.path.join(default_storage.location, temp_path)

        selfie_rel = f"face_crops/selfie_{file_hash[:8]}.jpg"
        selfie_abs = os.path.join(settings.MEDIA_ROOT, selfie_rel)
        os.makedirs(os.path.dirname(selfie_abs), exist_ok=True)
        import shutil
        shutil.copy2(full_path, selfie_abs)

        hasil_foto = []
        pesan = ""
        berhasil = False
        waktu_total = 0
        t1 = 0
        t2 = 0

        try:
            t1_mulai = time.time()
            cached_data = cache.get(cache_key)
            t1 = round(time.time() - t1_mulai, 4)

            if cached_data:
                print("\n" + "="*60)
                print(f"[REDIS HIT] Key: {cache_key} | T1: {t1} detik")

                photo_ids = [item['id'] for item in cached_data]
                photos_docs = {p['id']: p for p in koleksi_foto.find({'id': {'$in': photo_ids}})}

                hasil_foto = []
                for item in cached_data:
                    doc = photos_docs.get(item['id'])
                    if doc:
                        photo_obj = PhotoObj(doc)
                        photo_obj.similarity = item['similarity']
                        set_event_metadata(photo_obj)
                        _attach_face_crop(photo_obj)
                        hasil_foto.append(photo_obj)

                paginator = Paginator(hasil_foto, 12)
                page_obj = paginator.get_page(1)

                pesan = f"Berhasil! Ditemukan {len(hasil_foto)} wajah yang paling mirip."
                berhasil = True
                return render(request, 'photos/test_ai.html', {
                    'pesan': pesan,
                    'berhasil': berhasil,
                    'page_obj': page_obj,
                    'page_range': get_page_range(page_obj),
                    'hasil_foto': page_obj.object_list,
                    'waktu_proses': t1,
                    't1': t1,
                    't2': None,
                })

            else:
                t2_mulai = time.time()
                print("\n" + "-"*60)
                print(f"[REDIS MISS] Key: {cache_key} | T1: {t1} detik")
                print(f"Tindakan: Menjalankan ekstraksi fitur wajah DeepFace...")
                print("-"*60 + "\n")

                        # Gunakan FaceProcessor untuk ekstraksi embedding
            results = DeepFace.represent(
                img_path=full_path,
                model_name=face_processor.model_name,
                detector_backend=face_processor.detector_backend,
                enforce_detection=False
            )

            if results and len(results) > 0:
                selfie_vec = np.array(results[0]["embedding"], dtype=np.float32)
                selfie_vec = l2_normalize(selfie_vec)

                photos_map = {}
                for p in koleksi_foto.find():
                    pid = p.get('id')
                    photos_map[pid] = PhotoObj(p)

                all_matches = []

                print("\n=== DEBUG REAL PENCARIAN WAJAH (RANKING) ===")
                for wajah in koleksi_wajah.find():
                    photo_obj = photos_map.get(wajah.get('photo_id'))
                    if photo_obj is None:
                        continue

                    db_vec = np.frombuffer(wajah.get('embedding_data', b''), dtype=np.float32).copy()
                    if db_vec.shape[0] != 128:
                        continue
                    db_vec = l2_normalize(db_vec)

                    cosine_similarity = np.dot(selfie_vec, db_vec) / (np.linalg.norm(selfie_vec) * np.linalg.norm(db_vec))
                    dist_cosine = 1 - cosine_similarity

                    print(f"-> Foto ID: {photo_obj.id} | Threshold: {threshold_real} | Jarak Cosine: {dist_cosine:.4f}")

                    similarity_percent = round(float(cosine_similarity) * 100, 1)
                    all_matches.append({'dist': dist_cosine, 'photo': photo_obj, 'similarity': similarity_percent})
                print("=== END DEBUG RANKING ===\n")

                all_matches.sort(key=lambda x: x['dist'])

                best_matches = [m for m in all_matches if m['dist'] <= threshold_real]

                print("=== RINGKASAN HASIL FOTO YANG BERHASIL DIDAPATKAN ===")
                print(f"Total Ditemukan: {len(best_matches)} Hasil.")
                for item in best_matches:
                    nama_file = os.path.basename(item['photo'].image_name)
                    print(f"[LOLOS] -> ID: {item['photo'].id} | File: {nama_file} | Jarak Cosine: {item['dist']:.4f}")
                print("=====================================================")

                for item in best_matches:
                    photo = item['photo']
                    photo.similarity = item['similarity']
                    set_event_metadata(photo)
                    _attach_face_crop(photo)
                    hasil_foto.append(photo)

                t2 = round(time.time() - t2_mulai, 4)
                waktu_total = round(t1 + t2, 4)

                if hasil_foto:
                    match_data = [{'id': photo.id, 'similarity': photo.similarity} for photo in hasil_foto]
                    cache.set(cache_key, match_data, CACHE_TIMEOUT)

                if hasil_foto:
                    paginator = Paginator(hasil_foto, 12)
                    page_obj = paginator.get_page(1)

                    pesan = f"Berhasil! Ditemukan {len(hasil_foto)} wajah yang paling mirip."
                    berhasil = True
                    selfie_url = f"/media/{selfie_rel}"
                    match_data = [{'id': photo.id, 'similarity': photo.similarity} for photo in hasil_foto]
                    request.session['last_search_results'] = match_data
                    request.session['last_search_selfie'] = selfie_url
                    request.session['last_search_waktu'] = {'waktu_total': waktu_total, 't1': t1, 't2': t2}
                    return redirect('/?page=1')
                else:
                    pesan = "Wajah Anda terdeteksi, namun tidak ditemukan di galeri event manapun."

        except Exception as e:
            print(f"Error AI: {e}")
            pesan = "Terjadi kesalahan sistem."
            waktu_total = 0

        finally:
            if os.path.exists(full_path):
                os.remove(full_path)

        return render(request, 'photos/test_ai.html', {
            'pesan': pesan,
            'berhasil': berhasil,
            'hasil_foto': hasil_foto,
            'waktu_proses': waktu_total,
            't1': t1,
            't2': t2,
        })

    if request.method == 'GET' and request.GET.get('page'):
        cached = request.session.get('last_search_results')
        selfie_url = request.session.get('last_search_selfie')
        waktu_data = request.session.get('last_search_waktu', {})
        if cached and isinstance(cached, list) and len(cached) > 0 and isinstance(cached[0], dict):
            photo_ids = [item['id'] for item in cached]
            photos_docs = {p['id']: p for p in koleksi_foto.find({'id': {'$in': photo_ids}})}
            hasil_foto = []
            for item in cached:
                doc = photos_docs.get(item['id'])
                if doc:
                    photo_obj = PhotoObj(doc)
                    photo_obj.similarity = item['similarity']
                    set_event_metadata(photo_obj)
                    _attach_face_crop(photo_obj)
                    hasil_foto.append(photo_obj)
            page_num = int(request.GET.get('page', 1))
            paginator = Paginator(hasil_foto, 12)
            page_obj = paginator.get_page(page_num)
            return render(request, 'photos/test_ai.html', {
                'pesan': f"Menampilkan hasil pencarian ({len(hasil_foto)} wajah mirip).",
                'berhasil': True,
                'page_obj': page_obj,
                'page_range': get_page_range(page_obj),
                'hasil_foto': page_obj.object_list,
                'selfie_url': selfie_url,
                'waktu_proses': waktu_data.get('waktu_total'),
                't1': waktu_data.get('t1'),
                't2': waktu_data.get('t2'),
            })

    request.session.pop('last_search_results', None)
    request.session.pop('last_search_selfie', None)
    return render(request, 'photos/test_ai.html')


# ==========================================
# 2B. VIEW: CARI FOTO SEJENIS (KF-U05, TANPA UPLOAD ULANG)
# ==========================================
def _attach_face_crop(photo):
    """Attach face crop URL ke photo object."""
    face_doc = koleksi_wajah.find_one({'photo_id': photo.id})
    if face_doc and face_doc.get('face_image'):
        photo.face_crop_url = f"/media/{face_doc['face_image']}"
    elif face_doc and face_doc.get('bbox_json'):
        photo.face_crop_url = photo.image_url
    else:
        photo.face_crop_url = ''


def cari_serupa(request, photo_id):
    threshold_real = THRESHOLD
    cache_key = f"cari_serupa_{photo_id}_{threshold_real}"

    t1_mulai = time.time()
    cached_data = cache.get(cache_key)
    t1 = round(time.time() - t1_mulai, 4)
    t2 = None

    if cached_data:
        photo_ids = [item['id'] for item in cached_data]
        photos_docs = {p['id']: p for p in koleksi_foto.find({'id': {'$in': photo_ids}})}
        hasil_foto = []
        for item in cached_data:
            doc = photos_docs.get(item['id'])
            if doc:
                photo_obj = PhotoObj(doc)
                photo_obj.similarity = item['similarity']
                _attach_face_crop(photo_obj)
                hasil_foto.append(photo_obj)
        waktu_proses = t1
    else:
        t2_mulai = time.time()
        wajah_referensi = koleksi_wajah.find_one({'photo_id': photo_id})
        if not wajah_referensi:
            return render(request, 'photos/test_ai.html', {
                'pesan': 'Data wajah referensi tidak ditemukan.',
                'berhasil': False
            })

        query_vec = np.frombuffer(wajah_referensi.get('embedding_data', b''), dtype=np.float32).copy()
        query_vec = l2_normalize(query_vec)
        hasil_foto = cari_foto_mirip(query_vec, threshold_real=threshold_real, exclude_photo_id=photo_id)

        t2 = round(time.time() - t2_mulai, 4)
        waktu_proses = round(t1 + t2, 4)

        if hasil_foto:
            match_data = [{'id': photo.id, 'similarity': photo.similarity} for photo in hasil_foto]
            cache.set(cache_key, match_data, 12096000)

    for photo in hasil_foto:
        set_event_metadata(photo)
        _attach_face_crop(photo)

    request.session['last_search_cache_key'] = cache_key

    if not hasil_foto:
        return render(request, 'photos/test_ai.html', {
            'pesan': "Tidak ditemukan foto lain yang sejenis.",
            'berhasil': False
        })

    paginator = Paginator(hasil_foto, 12)
    page_obj = paginator.get_page(1)

    return render(request, 'photos/test_ai.html', {
        'pesan': f"Berhasil! Ditemukan {len(hasil_foto)} foto sejenis.",
        'berhasil': True,
        'page_obj': page_obj,
        'page_range': get_page_range(page_obj),
        'hasil_foto': page_obj.object_list,
        'waktu_proses': waktu_proses,
        't1': t1,
        't2': t2,
    })


def ganti_halaman(request):
    cache_key = request.session.get('last_search_cache_key')
    cached_data = cache.get(cache_key) if cache_key else None

    if not cached_data:
        return render(request, 'photos/test_ai.html', {
            'pesan': 'Sesi pencarian sudah habis, silakan upload ulang foto.',
            'berhasil': False,
            'waktu_proses': 0,
        })

    photo_ids = [item['id'] for item in cached_data]
    photos_docs = {p['id']: p for p in koleksi_foto.find({'id': {'$in': photo_ids}})}

    hasil_foto_urut = []
    for item in cached_data:
        doc = photos_docs.get(item['id'])
        if doc:
            photo_obj = PhotoObj(doc)
            photo_obj.similarity = item['similarity']
            set_event_metadata(photo_obj)
            _attach_face_crop(photo_obj)
            hasil_foto_urut.append(photo_obj)

    paginator = Paginator(hasil_foto_urut, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'photos/test_ai.html', {
        'pesan': f"Ditemukan {len(hasil_foto_urut)} wajah yang paling mirip.",
        'berhasil': True,
        'page_obj': page_obj,
        'page_range': get_page_range(page_obj),
        'hasil_foto': page_obj.object_list,
        'waktu_proses': 0,
    })


# ==========================================
# 3. FUNGSI PENGALIHAN URL
# ==========================================
def test_ai(request):
    return _handle_search_request(request, koleksi_foto, koleksi_wajah, cari_foto_mirip)

def index(request):
    return test_ai(request)

def landing_page(request):
    return test_ai(request)

def home(request):
    return test_ai(request)



# ==========================================
# DEMO: PEMBUKTIAN KONSEP CROPPING MANUAL
# ==========================================
def test_ai_blaze(request):
    """Search khusus BlazeFace (collection terpisah)."""
    if request.method == 'POST' and request.FILES.get('foto'):
        file_foto = request.FILES['foto']
        file_info_string = file_foto.name + str(file_foto.size)
        file_hash = hashlib.md5(file_info_string.encode('utf-8')).hexdigest()
        threshold_real = THRESHOLD
        cache_key = f"blaze_search_{file_hash}_{threshold_real}"

        temp_name = f"temp_blaze_{file_foto.name}"
        temp_path = default_storage.save(temp_name, file_foto)
        full_path = os.path.join(default_storage.location, temp_path)

        hasil_foto = []
        pesan = ""
        berhasil = False
        waktu_total = 0

        try:
            t0 = time.time()
            results = DeepFace.represent(
                img_path=full_path,
                model_name=face_processor.model_name,
                detector_backend=face_processor.detector_backend,
                enforce_detection=False,
            )

            if results and len(results) > 0:
                selfie_vec = np.array(results[0]["embedding"], dtype=np.float32)
                selfie_vec = l2_normalize(selfie_vec)
                best_matches = _cari_foto_mirip_generic(selfie_vec, threshold_real, koleksi_foto_blaze, koleksi_wajah_blaze)

                for photo in best_matches:
                    set_event_metadata(photo)
                    _attach_face_crop(photo)
                    hasil_foto.append(photo)

                waktu_total = round(time.time() - t0, 4)

                if hasil_foto:
                    paginator = Paginator(hasil_foto, 12)
                    page_obj = paginator.get_page(1)
                    pesan = f"Berhasil! Ditemukan {len(hasil_foto)} wajah yang paling mirip (BlazeFace)."
                    berhasil = True
                    return render(request, 'photos/test_ai.html', {
                        'pesan': pesan,
                        'berhasil': berhasil,
                        'page_obj': page_obj,
                        'page_range': get_page_range(page_obj),
                        'hasil_foto': page_obj.object_list,
                        'waktu_proses': waktu_total,
                    })
                else:
                    pesan = "Wajah terdeteksi, tetapi tidak ditemukan di data BlazeFace."
            else:
                pesan = "Wajah tidak terdeteksi."

        except Exception as e:
            pesan = f"Terjadi kesalahan sistem: {e}"
        finally:
            if os.path.exists(full_path):
                os.remove(full_path)

        return render(request, 'photos/test_ai.html', {
            'pesan': pesan,
            'berhasil': berhasil,
            'hasil_foto': hasil_foto,
            'waktu_proses': waktu_total,
        })

    return render(request, 'photos/test_ai.html', {'mode': 'blaze', 'page_url_base': '/test-ai-blaze/'})


def demo_crop_manual(request):
    subjek_terpilih = request.GET.get('subjek')

    data_config = {
        'alya': {
            'selfie': 'manual_Selfie.jpg',
            'foto': ['manual_1074.jpg', 'manual_1075.jpg', 'manual_1077.jpg', 'manual_1079.jpg', 'manual_1156.jpg', 'manual_554.JPG'],
        },
        'ira': {
            'selfie': 'manual_selfie.jpeg',
            'foto': ['manual_740.jpeg', 'manual_741.jpeg', 'manual_894.jpeg', 'manual_558.jpg'],
        },
        'fian': {
            'selfie': 'manual_selfie.jpeg',
            'foto': ['manual_741.jpeg', 'manual_894.jpeg', 'manual_556.JPG'],
        },
        'dida': {
            'selfie': 'manual_selfie.jpeg',
            'foto': ['manual_448.jpeg', 'manual_739.jpeg', 'manual_738.jpeg', 'manual_554.jpg'],
        },
    }

    hasil = None
    error = None

    if subjek_terpilih and subjek_terpilih in data_config:
        try:
            cfg = data_config[subjek_terpilih]
            folder = os.path.join(settings.MEDIA_ROOT, 'demo_crop_manual', subjek_terpilih)
            selfie_path = os.path.join(folder, cfg['selfie'])

            if not os.path.exists(selfie_path):
                error = f"File selfie tidak ditemukan: {cfg['selfie']}"
            else:
                                # Ekstrak selfie
                selfie_hasil = DeepFace.represent(
                    img_path=selfie_path,
                    model_name=face_processor.model_name,
                    detector_backend=face_processor.detector_backend,
                    enforce_detection=False
                )
                selfie_vec = l2_normalize(np.array(selfie_hasil[0]['embedding'], dtype=np.float32))

                hasil = []
                for f in cfg['foto']:
                    foto_path = os.path.join(folder, f)
                    if not os.path.exists(foto_path):
                        continue

                    # Ekstrak embedding dari foto CROP
                    r = DeepFace.represent(
                        img_path=foto_path,
                        model_name=face_processor.model_name,
                        detector_backend=face_processor.detector_backend,
                        enforce_detection=False
                    )
                    vec = l2_normalize(np.array(r[0]['embedding'], dtype=np.float32))
                    cos_sim = np.dot(selfie_vec, vec) / (np.linalg.norm(selfie_vec) * np.linalg.norm(vec))

                    # Ambil ID dari nama file crop (manual_1074.jpg -> 1074)
                    match = re.search(r'manual_(\d+)', f)
                    url_foto_asli = None
                    if match:
                        photo_id_asli = int(match.group(1))
                        photo_asli = PhotoEvent.objects.filter(id=photo_id_asli).first()
                        if photo_asli and photo_asli.image:
                            url_foto_asli = photo_asli.image.url  # ← FOTO ASLI (utuh)

                    hasil.append({
                        'nama_file': f,
                        'similarity': round(cos_sim * 100, 1),
                        'jarak': round(1 - cos_sim, 4),
                        # ✅ TAMPILKAN FOTO CROP
                        'url_foto_crop': f'/media/demo_crop_manual/{subjek_terpilih}/{f}',
                        # ✅ LINK KE FOTO ASLI (utuh)
                        'url_foto_asli': url_foto_asli,
                    })
                hasil.sort(key=lambda x: -x['similarity'])

        except Exception as e:
            error = f"Terjadi kesalahan: {str(e)}"

    return render(request, 'photos/demo_crop_manual.html', {
        'subjek_terpilih': subjek_terpilih,
        'hasil': hasil,
        'error': error,
    })