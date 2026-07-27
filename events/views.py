from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Event


# LIST EVENT
def event_list(request):

    events = Event.objects.all()

    q = request.GET.get('q')
    date = request.GET.get('date')

    if q:
        events = events.filter(event_type__icontains=q)

    if date:
        events = events.filter(timestamp__date=date)

    context = {
        'events': events
    }

    return render(
        request,
        'events/event_list.html',
        context
    )


# TAMBAH EVENT
def event_add(request):

    if request.method == 'POST':

        Event.objects.create(

            event_type=request.POST.get('event_type'),

            timestamp=request.POST.get('timestamp'),

            location=request.POST.get('location')

        )

        messages.success(
            request,
            '✅ Event berhasil ditambahkan!'
        )

        return redirect('dasboart')

    return render(
        request,
        'events/event_add.html'
    )

def event_detail(request):
    return render(
        request,
        'events/event_detail.html'
    )

