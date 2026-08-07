from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from config.db import (
    photos_collection, events_collection, users_collection,
    event_types_collection, db,
    get_next_id, create_user, authenticate_user, update_last_login,
    hash_password, verify_password, get_event_types
)
from datetime import datetime

# ============================================================
# GALERI FOTO EVENT — sumber data utama galeri publik
# Data foto event lari berada di collection 'photos_photoevent'
# (path image: lomba_lari/<folder>/<file>).
# ============================================================
koleksi_galeri = db['photos_photoevent']
GALERI_PER_PAGE = 25


def _folder_event(image_path):
    """Ambil nama folder event dari path 'lomba_lari/<folder>/<file>'."""
    if not image_path:
        return ''
    img = image_path.replace('\\', '/')
    parts = [p for p in img.split('/') if p]
    if len(parts) >= 3 and parts[0].lower() == 'lomba_lari':
        return parts[1]
    return ''


def _list_folders():
    """Folder event unik dari data galeri (lomba_lari)."""
    folders = set()
    for d in koleksi_galeri.find({}, {'image': 1}):
        f = _folder_event(d.get('image'))
        if f:
            folders.add(f)
    return sorted(folders)


# Nama event tampilan untuk tiap folder (sinkron dengan data di DB).
EVENT_NAME_MAP = {
    'colorun': 'Bandung Color Run Festival 2026',
    'kemerdekaan': 'Independence Day Fun Run 2026',
    'merdeka': 'Independence Day Fun Run 2026',
    'milo': 'MILO ACTIV Indonesia Race 2025',
    'milo_race_2026': 'Milo Race 2026',
    'tientorun': 'Tiento Run 2026',
    'carfreeday': 'Car Free Day Fun',
    'ui_ecorun': 'Vokasi UI ECO Run',
}


def _folder_label(folder):
    """Label event ramah dari nama folder."""
    return EVENT_NAME_MAP.get(folder, folder.replace('_', ' ').title())


# ============================================================
# DECORATOR: cek login admin (staff / superuser)
# ============================================================
def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        user_id = request.session.get('user_id')
        is_logged_in = request.session.get('is_logged_in', False)

        if not (user_id and is_logged_in):
            messages.error(request, 'Silakan login terlebih dahulu.')
            return redirect('admin_login')

        user_data = users_collection.find_one({'_id': int(user_id)})
        if not user_data or not (user_data.get('is_staff') or user_data.get('is_superuser')):
            messages.error(request, 'Anda tidak memiliki akses admin.')
            return redirect('admin_login')

        request._mongo_user = user_data
        return view_func(request, *args, **kwargs)
    return wrapper

# ============================================================
# VIEWS — ADMIN
# ============================================================

def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user_data = authenticate_user(username, password)
        if user_data and (user_data.get('is_staff') or user_data.get('is_superuser')):
            update_last_login(user_data['_id'])
            request.session['user_id'] = user_data['_id']
            request.session['username'] = user_data['username']
            request.session['is_logged_in'] = True
            request.session['is_staff'] = user_data.get('is_staff', False)
            request.session['is_superuser'] = user_data.get('is_superuser', False)
            return redirect('admin_dashboard')
        else:
            if user_data:
                messages.error(request, 'Akun ini tidak memiliki akses admin.')
            else:
                messages.error(request, 'Username atau password salah.')

    return render(request, 'admin/login.html')

def logout_view(request):
    request.session.flush()
    return redirect('admin_login')

@admin_required
def dashboard(request):
    total_photos = koleksi_galeri.count_documents({})
    total_events = events_collection.count_documents({})

    events = list(events_collection.find())
    # Statistik per jenis event (event_type = jenis_event dari photos_photoevent)
    event_type_counts = {}
    for e in events:
        et = e.get('event_type') or 'Lainnya'
        event_type_counts[et] = event_type_counts.get(et, 0) + 1

    latest_uploads = list(koleksi_galeri.find().sort('id', -1).limit(5))
    for photo in latest_uploads:
        photo['event_name'] = photo.get('event_name', 'Unknown')
        photo['id'] = photo['_id']

    context = {
        'total_photos': total_photos,
        'total_events': total_events,
        'event_type_counts': event_type_counts,
        'latest_uploads': latest_uploads,
    }
    return render(request, 'dashboard/dashboard.html', context)

@admin_required
def event_list(request):
    events = list(events_collection.find().sort('_id', -1))
    for e in events:
        e['id'] = e['_id']
    q = request.GET.get('q')
    date = request.GET.get('date')

    if q:
        events = [e for e in events if q.lower() in e.get('event_type', '').lower()]
    if date:
        try:
            date_filter = datetime.strptime(date, '%Y-%m-%d').date()
            events = [e for e in events if e.get('timestamp') and e['timestamp'].date() == date_filter]
        except ValueError:
            pass

    return render(request, 'admin/event_list.html', {'events': events})

@admin_required
def event_add(request):
    if request.method == 'POST':
        event_data = {
            '_id': get_next_id('events'),
            'name': request.POST.get('name', '').strip(),
            'event_type': request.POST.get('event_type'),
            'timestamp': datetime.strptime(request.POST.get('timestamp'), '%Y-%m-%d %H:%M'),
            'location': request.POST.get('location'),
        }
        events_collection.insert_one(event_data)
        messages.success(request, '✅ Event berhasil ditambahkan!')
        return redirect('admin_event_list')
    return render(request, 'admin/event_add.html', {'event_types': get_event_types()})

@admin_required
def event_edit(request, event_id):
    event = events_collection.find_one({'_id': int(event_id)})
    if not event:
        messages.error(request, 'Event tidak ditemukan.')
        return redirect('admin_event_list')

    if request.method == 'POST':
        events_collection.update_one(
            {'_id': int(event_id)},
            {'$set': {
                'name': request.POST.get('name', '').strip(),
                'event_type': request.POST.get('event_type'),
                'timestamp': datetime.strptime(request.POST.get('timestamp'), '%Y-%m-%d %H:%M'),
                'location': request.POST.get('location'),
            }}
        )
        messages.success(request, '✅ Event berhasil diupdate!')
        return redirect('admin_event_list')

    return render(request, 'admin/event_edit.html', {
        'event': event,
        'event_types': get_event_types()
    })

@admin_required
def event_delete(request, event_id):
    events_collection.delete_one({'_id': int(event_id)})
    messages.success(request, '✅ Event berhasil dihapus!')
    return redirect('admin_event_list')

# ============================================================
# EVENT TYPES — Jenis Event (standalone table)
# Struktur: { _id: int, name: str, order: int, created_at: datetime }
# ============================================================

@admin_required
def event_type_list(request):
    types = list(event_types_collection.find().sort('order', 1))
    for t in types:
        t['id'] = t['_id']
    return render(request, 'admin/event_type_list.html', {'types': types})

@admin_required
def event_type_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Nama jenis event tidak boleh kosong.')
        elif event_types_collection.find_one({'name': name}):
            messages.error(request, f'Jenis event "{name}" sudah ada.')
        else:
            last = event_types_collection.find_one(sort=[('order', -1)])
            event_types_collection.insert_one({
                '_id': get_next_id('event_types'),
                'name': name,
                'order': (last['order'] + 1) if last else 0,
                'created_at': datetime.utcnow(),
            })
            messages.success(request, f'✅ Jenis event "{name}" berhasil ditambahkan!')
            return redirect('admin_event_type_list')
    return render(request, 'admin/event_type_add.html')

@admin_required
def event_type_edit(request, type_id):
    et = event_types_collection.find_one({'_id': int(type_id)})
    if not et:
        messages.error(request, 'Jenis event tidak ditemukan.')
        return redirect('admin_event_type_list')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Nama jenis event tidak boleh kosong.')
        elif event_types_collection.find_one({'name': name, '_id': {'$ne': int(type_id)}}):
            messages.error(request, f'Jenis event "{name}" sudah ada.')
        else:
            event_types_collection.update_one(
                {'_id': int(type_id)},
                {'$set': {'name': name}}
            )
            messages.success(request, '✅ Jenis event berhasil diupdate!')
            return redirect('admin_event_type_list')

    return render(request, 'admin/event_type_edit.html', {'type': et})

@admin_required
def event_type_delete(request, type_id):
    et = event_types_collection.find_one({'_id': int(type_id)})
    if et:
        event_types_collection.delete_one({'_id': int(type_id)})
        messages.success(request, f'✅ Jenis event "{et.get("name", "")}" dihapus!')
    return redirect('admin_event_type_list')

@admin_required
def event_detail(request):
    return render(request, 'admin/event_detail.html')

@admin_required
def photo_edit(request, photo_id):
    foto = photos_collection.find_one({'_id': int(photo_id)})
    if not foto:
        messages.error(request, 'Foto tidak ditemukan.')
        return redirect('admin_photo_list')

    if request.method == 'POST':
        update_fields = {
            'nama_event': request.POST.get('nama_event', ''),
            'jenis_event': request.POST.get('jenis_event', ''),
            'timestamp': datetime.strptime(request.POST.get('timestamp'), '%Y-%m-%d %H:%M'),
        }
        # Handle upload gambar baru
        if request.FILES.get('gambar'):
            from django.core.files.storage import default_storage
            import os
            from django.conf import settings
            # Hapus gambar lama
            old_path = os.path.join(settings.MEDIA_ROOT, foto.get('gambar', ''))
            if old_path and os.path.exists(old_path):
                os.remove(old_path)
            gambar = request.FILES['gambar']
            filepath = default_storage.save(f'foto/{gambar.name}', gambar)
            update_fields['gambar'] = filepath

        photos_collection.update_one(
            {'_id': int(photo_id)},
            {'$set': update_fields}
        )
        messages.success(request, '✅ Foto berhasil diupdate!')
        return redirect('admin_photo_list')

    return render(request, 'admin/photo_edit.html', {'foto': foto, 'event_types': get_event_types()})

@admin_required
def photo_list(request):
    fotos = list(photos_collection.find().sort('_id', -1))
    for f in fotos:
        f['id'] = f['_id']
    return render(request, 'admin/photo_list.html', {'fotos': fotos})

@admin_required
def photo_upload(request):
    try:
        from .forms import FotoForm
    except ImportError:
        from galeri.forms import FotoForm
    if request.method == 'POST':
        form = FotoForm(request.POST, request.FILES)
        if form.is_valid():
            gambar = request.FILES['gambar']
            from django.core.files.storage import default_storage
            filepath = default_storage.save(f'foto/{gambar.name}', gambar)

            photo_data = {
                '_id': get_next_id('photos'),
                'nama_event': form.cleaned_data['nama_event'],
                'gambar': filepath,
                'timestamp': form.cleaned_data['timestamp'],
                'jenis_event': form.cleaned_data['jenis_event'],
                'uploaded_at': datetime.utcnow(),
            }
            photos_collection.insert_one(photo_data)
            messages.success(request, '✅ Foto berhasil diupload!')
            return redirect('admin_photo_list')
    else:
        form = FotoForm()

    event_types = get_event_types()
    return render(request, 'admin/photo_upload.html', {'form': form, 'event_types': event_types})

@admin_required
def photo_delete(request, photo_id):
    foto = photos_collection.find_one({'_id': int(photo_id)})
    if foto:
        import os
        from django.conf import settings
        file_path = os.path.join(settings.MEDIA_ROOT, foto.get('gambar', foto.get('image', '')))
        if os.path.exists(file_path):
            os.remove(file_path)
        photos_collection.delete_one({'_id': int(photo_id)})
        messages.success(request, '✅ Foto berhasil dihapus!')
    return redirect('admin_photo_list')

@admin_required
def foto_list(request):
    fotos = list(photos_collection.find().sort('_id', -1))
    return render(request, 'admin/foto_list.html', {'fotos': fotos})

@admin_required
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        user_id = request.session.get('user_id')
        user_data = users_collection.find_one({'_id': int(user_id)})

        if not user_data:
            messages.error(request, 'User tidak ditemukan.')
            return redirect('admin_change_password')

        if not verify_password(current_password, user_data['password']):
            messages.error(request, 'Password saat ini salah.')
            return redirect('admin_change_password')

        if new_password != confirm_password:
            messages.error(request, 'Password baru tidak cocok.')
            return redirect('admin_change_password')

        if len(new_password) < 6:
            messages.error(request, 'Password baru minimal 6 karakter.')
            return redirect('admin_change_password')

        users_collection.update_one(
            {'_id': int(user_id)},
            {'$set': {'password': hash_password(new_password)}}
        )
        messages.success(request, '✅ Password berhasil diubah!')
        return redirect('admin_dashboard')

    return render(request, 'admin/change_password.html')

# ============================================================
# GALERI FOTO EVENT — ADMIN (photos_photoevent)
# ============================================================

@admin_required
def galeri_photo_list(request):
    """Daftar foto galeri event (photos_photoevent), filter by folder."""
    folder = (request.GET.get('folder') or '').strip()
    q = (request.GET.get('q') or '').strip()

    query = {}
    if folder:
        query['image'] = {'$regex': f'^lomba_lari/{folder}/'}
    if q:
        query['event_name'] = {'$regex': q, '$options': 'i'}

    cursor = koleksi_galeri.find(query).sort('id', 1)
    fotos = []
    for d in cursor:
        image_path = d.get('image', '')
        fotos.append({
            'id': d.get('id'),
            'image': f"/media/{image_path.replace(chr(92), '/')}",
            'folder': _folder_event(image_path),
            'event_name': d.get('event_name', ''),
            'bib_number': d.get('bib_number', ''),
            'ocr_raw_text': d.get('ocr_raw_text', ''),
        })

    paginator = Paginator(fotos, GALERI_PER_PAGE)
    page_obj = paginator.get_page(int(request.GET.get('page', 1)))

    return render(request, 'admin/galeri_photo_list.html', {
        'page_obj': page_obj,
        'fotos': page_obj.object_list,
        'folder_list': _list_folders(),
        'folder_selected': folder,
        'q': q,
        'total': paginator.count,
    })


@admin_required
def galeri_photo_edit(request, photo_id):
    """Edit metadata foto galeri (event_name, bib_number)."""
    foto = koleksi_galeri.find_one({'id': int(photo_id)})
    if not foto:
        messages.error(request, 'Foto tidak ditemukan.')
        return redirect('admin_galeri_photo_list')

    if request.method == 'POST':
        update_fields = {
            'event_name': request.POST.get('event_name', '').strip(),
            'bib_number': request.POST.get('bib_number', '').strip(),
        }
        koleksi_galeri.update_one(
            {'id': int(photo_id)},
            {'$set': update_fields}
        )
        messages.success(request, '✅ Foto galeri berhasil diupdate!')
        return redirect(request.POST.get('next') or 'admin_galeri_photo_list')

    image_path = foto.get('image', '')
    return render(request, 'admin/galeri_photo_edit.html', {
        'foto': foto,
        'foto_id': photo_id,
        'image_url': f"/media/{image_path.replace(chr(92), '/')}",
        'folder': _folder_event(image_path),
    })


@admin_required
def galeri_photo_delete(request, photo_id):
    """Hapus foto dari collection galeri (metadata + file media bila ada)."""
    foto = koleksi_galeri.find_one({'id': int(photo_id)})
    if foto:
        import os
        from django.conf import settings
        image_path = foto.get('image', '')
        if image_path:
            file_path = os.path.join(settings.MEDIA_ROOT, image_path.replace('\\', '/'))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
        koleksi_galeri.delete_one({'id': int(photo_id)})
        messages.success(request, '✅ Foto galeri berhasil dihapus!')
    return redirect(request.POST.get('next') or 'admin_galeri_photo_list')


@admin_required
def galeri_photo_upload(request):
    """Upload foto galeri event + deteksi otomatis.

    Alur:
      1. Simpan file ke media/lomba_lari/<event>/ (nama di-rename bila bentrok).
      2. Deteksi nomor BIB via OCR (EasyOCR) -> kolom bib_number.
      3. Deteksi wajah + ekstraksi embedding:
         - BlazeFace (photos_faceembedding_blaze)
         - MTCNN/generic (photos_faceembedding)
      4. Insert metadata ke photos_photoevent & photos_photoevent_blaze.
    """
    import os
    import re
    from django.conf import settings
    from photos.face_views import _ocr_extract_bibs, _extract_blaze_embedding, l2_normalize

    # Event berasal dari collection 'events' (sinkron dengan photos_photoevent)
    events = list(events_collection.find().sort('timestamp', 1))
    for ev in events:
        ev['id'] = ev['_id']
    context = {'events': events}

    if request.method == 'POST':
        event_id = (request.POST.get('event_id') or '').strip()
        uploaded = request.FILES.get('gambar')

        event = None
        if event_id:
            try:
                event = events_collection.find_one({'_id': int(event_id)})
            except (ValueError, TypeError):
                event = None
        if not event:
            messages.error(request, 'Pilih event terlebih dahulu.')
            return render(request, 'admin/galeri_photo_upload.html', context)

        folder = (event.get('folder') or '').strip()
        event_name = (event.get('name') or '').strip()
        jenis_event = (event.get('event_type') or '').strip()
        event_timestamp = event.get('timestamp')

        if not uploaded:
            messages.error(request, 'Pilih file gambar terlebih dahulu.')
            return render(request, 'admin/galeri_photo_upload.html', context)

        ext = os.path.splitext(uploaded.name)[1].lower()
        allowed = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif'}
        if ext not in allowed:
            messages.error(request, 'Format file tidak didukung. Gunakan JPG, PNG, BMP, WebP, atau TIFF.')
            return render(request, 'admin/galeri_photo_upload.html', context)

        if not folder or not os.path.isdir(os.path.join(settings.MEDIA_ROOT, 'lomba_lari', folder)):
            messages.error(request, f'Folder event "{folder}" tidak ditemukan di media. Periksa folder event.')
            return render(request, 'admin/galeri_photo_upload.html', context)

        # ============ 1. SIMPAN FILE ============
        safe_name = re.sub(r'[^A-Za-z0-9_.-]+', '_', uploaded.name)
        target_dir = os.path.join(settings.MEDIA_ROOT, 'lomba_lari', folder)
        final_name = safe_name
        target_path = os.path.join(target_dir, final_name)
        base_name, dot_ext = os.path.splitext(final_name)
        counter = 1
        while os.path.exists(target_path):
            final_name = f'{base_name}_{counter}{dot_ext}'
            target_path = os.path.join(target_dir, final_name)
            counter += 1

        with open(target_path, 'wb+') as fh:
            for chunk in uploaded.chunks():
                fh.write(chunk)

        image_rel = f'lomba_lari/{folder}/{final_name}'

        # ============ 2. ID BARU (max id + 1) + SINKRON COUNTER ============
        ids = []
        for col in (koleksi_galeri, db['photos_photoevent_blaze']):
            ids.extend(d.get('id') for d in col.find({}, {'id': 1}) if d.get('id') is not None)
        next_id = (max(ids) + 1) if ids else 1
        db['counters'].update_one(
            {'_id': 'photos_photoevent'},
            {'$set': {'seq': next_id}},
            upsert=True,
        )

        result = {
            'photo_id': next_id,
            'image_url': f'/media/{image_rel}',
            'event_name': event_name,
            'jenis_event': jenis_event,
            'folder': folder,
        }

        # ============ 3. DETEKSI NOMOR BIB (OCR) ============
        try:
            ocr = _ocr_extract_bibs(target_path)
            bib_list = sorted(ocr.get('bib_numbers') or [])
            result['bib_numbers'] = bib_list
            result['ocr_text'] = (ocr.get('text') or '')
        except Exception as e:
            bib_list = []
            result['bib_numbers'] = []
            result['ocr_text'] = ''
            print(f"[ADMIN UPLOAD] OCR error: {e}")
        bib_str = ', '.join(bib_list)

        # ============ 4. EMBEDDING WAJAH (BlazeFace) ============
        blaze_count = 0
        try:
            vec, bbox, conf = _extract_blaze_embedding(target_path)
            if vec is not None and bbox:
                from PIL import Image, ImageOps
                crop_dir = os.path.join(settings.MEDIA_ROOT, 'blaze_face_crops')
                os.makedirs(crop_dir, exist_ok=True)
                crop_name = f'blaze_{next_id}_0.jpg'
                img = Image.open(target_path)
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
                img = img.convert('RGB')
                x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
                crop = img.crop((x, y, x + w, y + h))
                max_crop = 400
                if max(crop.size) > max_crop:
                    ratio = max_crop / max(crop.size)
                    crop = crop.resize((int(crop.width * ratio), int(crop.height * ratio)), Image.LANCZOS)
                crop.save(os.path.join(crop_dir, crop_name), 'JPEG', quality=90)
                db['photos_faceembedding_blaze'].insert_one({
                    'photo_id': next_id,
                    'image': image_rel,
                    'event_name': event_name,
                    'detector': 'blazeface',
                    'bbox_json': bbox,
                    'embedding_data': vec.tobytes(),
                    'face_image': f'blaze_face_crops/{crop_name}',
                    'confidence': conf or 0.0,
                })
                blaze_count = 1
        except Exception as e:
            print(f"[ADMIN UPLOAD] BlazeFace error: {e}")
        result['blaze_face'] = blaze_count

        # ============ 5. EMBEDDING WAJAH (MTCNN/generic) ============
        generic_count = 0
        try:
            import cv2
            from PIL import Image
            from photos.face_utils import FaceProcessor
            fp = FaceProcessor()
            faces = fp.detect_faces(target_path)
            crop_dir = os.path.join(settings.MEDIA_ROOT, 'face_crops')
            os.makedirs(crop_dir, exist_ok=True)
            for idx, face in enumerate(faces):
                emb = fp.extract_embedding(face['face'])
                if emb is None:
                    continue
                emb = l2_normalize(emb)
                crop_name = f'face_{next_id}_{idx}.jpg'
                pil_img = Image.fromarray(cv2.cvtColor(face['face'], cv2.COLOR_BGR2RGB))
                pil_img.save(os.path.join(crop_dir, crop_name), 'JPEG', quality=90)
                db['photos_faceembedding'].insert_one({
                    'photo_id': next_id,
                    'bbox_json': face['bbox'],
                    'embedding_data': emb.tobytes(),
                    'face_image': f'face_crops/{crop_name}',
                })
                generic_count += 1
        except Exception as e:
            print(f"[ADMIN UPLOAD] MTCNN error: {e}")
        result['mtcnn_face'] = generic_count

        # ============ 6. INSERT METADATA FOTO ============
        from datetime import datetime
        now = datetime.utcnow()
        koleksi_galeri.insert_one({
            'id': next_id,
            'event_name': event_name,
            'jenis_event': jenis_event,
            'timestamp': event_timestamp,
            'image': image_rel,
            'bib_number': bib_str,
            'ocr_raw_text': result['ocr_text'],
            'ocr_updated_at': now,
            'uploaded_at': now,
        })
        db['photos_photoevent_blaze'].insert_one({
            'id': next_id,
            'event_name': event_name,
            'jenis_event': jenis_event,
            'timestamp': event_timestamp,
            'image': image_rel,
            'bib_number': bib_str,
            'uploaded_at': now,
        })

        messages.success(
            request,
            f'✅ Foto berhasil diupload ke event "{event_name}" (ID {next_id}). '
            f'Jenis: {jenis_event} | BIB terdeteksi: {len(bib_list)} | '
            f'Wajah: BlazeFace {blaze_count}, MTCNN {generic_count}.'
        )
        context['result'] = result
        return render(request, 'admin/galeri_photo_upload.html', context)

    return render(request, 'admin/galeri_photo_upload.html', context)


# ============================================================
# URL PATTERNS
# ============================================================
urlpatterns = [
    path('login/', login, name='admin_login'),
    path('logout/', logout_view, name='admin_logout'),
    path('', dashboard, name='admin_dashboard'),
    path('change-password/', change_password, name='admin_change_password'),
    path('events/', event_list, name='admin_event_list'),
    path('events/add/', event_add, name='admin_event_add'),
    path('events/edit/<int:event_id>/', event_edit, name='admin_event_edit'),
    path('events/delete/<int:event_id>/', event_delete, name='admin_event_delete'),
    path('events/detail/', event_detail, name='admin_event_detail'),
    path('event-types/', event_type_list, name='admin_event_type_list'),
    path('event-types/add/', event_type_add, name='admin_event_type_add'),
    path('event-types/edit/<int:type_id>/', event_type_edit, name='admin_event_type_edit'),
    path('event-types/delete/<int:type_id>/', event_type_delete, name='admin_event_type_delete'),
    path('photos/', photo_list, name='admin_photo_list'),
    path('photos/upload/', photo_upload, name='admin_photo_upload'),
    path('photos/edit/<int:photo_id>/', photo_edit, name='admin_photo_edit'),
    path('photos/delete/<int:photo_id>/', photo_delete, name='admin_photo_delete'),
    path('foto/', foto_list, name='admin_foto_list'),
    path('foto/delete/<int:foto_id>/', photo_delete, name='admin_foto_delete'),
    # Galeri Foto Event (photos_photoevent)
    path('galeri-foto/', galeri_photo_list, name='admin_galeri_photo_list'),
    path('galeri-foto/upload/', galeri_photo_upload, name='admin_galeri_photo_upload'),
    path('galeri-foto/edit/<int:photo_id>/', galeri_photo_edit, name='admin_galeri_photo_edit'),
    path('galeri-foto/delete/<int:photo_id>/', galeri_photo_delete, name='admin_galeri_photo_delete'),
]
