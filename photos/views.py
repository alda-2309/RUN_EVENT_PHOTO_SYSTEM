from django.shortcuts import render, redirect

from .models import Photo
from events.models import Event


def photo_list(request):

    photos = Photo.objects.all().order_by('-id')

    return render(
        request,
        'photos/photo_list.html',
        {
            'photos': photos
        }
    )


def photo_upload(request):

    events = Event.objects.all()

    if request.method == 'POST':

        event_id = request.POST.get('event')

        image = request.FILES.get('image')

        event = Event.objects.get(id=event_id)

        Photo.objects.create(
            event=event,
            image=image
        )

        return redirect('photo_list')

    return render(
        request,
        'photos/photo_upload.html',
        {
            'events': events
        }
    )

def photo_delete(request, photo_id):

    photo = Photo.objects.get(id=photo_id)

    photo.delete()

    return redirect('photo_list')