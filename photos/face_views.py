import os
import re
import time
import hashlib
import logging
import numpy as np
from PIL import Image, ImageOps
from io import BytesIO
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.core.paginator import Paginator
from django.conf import settings
from config.db import db as mongo_db

logger = logging.getLogger(__name__)

koleksi_foto = mongo_db['photos_photoevent']
koleksi_foto_legacy = mongo_db['photos']
koleksi_wajah = mongo_db['photos_faceembedding']

# ============================================
# COLLECTION KHUSUS EXPERIMEN BLAZEFACE
# Embedding di collection ini dihasilkan oleh
# pipeline BlazeFace (deteksi mediapipe + crop,
# lalu embedding Facenet dg detector_backend='skip').
# ============================================
koleksi_foto_blaze = mongo_db['photos_photoevent_blaze']
koleksi_wajah_blaze = mongo_db['photos_faceembedding_blaze']

def _get_deepface():
    from deepface import DeepFace
    return DeepFace

def l2_normalize(x):
    return x / np.sqrt(np.maximum(np.sum(np.square(x), axis=-1, keepdims=True), 1e-6))

THRESHOLD = 0.50
# Threshold khusus pipeline BlazeFace (lebih ketat).
BLAZE_THRESHOLD = 0.35
ITEMS_PER_PAGE = 12
CACHE_TIMEOUT = 3600

# ==========================================
# FEATURE TOGGLE: BIB SEARCH FLOW
# Set True = Event selection first (new flow)
# Set False = Direct BIB search (original flow)
# ==========================================
USE_EVENT_SELECTION_FOR_BIB = True

# ==========================================
# HELPER FUNCTIONS FOR EVENT/FOLDER
# ==========================================
def _folder_event(image_path):
    """Extract event folder from image path 'lomba_lari/<folder>/<file>'.
    
    Example:
      'lomba_lari/colorun/ColorRun_Fest(1).jpg' -> 'colorun'
      'lomba_lari/tientorun/Tiento_Run(1).JPG'  -> 'tientorun'
    """
    if not image_path:
        return ''
    img = image_path.replace('\\', '/')
    parts = [p for p in img.split('/') if p]
    if len(parts) >= 3 and parts[0].lower() == 'lomba_lari':
        return parts[1]
    return ''

def _folder_label(folder):
    """Convert folder name to display label.
    
    Example: 'colorun' -> 'Color Run', 'milo_race_2026' -> 'Milo Race 2026'
    """
    mapping = {
        'tientorun': 'Tiento Run',
        'colorun': 'Color Run',
        'carfreeday': 'Car Free Day',
        'milo': 'Milo',
        'milo_race_2026': 'Milo Race 2026',
        'merdeka': 'Kemerdekaan',
        'kemerdekaan': 'Kemerdekaan',
        'ui_ecorun': 'UI ECO Run',
    }
    if folder in mapping:
        return mapping[folder]
    return folder.replace('_', ' ').title()

def _get_event_list():
    """Get list of unique event folders from database."""
    folders = set()
    for d in koleksi_foto.find({}, {'image': 1}):
        f = _folder_event(d.get('image'))
        if f:
            folders.add(f)
    sorted_folders = sorted(folders)
    return [{'folder': f, 'label': _folder_label(f)} for f in sorted_folders]

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


def _attach_face_crops_batch(photos, koleksi_wajah_ref):
    """
    Ikat face_crop_url ke banyak foto sekaligus dgn SATU query `$in`,
    menghindari round-trip `find_one` per foto (penyebab lambat saat pagination).
    """
    ids = [p.id for p in photos if p.id is not None]
    if not ids:
        return
    crop_map = {}
    for wajah in koleksi_wajah_ref.find({'photo_id': {'$in': ids}}):
        pid = wajah.get('photo_id')
        if pid in crop_map:
            continue
        crop_map[pid] = wajah
    for photo in photos:
        face_doc = crop_map.get(photo.id)
        if face_doc and face_doc.get('face_image'):
            photo.face_crop_url = f"/media/{face_doc['face_image']}"
        elif face_doc and face_doc.get('bbox_json'):
            photo.face_crop_url = photo.image_url
        else:
            photo.face_crop_url = ''

def cari_foto_mirip_generic(query_vec, threshold_real, koleksi_foto_ref, koleksi_wajah_ref, exclude_photo_id=None):
    photos_map = {}
    for p in koleksi_foto_ref.find():
        pid = p.get('id')
        if pid is None:
            continue
        obj = PhotoObj(p)
        obj.similarity = 0
        obj._dist = float('inf')
        photos_map[pid] = obj

    # Untuk tiap embedding: hitung skor, simpan skor TERBAIK per foto.
    for wajah in koleksi_wajah_ref.find():
        photo_obj = photos_map.get(wajah.get('photo_id'))
        if photo_obj is None or photo_obj.id == exclude_photo_id:
            continue
        db_vec = np.frombuffer(wajah.get('embedding_data', b''), dtype=np.float32).copy()
        if db_vec.shape[0] != 128:
            continue
        db_vec = l2_normalize(db_vec)
        cosine_similarity = np.dot(query_vec, db_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(db_vec))
        dist_cosine = 1 - cosine_similarity
        if dist_cosine < photo_obj._dist:
            photo_obj._dist = dist_cosine
            photo_obj.similarity = round(float(cosine_similarity) * 100, 1)

    # Hanya foto yg lolos threshold, lalu urutkan DRASCENDING similarity (terbesar -> terkecil).
    hasil = [obj for obj in photos_map.values() if obj._dist <= threshold_real]
    hasil.sort(key=lambda p: p.similarity, reverse=True)
    return hasil


def cari_foto_mirip(query_vec, threshold_real, exclude_photo_id=None):
    return cari_foto_mirip_generic(query_vec, threshold_real, koleksi_foto, koleksi_wajah, exclude_photo_id)


def cari_foto_mirip_blaze(query_vec, threshold_real, exclude_photo_id=None):
    return cari_foto_mirip_generic(query_vec, threshold_real, koleksi_foto_blaze, koleksi_wajah_blaze, exclude_photo_id)

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
                    'active_page': 'search',
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
                        'active_page': 'search',
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
            'active_page': 'search',
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
                'active_page': 'search',
            })

    request.session.pop('last_search_results', None)
    request.session.pop('last_search_selfie', None)
    return render(request, 'photos/face_results.html', {'active_page': 'search'})

# ==========================================
# VIEW: CARI BIB
# ==========================================
def _norm_bib(s):
    """Normalize BIB input: keep alphanumeric uppercase, strip spaces/separators."""
    return re.sub(r'[^A-Za-z0-9]+', '', (s or '').upper())


def _is_valid_bib_input(s):
    bib = _norm_bib(s)
    return bool(bib)


def _bib_token_matches(token, target):
    token = _norm_bib(token)
    target = _norm_bib(target)
    if not token or not target:
        return False
    if token == target:
        return True
    # Support OCR output that may have trailing/leading zero noise.
    return token.lstrip('0') == target.lstrip('0') or token == target.lstrip('0') or token.lstrip('0') == target

def _bib_search_photos(bib_input, event=None):
    """
    Core BIB search logic with optional event filtering.

    Supports these DB shapes:
    - '51012'
    - '051012'
    - '51,012'
    - ['51012', '...']

    Matching is digit-only and exact after normalization, with a small tolerance
    for leading-zero noise from OCR.
    
    Args:
        bib_input: BIB number to search for
        event: Optional event folder name to filter by (e.g. 'colorun', 'tientorun')
    """
    bib_input = _norm_bib(bib_input)
    if not bib_input:
        return []

    results = []
    seen_ids = set()
    logger.info("BIB search start query=%r normalized=%r event=%r", bib_input, bib_input, event)

    for collection_name, collection in (("photos_photoevent", koleksi_foto), ("photos", koleksi_foto_legacy)):
        try:
            count = collection.count_documents({'bib_number': {'$nin': [None, '']}})
        except Exception:
            count = -1
        logger.info("BIB search scanning collection=%s candidate_count=%s", collection_name, count)

        for p in collection.find({'bib_number': {'$nin': [None, '']}}):
            pid = p.get('id') or p.get('_id')
            raw_bib = p.get('bib_number')
            
            # Filter by event folder if specified
            if event:
                img_path = p.get('image', '')
                photo_folder = _folder_event(img_path)
                if photo_folder != event:
                    continue
            
            logger.info(
                "BIB check collection=%s pid=%r bib_number=%r type=%s",
                collection_name, pid, raw_bib, type(raw_bib).__name__
            )

            if pid in seen_ids:
                logger.info("BIB skip duplicate pid=%r", pid)
                continue
            if raw_bib is None:
                logger.info("BIB skip pid=%r reason=None bib_number", pid)
                continue

            candidates = []
            if isinstance(raw_bib, (list, tuple, set)):
                candidates = list(raw_bib)
            else:
                raw_bib = str(raw_bib).strip()
                if not raw_bib:
                    logger.info("BIB skip pid=%r reason=empty-string bib_number", pid)
                    continue
                candidates = [t.strip() for t in raw_bib.split(',') if t.strip()]

            normalized_candidates = [_norm_bib(t) for t in candidates]
            logger.info("BIB candidates pid=%r candidates=%r normalized=%r", pid, candidates, normalized_candidates)

            matched = any(_bib_token_matches(t, bib_input) for t in candidates)
            logger.info("BIB match pid=%r matched=%s", pid, matched)
            if matched:
                seen_ids.add(pid)
                photo_obj = PhotoObj(p)
                set_event_metadata(photo_obj)
                _attach_face_crop(photo_obj)
                results.append(photo_obj)

    logger.info("BIB search done query=%r results=%d", bib_input, len(results))
    return results


def _bib_photo_to_dict(p):
    return {
        'id': p.id,
        'image_url': p.image_url,
        'event_name': p.event_name,
        'event_location': p.event_location,
        'event_date': p.event_date,
        'bib_number': p.bib_number,
        'face_crop_url': p.face_crop_url,
    }


def bib_search(request):
    """
    BIB search with configurable flow (toggle via USE_EVENT_SELECTION_FOR_BIB).
    - If True: Two-step flow (event selection → BIB input)
    - If False: Original direct BIB search (no event selection)
    """
    
    if USE_EVENT_SELECTION_FOR_BIB:
        # ========================================
        # NEW FLOW: Event selection first
        # ========================================
        event = request.GET.get('event', '').strip()
        
        # Step 1: No event selected → show event selection page
        if not event:
            event_list = _get_event_list()
            return render(request, 'photos/bib_event_select.html', {
                'event_list': event_list,
                'active_page': 'search',
            })
        
        # Step 2 & 3: Event selected → show BIB form and handle search
        event_label = _folder_label(event)
        
        if request.method == 'POST':
            bib_number = _norm_bib(request.POST.get('bib_number', ''))
            if not _is_valid_bib_input(bib_number):
                return render(request, 'photos/bib_results.html', {
                    'pesan': 'Masukkan nomor bib yang valid (angka dan/atau huruf).',
                    'berhasil': False,
                    'bib_number': bib_number,
                    'event': event,
                    'event_label': event_label,
                    'active_page': 'search',
                })

            # Search with event filter
            hasil_foto = _bib_search_photos(bib_number, event=event)

            if hasil_foto:
                paginator = Paginator(hasil_foto, ITEMS_PER_PAGE)
                page_obj = paginator.get_page(1)
                return render(request, 'photos/bib_results.html', {
                    'pesan': f"Berhasil! Ditemukan {len(hasil_foto)} foto dengan nomor bib '{bib_number}' di event {event_label}.",
                    'berhasil': True,
                    'page_obj': page_obj,
                    'page_range': get_page_range(page_obj),
                    'hasil_foto': page_obj.object_list,
                    'bib_number': bib_number,
                    'event': event,
                    'event_label': event_label,
                    'active_page': 'search',
                })
            else:
                return render(request, 'photos/bib_results.html', {
                    'pesan': f"Tidak ditemukan foto dengan nomor bib '{bib_number}' di event {event_label}.",
                    'berhasil': False,
                    'bib_number': bib_number,
                    'event': event,
                    'event_label': event_label,
                    'active_page': 'search',
                })

        # GET with event → show BIB input form
        return render(request, 'photos/bib_results.html', {
            'event': event,
            'event_label': event_label,
            'active_page': 'search',
        })
    
    else:
        # ========================================
        # ORIGINAL FLOW: Direct BIB search
        # ========================================
        if request.method == 'POST':
            bib_number = _norm_bib(request.POST.get('bib_number', ''))
            if not _is_valid_bib_input(bib_number):
                return render(request, 'photos/bib_results.html', {
                    'pesan': 'Masukkan nomor bib yang valid (angka dan/atau huruf).',
                    'berhasil': False,
                    'bib_number': bib_number,
                    'active_page': 'search',
                })

            # Search without event filter (all events)
            hasil_foto = _bib_search_photos(bib_number, event=None)

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
                    'active_page': 'search',
                })
            else:
                return render(request, 'photos/bib_results.html', {
                    'pesan': f"Tidak ditemukan foto dengan nomor bib '{bib_number}'.",
                    'berhasil': False,
                    'bib_number': bib_number,
                    'active_page': 'search',
                })

        # GET → show BIB input form (no event selection)
        return render(request, 'photos/bib_results.html', {'active_page': 'search'})


def bib_search_api(request):
    """
    JSON endpoint for live (as-you-type) BIB search with optional event filtering.
    GET /photos/bib-search-api/?q=83&event=colorun
    -> {"count": N, "query": "83", "results": [{id, image_url, ...}]}
    """
    q = (request.GET.get('q') or '').strip()
    event = (request.GET.get('event') or '').strip()
    logger.info("bib_search_api q=%r event=%r", q, event)
    if not q:
        logger.info("bib_search_api empty query")
        return JsonResponse({'count': 0, 'query': '', 'results': []})
    if not _is_valid_bib_input(q):
        return JsonResponse({'count': 0, 'query': q, 'results': [], 'error': 'BIB harus berupa angka dan/atau huruf.'}, status=400)

    # Hard cap so a single request never returns an absurd number of cards.
    # 60 is plenty for any realistic BIB (most have 1-5 photos).
    MAX_RESULTS = 60

    all_photos = _bib_search_photos(q, event=event)
    photos = all_photos[:MAX_RESULTS]
    logger.info("bib_search_api q=%r event=%r total=%d returned=%d truncated=%s", q, event, len(all_photos), len(photos), len(all_photos) > MAX_RESULTS)
    return JsonResponse({
        'count': len(photos),
        'query': q,
        'results': [_bib_photo_to_dict(p) for p in photos],
        'truncated': len(all_photos) > MAX_RESULTS,
    })


# ==========================================
# BLAZEFACE PIPELINE & VIEWS
#
# Embedding BlazeFace di collection *_blaze dibuat dengan
# pipeline EXACT seperti batch_blazeface_embeddings.py:
#   1. Deteksi wajah dg BlazeFaceProcessor (min_confidence 0.1,
#      model_selection 1, padding 0.2).
#   2. Crop wajah, resize max 400px.
#   3. Embedding dgn DeepFace Facenet detector_backend='skip'.
# Query selfie HARUS diproses dgn pipeline yg sama supaya
# embedding bisa dibandingkan secara konsisten.
# ==========================================
def _extract_blaze_embedding(img_path):
    """Deteksi BlazeFace + crop + embedding Facenet (skip). Return (vec, bbox, conf) or (None, None, None)."""
    try:
        from photos.blazeface_utils import BlazeFaceProcessor
    except Exception as e:
        logger.warning("blazeface_utils import gagal: %s", e)
        return None, None, None

    import tempfile
    processor = BlazeFaceProcessor(min_detection_confidence=0.1, model_selection=1)
    detections = processor.detect_faces(img_path)
    if not detections:
        return None, None, None

    orig_img = Image.open(img_path)
    try:
        orig_img = ImageOps.exif_transpose(orig_img)
    except Exception:
        pass
    orig_img = orig_img.convert('RGB')

    DeepFace = _get_deepface()
    for det in detections:
        bbox = det['bbox']
        x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
        if w <= 0 or h <= 0:
            continue
        crop = orig_img.crop((x, y, x + w, y + h))
        max_crop = 400
        if max(crop.size) > max_crop:
            ratio = max_crop / max(crop.size)
            crop = crop.resize((int(crop.width * ratio), int(crop.height * ratio)), Image.LANCZOS)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                crop.save(tmp.name, 'JPEG', quality=90)
                tmp_path = tmp.name
            emb = DeepFace.represent(
                img_path=tmp_path,
                model_name='Facenet',
                detector_backend='skip',
                enforce_detection=False,
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        if not emb:
            continue
        vec = np.array(emb[0]['embedding'], dtype=np.float32)
        vec = l2_normalize(vec)
        return vec, bbox, det.get('confidence', 0.0)

    return None, None, None


def _attach_face_crop_blaze(photo):
    """Deprecated: pakai _attach_face_crops_batch. Dibiarkan utk backward-compat."""
    face_doc = koleksi_wajah_blaze.find_one({'photo_id': photo.id})
    if face_doc and face_doc.get('face_image'):
        photo.face_crop_url = f"/media/{face_doc['face_image']}"
    elif face_doc and face_doc.get('bbox_json'):
        photo.face_crop_url = photo.image_url
    else:
        photo.face_crop_url = ''


def test_ai_blaze(request):
    """
    Face search khusus pipeline BlazeFace terhadap collection _blaze.
    Berfungsi seperti halaman /test-ai-blaze/ di proyek mirror,
    sekarang disajikan di /photos/face-search/.
    """
    if request.method == 'POST' and request.FILES.get('foto'):
        file_foto = request.FILES['foto']
        file_info_string = file_foto.name + str(file_foto.size)
        file_hash = hashlib.md5(file_info_string.encode('utf-8')).hexdigest()
        threshold_real = BLAZE_THRESHOLD
        cache_key = f"blaze_search_{file_hash}_{threshold_real}"
        request.session['last_search_cache_key'] = cache_key

        temp_name = f"temp_blaze_{file_foto.name}"
        temp_path = default_storage.save(temp_name, file_foto)
        full_path = os.path.join(default_storage.location, temp_path)

        selfie_rel = f"face_crops/blaze_selfie_{file_hash[:8]}.jpg"
        selfie_abs = os.path.join(settings.MEDIA_ROOT, selfie_rel)
        os.makedirs(os.path.dirname(selfie_abs), exist_ok=True)
        import shutil
        shutil.copy2(full_path, selfie_abs)

        hasil_foto = []
        pesan = ""
        berhasil = False
        waktu_total = 0

        try:
            t0 = time.time()
            selfie_vec, _, _ = _extract_blaze_embedding(full_path)

            if selfie_vec is not None:
                best_matches = cari_foto_mirip_blaze(selfie_vec, threshold_real)

                for photo in best_matches:
                    set_event_metadata(photo)
                # Batch attach face crop (1 query)
                _attach_face_crops_batch(best_matches, koleksi_wajah_blaze)
                hasil_foto = best_matches

                waktu_total = round(time.time() - t0, 4)

                if hasil_foto:
                    paginator = Paginator(hasil_foto, ITEMS_PER_PAGE)
                    page_obj = paginator.get_page(1)

                    match_data = [{'id': photo.id, 'similarity': photo.similarity} for photo in hasil_foto]
                    request.session['last_search_results'] = match_data
                    request.session['last_search_selfie'] = f"/media/{selfie_rel}"

                    # Sukses: jumlah sudah ditampilkan di header "Hasil Foto Ditemukan", jadi tak perlu alert.
                    pesan = ""
                    berhasil = True
                    return render(request, 'photos/test_ai.html', {
                        'pesan': pesan,
                        'berhasil': berhasil,
                        'page_obj': page_obj,
                        'page_range': get_page_range(page_obj),
                        'hasil_foto': page_obj.object_list,
                        'waktu_proses': waktu_total,
                        'selfie_url': f"/media/{selfie_rel}",
                        'mode': 'blaze',
                        'page_url_base': '/photos/face-search/',
                    })
                else:
                    pesan = "Wajah terdeteksi, tetapi tidak ditemukan di data BlazeFace."
            else:
                pesan = "Wajah tidak terdeteksi (BlazeFace)."

        except Exception as e:
            print(f"Error AI Blaze: {e}")
            pesan = f"Terjadi kesalahan sistem: {e}"
        finally:
            if os.path.exists(full_path):
                os.remove(full_path)

        return render(request, 'photos/test_ai.html', {
            'pesan': pesan,
            'berhasil': berhasil,
            'hasil_foto': hasil_foto,
            'waktu_proses': waktu_total,
            'mode': 'blaze',
            'page_url_base': '/photos/face-search/',
        })

    if request.method == 'GET' and request.GET.get('page'):
        cached = request.session.get('last_search_results')
        selfie_url = request.session.get('last_search_selfie')
        if cached and isinstance(cached, list) and len(cached) > 0 and isinstance(cached[0], dict):
            photo_ids = [item['id'] for item in cached]
            photos_docs = {p['id']: p for p in koleksi_foto_blaze.find({'id': {'$in': photo_ids}})}
            hasil_foto = []
            for item in cached:
                doc = photos_docs.get(item['id'])
                if doc:
                    photo_obj = PhotoObj(doc)
                    photo_obj.similarity = item['similarity']
                    set_event_metadata(photo_obj)
                    hasil_foto.append(photo_obj)
            # Batch attach face crop (1 query, bukan per-foto)
            _attach_face_crops_batch(hasil_foto, koleksi_wajah_blaze)
            page_num = int(request.GET.get('page', 1))
            paginator = Paginator(hasil_foto, ITEMS_PER_PAGE)
            page_obj = paginator.get_page(page_num)
            return render(request, 'photos/test_ai.html', {
                'pesan': '',
                'berhasil': True,
                'page_obj': page_obj,
                'page_range': get_page_range(page_obj),
                'hasil_foto': page_obj.object_list,
                'selfie_url': selfie_url,
                'waktu_proses': 0,
                'mode': 'blaze',
                'page_url_base': '/photos/face-search/',
            })

    request.session.pop('last_search_results', None)
    request.session.pop('last_search_selfie', None)
    return render(request, 'photos/test_ai.html', {
        'mode': 'blaze',
        'page_url_base': '/photos/face-search/',
        'active_page': 'search',
    })


def cari_serupa_blaze(request, photo_id):
    """Cari foto sejenis dari referensi di collection blaze (KF-U05)."""
    threshold_real = BLAZE_THRESHOLD
    cache_key = f"cari_serupa_blaze_{photo_id}_{threshold_real}"

    t1_mulai = time.time()
    cached_data = cache.get(cache_key)
    t1 = round(time.time() - t1_mulai, 4)
    t2 = None

    if cached_data:
        photo_ids = [item['id'] for item in cached_data]
        photos_docs = {p['id']: p for p in koleksi_foto_blaze.find({'id': {'$in': photo_ids}})}
        hasil_foto = []
        for item in cached_data:
            doc = photos_docs.get(item['id'])
            if doc:
                photo_obj = PhotoObj(doc)
                photo_obj.similarity = item['similarity']
                set_event_metadata(photo_obj)
                hasil_foto.append(photo_obj)
        _attach_face_crops_batch(hasil_foto, koleksi_wajah_blaze)
        waktu_proses = t1
    else:
        t2_mulai = time.time()
        wajah_referensi = koleksi_wajah_blaze.find_one({'photo_id': int(photo_id)})
        if not wajah_referensi:
            return render(request, 'photos/test_ai.html', {
                'pesan': 'Data wajah referensi (BlazeFace) tidak ditemukan.',
                'berhasil': False,
                'mode': 'blaze',
                'page_url_base': '/photos/face-search/',
            })

        query_vec = np.frombuffer(wajah_referensi.get('embedding_data', b''), dtype=np.float32).copy()
        query_vec = l2_normalize(query_vec)
        hasil_foto = cari_foto_mirip_blaze(query_vec, threshold_real=threshold_real, exclude_photo_id=int(photo_id) if isinstance(photo_id, int) else photo_id)

        t2 = round(time.time() - t2_mulai, 4)
        waktu_proses = round(t1 + t2, 4)

        if hasil_foto:
            match_data = [{'id': photo.id, 'similarity': photo.similarity} for photo in hasil_foto]
            cache.set(cache_key, match_data, 12096000)

    for photo in hasil_foto:
        set_event_metadata(photo)
    _attach_face_crops_batch(hasil_foto, koleksi_wajah_blaze)

    request.session['last_search_cache_key'] = cache_key
    request.session['last_search_results'] = [{'id': photo.id, 'similarity': photo.similarity} for photo in hasil_foto]

    if not hasil_foto:
        return render(request, 'photos/test_ai.html', {
            'pesan': "Tidak ditemukan foto lain yang sejenis (BlazeFace).",
            'berhasil': False,
            'mode': 'blaze',
            'page_url_base': '/photos/face-search/',
        })

    paginator = Paginator(hasil_foto, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(1)

    return render(request, 'photos/test_ai.html', {
        'pesan': '',
        'berhasil': True,
        'page_obj': page_obj,
        'page_range': get_page_range(page_obj),
        'hasil_foto': page_obj.object_list,
        'waktu_proses': waktu_proses,
        'mode': 'blaze',
        'page_url_base': '/photos/face-search/',
    })
