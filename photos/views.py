from django.shortcuts import render
from config.db import photos_collection, events_collection

def photo_list(request):
    photos = list(photos_collection.find().sort('_id', -1))
    # Attach event data
    for photo in photos:
        event = events_collection.find_one({'_id': photo.get('event_id')})
        photo['event_name'] = event['event_type'] if event else 'Unknown'
    return render(request, 'photos/photo_list.html', {'photos': photos})
