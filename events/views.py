from django.shortcuts import render, redirect
from django.contrib import messages
from config.db import events_collection, get_next_id
from datetime import datetime

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
            'event_type': request.POST.get('event_type'),
            'timestamp': datetime.strptime(request.POST.get('timestamp'), '%Y-%m-%dT%H:%M'),
            'location': request.POST.get('location'),
        }
        events_collection.insert_one(event_data)
        messages.success(request, '✅ Event berhasil ditambahkan!')
        return redirect('dasboart')
    return render(request, 'events/event_add.html')


def event_detail(request):
    return render(request, 'events/event_detail.html')
