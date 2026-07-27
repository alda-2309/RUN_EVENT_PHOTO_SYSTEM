from django.shortcuts import render, redirect
from .forms import FotoForm
from .models import Foto
from datetime import datetime




def add_foto(request):

    if request.method == "POST":

        form = FotoForm(request.POST, request.FILES)

        if form.is_valid():

            foto = form.save(commit=False)

            foto.user = request.user

            foto.save()

            return redirect("foto_list")

        else:
            print(form.errors)

    else:

        form = FotoForm()

    return render(
        request,
        "galeri/foto/add.html",
        {
            "form": form
        }
    )


def foto_list(request):

    fotos = Foto.objects.all().order_by("-id")

    return render(
        request,
        "galeri/foto/list.html",
        {
            "fotos": fotos
        }
    )


def delete_foto(request, foto_id):

    foto = Foto.objects.get(id=foto_id)

    foto.delete()

    return redirect("foto_list")

def foto_user(request):
    return render(request, "galeri/foto/foto.html")

def hasil(request):

    fotos = Foto.objects.all()

    event = request.GET.get("event")
    timestamp = request.GET.get("timestamp")

    if event:
        fotos = fotos.filter(jenis_event=event)

    if timestamp:
        jam = datetime.strptime(timestamp, "%H:%M").time()
        fotos = fotos.filter(
            timestamp__hour=jam.hour,
            timestamp__minute=jam.minute
        )

    return render(
        request,
        "galeri/foto/hasil.html",
        {
            "fotos": fotos
        }
    )