import json
from datetime import datetime
from functools import wraps
from bson import ObjectId
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import os
from django.core.files.storage import default_storage
from django.conf import settings
from config.db import (
    events_collection, map_points_collection, map_routes_collection,
    map_point_photos_collection, get_next_id, users_collection, get_event_types,
)

# ============================================================
# HELPER — cek admin dari session
# ============================================================
def _is_admin(request):
    user_id = request.session.get('user_id')
    is_logged_in = request.session.get('is_logged_in', False)
    if not (user_id and is_logged_in):
        return False
    user_data = users_collection.find_one({'_id': int(user_id)})
    return bool(user_data and (user_data.get('is_staff') or user_data.get('is_superuser')))

def admin_required_api(view_func):
    """Decorator untuk proteksi API endpoint — hanya admin bisa akses"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not _is_admin(request):
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper

# ============================================================
# ADMIN EVENT MANAGEMENT
# ============================================================

def event_list(request):
    events = list(events_collection.find().sort('_id', -1))
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

    return render(request, 'events/event_list.html', {'events': events})

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
    return render(request, 'events/event_add.html', {'event_types': get_event_types()})

def event_detail(request):
    return render(request, 'events/event_detail.html')

def event_map_view(request):
    """Public map view — admin bisa edit, user cuma lihat"""
    is_admin = _is_admin(request)
    return render(request, 'events/event_detail.html', {'is_admin': is_admin})


# ============================================================
# MAP API – CRUD TITIK + ROUTE
# ============================================================
# Semua titik disimpan di collection 'map_points'
# Struktur dokumen:
# {
#   _id: ObjectId / int,
#   event_id: int (default 1),
#   name: str,         # nama titik (START, KM 1, FINISH, dll)
#   lat: float,
#   lng: float,
#   order: int,        # urutan route (0 = start, 1, 2, ...)
#   icon: str,         # icon yg dipilih user
#   created_at: datetime,
#   updated_at: datetime
# }

def _serialize_point(p):
    """Convert MongoDB doc to JSON-serializable dict"""
    return {
        'id': str(p['_id']),
        'event_id': p.get('event_id', 1),
        'name': p.get('name', ''),
        'lat': p.get('lat', 0),
        'lng': p.get('lng', 0),
        'order': p.get('order', 0),
        'icon': p.get('icon', '📍'),
    }


def _serialize_route(route_doc):
    return {
        'event_id': route_doc.get('event_id', 1),
        'points': route_doc.get('points', []),
    }


def api_get_points(request):
    """GET /events/api/points/?event_id=1 — ambil semua titik"""
    event_id = int(request.GET.get('event_id', 1))
    points = list(map_points_collection.find({'event_id': event_id}).sort('order', 1))
    return JsonResponse({'points': [_serialize_point(p) for p in points]})

@csrf_exempt
@require_http_methods(['GET'])
def api_get_route(request):
    """GET /events/api/route/?event_id=1 — ambil route geometry tersimpan"""
    event_id = int(request.GET.get('event_id', 1))
    route = map_routes_collection.find_one({'event_id': event_id})
    return JsonResponse({'route': _serialize_route(route) if route else None})


@csrf_exempt
@admin_required_api
@require_http_methods(['POST'])
def api_add_point(request):
    """POST /events/api/points/add/ — tambah titik baru"""
    try:
        data = json.loads(request.body)
        event_id = int(data.get('event_id', 1))

        # hitung order terakhir + 1
        last_point = map_points_collection.find_one(
            {'event_id': event_id},
            sort=[('order', -1)]
        )
        next_order = (last_point['order'] + 1) if last_point else 0

        point = {
            '_id': get_next_id('map_points'),
            'event_id': event_id,
            'name': data.get('name', 'Titik ' + str(next_order)),
            'lat': float(data['lat']),
            'lng': float(data['lng']),
            'order': next_order,
            'icon': data.get('icon', '📍'),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }
        map_points_collection.insert_one(point)
        return JsonResponse({'success': True, 'point': _serialize_point(point)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@admin_required_api
@require_http_methods(['PUT'])
def api_update_point(request, point_id):
    """PUT /events/api/points/<point_id>/ — update nama, icon, posisi"""
    try:
        data = json.loads(request.body)
        update_fields = {}
        if 'name' in data:
            update_fields['name'] = data['name']
        if 'lat' in data and 'lng' in data:
            update_fields['lat'] = float(data['lat'])
            update_fields['lng'] = float(data['lng'])
        if 'icon' in data:
            update_fields['icon'] = data['icon']
        if 'order' in data:
            update_fields['order'] = int(data['order'])
        update_fields['updated_at'] = datetime.utcnow()

        map_points_collection.update_one(
            {'_id': int(point_id)},
            {'$set': update_fields}
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@admin_required_api
@require_http_methods(['DELETE'])
def api_delete_point(request, point_id):
    """DELETE /events/api/points/<point_id>/ — hapus titik"""
    try:
        map_points_collection.delete_one({'_id': int(point_id)})
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@admin_required_api
@require_http_methods(['POST'])
def api_save_route(request):
    """POST /events/api/route/save/ — simpan route geometry asli"""
    try:
        data = json.loads(request.body)
        event_id = int(data.get('event_id', 1))
        points = data.get('points', [])  # list of {lat, lng}
        map_routes_collection.update_one(
            {'event_id': event_id},
            {'$set': {
                'event_id': event_id,
                'points': points,
                'updated_at': datetime.utcnow(),
            }},
            upsert=True,
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@admin_required_api
@require_http_methods(['POST'])
def api_reset_points(request):
    """POST /events/api/points/reset/ — hapus semua titik & route untuk event_id"""
    try:
        data = json.loads(request.body)
        event_id = int(data.get('event_id', 1))
        map_points_collection.delete_many({'event_id': event_id})
        map_routes_collection.delete_many({'event_id': event_id})
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ============================================================
# MAP POINT PHOTOS – FOTO PER CHECKPOINT
# ============================================================
# Semua foto tersimpan di collection 'map_point_photos'.
# Struktur dokumen:
# {
#   _id: int (auto increment),
#   point_id: int,        # _id dari map_points
#   event_id: int,
#   caption: str,
#   image: str,           # path file di MEDIA_ROOT (contoh: 'map_photos/xxx.jpg')
#   created_at: datetime
# }

def _serialize_point_photo(p):
    """Convert MongoDB doc ke JSON-serializable dict"""
    return {
        'id': str(p['_id']),
        'point_id': str(p.get('point_id', '')),
        'event_id': p.get('event_id', 1),
        'caption': p.get('caption', ''),
        'image': p.get('image', ''),
        'url': settings.MEDIA_URL + p.get('image', '') if p.get('image') else '',
        'created_at': p.get('created_at').isoformat() if p.get('created_at') else '',
    }

def api_get_point_photos(request, point_id):
    """GET /events/api/points/<point_id>/photos/ — list semua foto sebuah checkpoint (public)"""
    try:
        photos = list(map_point_photos_collection.find({'point_id': int(point_id)}).sort('_id', -1))
        return JsonResponse({'photos': [_serialize_point_photo(p) for p in photos]})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@admin_required_api
@require_http_methods(['POST'])
def api_upload_point_photo(request, point_id):
    """POST /events/api/points/<point_id>/photos/upload/ (multipart)
    field: caption (optional), images (multiple files)
    """
    try:
        # pastikan pointnya ada
        point = map_points_collection.find_one({'_id': int(point_id)})
        if not point:
            return JsonResponse({'success': False, 'error': 'Checkpoint tidak ditemukan'}, status=404)

        event_id = point.get('event_id', 1)
        files = request.FILES.getlist('images')
        if not files:
            return JsonResponse({'success': False, 'error': 'Tidak ada file gambar dikirim'}, status=400)

        caption = request.POST.get('caption', '')
        saved = []
        for f in files:
            filepath = default_storage.save(f'map_photos/{f.name}', f)
            doc = {
                '_id': get_next_id('map_point_photos'),
                'point_id': int(point_id),
                'event_id': event_id,
                'caption': caption,
                'image': filepath,
                'created_at': datetime.utcnow(),
            }
            map_point_photos_collection.insert_one(doc)
            saved.append(_serialize_point_photo(doc))
        return JsonResponse({'success': True, 'photos': saved})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@admin_required_api
@require_http_methods(['DELETE'])
def api_delete_point_photo(request, point_id, photo_id):
    """DELETE /events/api/points/<point_id>/photos/<photo_id>/ — hapus foto checkpoint"""
    try:
        doc = map_point_photos_collection.find_one({
            '_id': int(photo_id),
            'point_id': int(point_id),
        })
        if not doc:
            return JsonResponse({'success': False, 'error': 'Foto tidak ditemukan'}, status=404)

        # hapus file di media
        file_path = os.path.join(settings.MEDIA_ROOT, doc.get('image', ''))
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        map_point_photos_collection.delete_one({'_id': int(photo_id)})
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@admin_required_api
@require_http_methods(['DELETE'])
def api_delete_point_all_photos(request, point_id):
    """DELETE /events/api/points/<point_id>/photos/ — hapus SEMUA foto sebuah checkpoint"""
    try:
        docs = list(map_point_photos_collection.find({'point_id': int(point_id)}))
        for doc in docs:
            file_path = os.path.join(settings.MEDIA_ROOT, doc.get('image', ''))
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        map_point_photos_collection.delete_many({'point_id': int(point_id)})
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
