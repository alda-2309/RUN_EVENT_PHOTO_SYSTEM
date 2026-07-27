from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

from events.models import Event
from photos.models import Photo


def home_view(request):
    return render(request, 'dashboard/index.html')


def dasboart_view(request):

    total_photos = Photo.objects.count()

    total_events = Event.objects.count()

    marathon_count = Event.objects.filter(
        event_type='Marathon'
    ).count()

    trail_count = Event.objects.filter(
        event_type='Trail Run'
    ).count()

    funrun_count = Event.objects.filter(
        event_type='Fun Run'
    ).count()

    night_run_count = Event.objects.filter(
        event_type='Night Run'
    ).count()

    latest_uploads = Photo.objects.order_by(
        '-id'
    )[:5]

    context = {

        'total_photos': total_photos,

        'total_events': total_events,

        'marathon_count': marathon_count,

        'trail_count': trail_count,

        'funrun_count': funrun_count,

        'night_run_count': night_run_count,

        'latest_uploads': latest_uploads,
    }

    return render(
        request,
        'dashboard/dashboard.html',
        context
    )

def login_view(request):

    if request.method == 'POST':

        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            return redirect('dasboart')

        else:
            messages.error(
                request,
                'Username atau password salah'
            )

    return render(
        request,
        'users/login.html'
    )

def register_view(request):

    if request.method == "POST":

        full_name = request.POST.get("full_name")

        username = request.POST.get("username")

        email = request.POST.get("email")

        password1 = request.POST.get("password1")

        password2 = request.POST.get("password2")


        if password1 != password2:

            messages.error(
                request,
                "Password tidak sama"
            )

            return redirect("register")


        if User.objects.filter(
            username=username
        ).exists():

            messages.error(
                request,
                "Username sudah digunakan"
            )

            return redirect("register")


        User.objects.create_user(

            username=username,

            email=email,

            password=password1,

            first_name=full_name

        )


        messages.success(
            request,
            "Registrasi berhasil"
        )

        return redirect("login")


    return render(
        request,
        "users/register.html"
    )


def logout_view(request):

    logout(request)

    return redirect('login')

def search_view(request):
    return render(request, 'dashboard/search.html')

def tentang_kami_view(request):
    return render(request, "dashboard/tentang_kami.html")

def events_view(request):
    return render(request, "dashboard/events.html")

def kategori_view(request):
    return render(request, "dashboard/kategori.html")

