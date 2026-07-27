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
from django.conf import settings
from config.db import db as mongo_db

koleksi_foto = mongo_db['photos_photoevent']
koleksi_wajah = mongo_db['photos_faceembedding']


def _get_deepface():
    from deepface import DeepFace
    return DeepFace


def l2_normalize(x):
    return x / np.sqrt(np.maximum(np.sum(np.square(x), axis=-1, keepdims=True), 1e-6))


THRESHOLD = 0.50
ITEMS_PER_PAGE = 12
CACHE_TIMEOUT = 3600


class PhotoObj:
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
        if 'tiento' in nama_file_lower:
            return f"/media/lomba_lari/tientorun/{nama_file}"
        elif 'colorun' in nama_file_lower or 'color' in nama_file_lower:
            return f"/media/lomba_lari/colorun/{nama_file}"
        elif 'carfree' in nama_file_lower or 'cfd' in nama_file_lower:
            return f"/media/lomba_lari/carfreeday/{nama_file}"
        elif 'milo' in nama_file_lower:
            return f"/media/lomba_lari/milo/{nama_file}"
        elif 'merdeka' in nama_file_lower or 'kemerdekaan' in nama_file_lower:
            return f"/media/lomba_lari/kemerdekaan/{nama_file}"
        elif 'ui_eco' in nama_file_lower or 'ecorun' in nama_file_lower:
            return f"/media/lomba_lari/ui_ecorun/{nama_file}"
        return f"/media/{image_name}"


def set_event_metadata(photo):
    folder_nama = photo.image_name.lower() if photo.image_name else ""

    if 'tiento' in folder_nama:
        photo.event_name = "Tiento Run 2026"
        photo.event_location = "Balai Kota, Bandung"
        photo.event_date = "28 Juni 2026"
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
    current = page_obj.number
    total = page_obj.paginator.num_pages
    start = max(current - window, 1)
    end = min(current + window, total)
    return range(start, end + 1)


def _attach_face_crop(photo):
    face_doc = koleksi_wajah.find_one({'photo_id': photo.id})
    if face_doc and face_doc.get('face_image'):
        photo.face_crop_url = f"/media/{face_doc['face_image']}"
    elif face_doc and face_doc.get('bbox_json'):
        photo.face_crop_url = photo.image_url
    else:
        photo.face_crop_url = ''


def cari_foto_mirip(query_vec, threshold_real, exclude_photo_id=None):
    all_matches = []
    photos_map = {}

    for p in koleksi_foto.find():
        pid = p.get('id')
        photos_map[pid] = PhotoObj(p)

    for wajah in koleksi_wajah.find():
        photo_obj = photos_map.get(wajah.get('photo_id'))
        if photo_obj is None or photo_obj.id == exclude_photo_id:
            continue
        db_vec = np.frombuffer(wajah.get('embedding_data', b''), dtype=np.float32).copy()
        if db_vec.shape[0] != 128:
            continue
        db_vec = l2_normalize(db_vec)
        cosine_similarity = np.dot(query_vec, db_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(db_vec))
        dist_cosine = 1 - cosine_similarity
        similarity_percent = round(float(cosine_similarity) * 100, 1)
        photo_obj.similarity = similarity_percent
        all_matches.append({'dist': dist_cosine, 'photo': photo_obj})

    all_matches.sort(key=lambda x: x['dist'])
    return [m['photo'] for m in all_matches if m['dist'] <= threshold_real]


# ==========================================
# VIEW: FACE RECOGNITION SEARCH
# ==========================================
def face_search(request):
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

                paginator = Paginator(hasil_foto, ITEMS_PER_PAGE)
                page_obj = paginator.get_page(1)

                pesan = f"Berhasil! Ditemukan {len(hasil_foto)} wajah yang paling mirip."
                berhasil = True
                return render(request, 'photos/face_results.html', {
                    'pesan': pesan,
                    'berhasil': berhasil,
                    'page_obj': page_obj,
                    'page_range': get_page_range(page_obj),
                    'hasil_foto': page_obj.object_list,
                    'waktu_proses': t1,
                    'selfie_url': f"/media/{selfie_rel}",
                })
            else:
                t2_mulai = time.time()

            DeepFace = _get_deepface()
            results = DeepFace.represent(
                img_path=full_path,
                model_name='Facenet',
                detector_backend='mtcnn',
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

                    similarity_percent = round(float(cosine_similarity) * 100, 1)
                    all_matches.append({'dist': dist_cosine, 'photo': photo_obj, 'similarity': similarity_percent})

                all_matches.sort(key=lambda x: x['dist'])
                best_matches = [m for m in all_matches if m['dist'] <= threshold_real]

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
                    paginator = Paginator(hasil_foto, ITEMS_PER_PAGE)
                    page_obj = paginator.get_page(1)

                    pesan = f"Berhasil! Ditemukan {len(hasil_foto)} wajah yang paling mirip."
                    berhasil = True
                    selfie_url = f"/media/{selfie_rel}"
                    request.session['last_search_results'] = match_data
                    request.session['last_search_selfie'] = selfie_url
                    request.session['last_search_waktu'] = {'waktu_total': waktu_total, 't1': t1, 't2': t2}
                    return render(request, 'photos/face_results.html', {
                        'pesan': pesan,
                        'berhasil': berhasil,
                        'page_obj': page_obj,
                        'page_range': get_page_range(page_obj),
                        'hasil_foto': page_obj.object_list,
                        'waktu_proses': waktu_total,
                        'selfie_url': selfie_url,
                    })
                else:
                    pesan = "Wajah Anda terdeteksi, namun tidak ditemukan di galeri event manapun."

        except Exception as e:
            print(f"Error AI: {e}")
            pesan = "Terjadi kesalahan saat memproses foto."
            waktu_total = 0

        finally:
            if os.path.exists(full_path):
                os.remove(full_path)

        return render(request, 'photos/face_results.html', {
            'pesan': pesan,
            'berhasil': berhasil,
            'hasil_foto': hasil_foto,
            'waktu_proses': waktu_total,
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
            paginator = Paginator(hasil_foto, ITEMS_PER_PAGE)
            page_obj = paginator.get_page(page_num)
            return render(request, 'photos/face_results.html', {
                'pesan': f"Menampilkan hasil pencarian ({len(hasil_foto)} wajah mirip).",
                'berhasil': True,
                'page_obj': page_obj,
                'page_range': get_page_range(page_obj),
                'hasil_foto': page_obj.object_list,
                'selfie_url': selfie_url,
                'waktu_proses': waktu_data.get('waktu_total'),
            })

    request.session.pop('last_search_results', None)
    request.session.pop('last_search_selfie', None)
    return render(request, 'photos/face_results.html')


# ==========================================
# VIEW: CARI BIB
# ==========================================
def bib_search(request):
    if request.method == 'POST':
        bib_number = request.POST.get('bib_number', '').strip()
        if not bib_number:
            return render(request, 'photos/bib_results.html', {
                'pesan': 'Masukkan nomor bib.',
                'berhasil': False,
            })

        hasil_foto = []
        for p in koleksi_foto.find({'bib_number': {'$regex': bib_number, '$options': 'i'}}):
            photo_obj = PhotoObj(p)
            set_event_metadata(photo_obj)
            _attach_face_crop(photo_obj)
            hasil_foto.append(photo_obj)

        if hasil_foto:
            paginator = Paginator(hasil_foto, ITEMS_PER_PAGE)
            page_obj = paginator.get_page(1)
            return render(request, 'photos/bib_results.html', {
                'pesan': f"Berhasil! Ditemukan {len(hasil_foto)} foto dengan nomor bib '{bib_number}'.",
                'berhasil': True,
                'page_obj': page_obj,
                'page_range': get_page_range(page_obj),
                'hasil_foto': page_obj.object_list,
                'bib_number': bib_number,
            })
        else:
            return render(request, 'photos/bib_results.html', {
                'pesan': f"Tidak ditemukan foto dengan nomor bib '{bib_number}'.",
                'berhasil': False,
                'bib_number': bib_number,
            })

    return render(request, 'photos/bib_results.html')
