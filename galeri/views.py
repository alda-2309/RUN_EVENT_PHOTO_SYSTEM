from django.shortcuts import render
from config.db import photos_collection
from datetime import datetime

def foto_user(request):
    return render(request, 'galeri/foto/foto.html', {'active_page': 'search'})

def hasil(request):
    fotos = photos_collection.find().sort('_id', -1)
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

    return render(request, 'galeri/foto/hasil.html', {'fotos': fotos, 'active_page': 'search'})
