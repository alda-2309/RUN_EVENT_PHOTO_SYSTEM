from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from config.db import (
    photos_collection, events_collection, users_collection,
    get_next_id, create_user, authenticate_user, update_last_login,
    hash_password, verify_password
)
from datetime import datetime

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
    total_photos = photos_collection.count_documents({})
    total_events = events_collection.count_documents({})

    events = list(events_collection.find())
    marathon_count = sum(1 for e in events if e.get('event_type') == 'Marathon')
    trail_count = sum(1 for e in events if e.get('event_type') == 'Trail Run')
    funrun_count = sum(1 for e in events if 'Fun Run' in e.get('event_type', ''))
    night_run_count = sum(1 for e in events if e.get('event_type') == 'Night Run')

    latest_uploads = list(photos_collection.find().sort('_id', -1).limit(5))
    for photo in latest_uploads:
        event = events_collection.find_one({'_id': photo.get('event_id')})
        photo['event_name'] = event['event_type'] if event else 'Unknown'

    context = {
        'total_photos': total_photos,
        'total_events': total_events,
        'marathon_count': marathon_count,
        'trail_count': trail_count,
        'funrun_count': funrun_count,
        'night_run_count': night_run_count,
        'latest_uploads': latest_uploads,
    }
    return render(request, 'dashboard/dashboard.html', context)

@admin_required
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

    return render(request, 'admin/event_list.html', {'events': events})

@admin_required
def event_add(request):
    if request.method == 'POST':
        event_data = {
            '_id': get_next_id('events'),
            'event_type': request.POST.get('event_type'),
            'timestamp': datetime.strptime(request.POST.get('timestamp'), '%Y-%m-%dT%H:%M'),
            'location': request.POST.get('location'),
        }
        events_collection.insert_one(event_data)
        messages.success(request, '✅ Event berhasil ditambahkan!')
        return redirect('admin_event_list')
    return render(request, 'admin/event_add.html')

@admin_required
def event_detail(request):
    return render(request, 'admin/event_detail.html')

@admin_required
def photo_list(request):
    fotos = list(photos_collection.find().sort('_id', -1))
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

    return render(request, 'admin/photo_upload.html', {'form': form})

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
# URL PATTERNS
# ============================================================
urlpatterns = [
    path('login/', login, name='admin_login'),
    path('logout/', logout_view, name='admin_logout'),
    path('', dashboard, name='admin_dashboard'),
    path('change-password/', change_password, name='admin_change_password'),
    path('events/', event_list, name='admin_event_list'),
    path('events/add/', event_add, name='admin_event_add'),
    path('events/detail/', event_detail, name='admin_event_detail'),
    path('photos/', photo_list, name='admin_photo_list'),
    path('photos/upload/', photo_upload, name='admin_photo_upload'),
    path('photos/delete/<int:photo_id>/', photo_delete, name='admin_photo_delete'),
    path('foto/', foto_list, name='admin_foto_list'),
    path('foto/delete/<int:foto_id>/', photo_delete, name='admin_foto_delete'),
]
