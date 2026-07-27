from django.shortcuts import render, redirect
from django.contrib import messages
from config.db import photos_collection, events_collection, get_next_id
from datetime import datetime


def photo_list(request):
    photos = list(photos_collection.find().sort('_id', -1))
    # Attach event data
    for photo in photos:
        event = events_collection.find_one({'_id': photo.get('event_id')})
        photo['event_name'] = event['event_type'] if event else 'Unknown'
    return render(request, 'photos/photo_list.html', {'photos': photos})


def photo_upload(request):
    events = list(events_collection.find().sort('_id', -1))

    if request.method == 'POST':
        event_id = int(request.POST.get('event_id'))
        image = request.FILES.get('image')

        if not image:
            messages.error(request, 'Pilih gambar terlebih dahulu.')
            return render(request, 'photos/photo_upload.html', {'events': events})

        # Save image file
        from django.core.files.storage import default_storage
        import os
        filepath = default_storage.save(f'photos/{image.name}', image)

        photo_data = {
            '_id': get_next_id('photos'),
            'event_id': event_id,
            'image': filepath,
            'uploaded_at': datetime.utcnow(),
        }
        photos_collection.insert_one(photo_data)
        messages.success(request, '✅ Foto berhasil diupload!')
        return redirect('photo_list')

    return render(request, 'photos/photo_upload.html', {'events': events})


def photo_delete(request, photo_id):
    photo = photos_collection.find_one({'_id': int(photo_id)})
    if photo:
        # Delete file
        import os
        from django.conf import settings
        file_path = os.path.join(settings.MEDIA_ROOT, photo.get('image', ''))
        if os.path.exists(file_path):
            os.remove(file_path)
        photos_collection.delete_one({'_id': int(photo_id)})
    return redirect('photo_list')
