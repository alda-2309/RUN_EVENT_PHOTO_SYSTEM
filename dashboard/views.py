from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

from config.db import (
    photos_collection, events_collection, users_collection,
    get_next_id, create_user, authenticate_user, update_last_login
)


def home_view(request):
    return render(request, 'dashboard/index.html')


def dasboart_view(request):
    total_photos = photos_collection.count_documents({})
    total_events = events_collection.count_documents({})

    events = list(events_collection.find())
    marathon_count = sum(1 for e in events if e.get('event_type') == 'Marathon')
    trail_count = sum(1 for e in events if e.get('event_type') == 'Trail Run')
    funrun_count = sum(1 for e in events if 'Fun Run' in e.get('event_type', ''))
    night_run_count = sum(1 for e in events if e.get('event_type') == 'Night Run')

    latest_uploads = list(photos_collection.find().sort('_id', -1).limit(5))

    # Attach event info to photos
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


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate_user(username, password)
        if user:
            update_last_login(user['_id'])
            # Create Django user in-memory for session
            django_user = User(
                id=user['_id'],
                username=user['username'],
                email=user.get('email', ''),
            )
            django_user.backend = 'config.auth_backend.MongoAuthBackend'
            login(request, django_user)
            return redirect('dasboart')
        else:
            messages.error(request, 'Username atau password salah')

    return render(request, 'users/login.html')


def register_view(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, 'Password tidak sama')
            return redirect('register')

        if users_collection.find_one({'username': username}):
            messages.error(request, 'Username sudah digunakan')
            return redirect('register')

        try:
            create_user(
                username=username,
                email=email,
                password=password1,
                first_name=full_name,
            )
            messages.success(request, 'Registrasi berhasil')
            return redirect('login')
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('register')

    return render(request, 'users/register.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def search_view(request):
    return render(request, 'dashboard/search.html')


def tentang_kami_view(request):
    return render(request, 'dashboard/tentang_kami.html')


def events_view(request):
    return render(request, 'dashboard/events.html')


def kategori_view(request):
    return render(request, 'dashboard/kategori.html')
