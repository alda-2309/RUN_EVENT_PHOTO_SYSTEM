from django.shortcuts import render, redirect
from config.db import galeri_collection, get_next_id
from .forms import FotoForm
from datetime import datetime


def add_foto(request):
    if request.method == 'POST':
        form = FotoForm(request.POST, request.FILES)
        if form.is_valid():
            # Save image
            gambar = request.FILES['gambar']
            from django.core.files.storage import default_storage
            filepath = default_storage.save(f'foto/{gambar.name}', gambar)

            foto_data = {
                '_id': get_next_id('galeri'),
                'nama_event': form.cleaned_data['nama_event'],
                'gambar': filepath,
                'timestamp': form.cleaned_data['timestamp'],
                'jenis_event': form.cleaned_data['jenis_event'],
            }
            galeri_collection.insert_one(foto_data)
            return redirect('foto_list')
        else:
            print(form.errors)
    else:
        form = FotoForm()

    return render(request, 'galeri/foto/add.html', {'form': form})


def foto_list(request):
    fotos = list(galeri_collection.find().sort('_id', -1))
    return render(request, 'galeri/foto/list.html', {'fotos': fotos})


def delete_foto(request, foto_id):
    foto = galeri_collection.find_one({'_id': int(foto_id)})
    if foto:
        # Delete image file
        import os
        from django.conf import settings
        file_path = os.path.join(settings.MEDIA_ROOT, foto.get('gambar', ''))
        if os.path.exists(file_path):
            os.remove(file_path)
        galeri_collection.delete_one({'_id': int(foto_id)})
    return redirect('foto_list')


def foto_user(request):
    return render(request, 'galeri/foto/foto.html')


def hasil(request):
    fotos = galeri_collection.find().sort('_id', -1)
    event = request.GET.get('event')
    timestamp = request.GET.get('timestamp')

    if event:
        fotos = [f for f in fotos if f.get('jenis_event') == event]
    if timestamp:
        try:
            jam = datetime.strptime(timestamp, '%H:%M').time()
            fotos = [f for f in fotos if f.get('timestamp') and f['timestamp'].hour == jam.hour and f['timestamp'].minute == jam.minute]
        except ValueError:
            pass

    return render(request, 'galeri/foto/hasil.html', {'fotos': fotos})
