from django.urls import path
from . import views

from .views import (
    home_view,
    dasboart_view,
    login_view,
    register_view,
    logout_view,
    search_view,
    tentang_kami_view,
    events_view,
)

urlpatterns = [

    path(
        '',
        home_view,
        name='dashboard'
    ),

    path(
        'dasboart/',
        dasboart_view,
        name='dasboart'
    ),

    path(
        'login/',
        login_view,
        name='login'
    ),

    path(
        'register/',
        register_view,
        name='register'
    ),

    path(
        'logout/',
        logout_view,
        name='logout'
    ),

    path(
        'search/',
        search_view,
        name='search'
    ),

    path(
        "tentang-kami/",
        views.tentang_kami_view,
        name="tentang_kami"
    ),

    path(
    "events/",
    events_view,
    name="events"
),

    path(
    "kategori/",
    views.kategori_view,
    name="kategori"
),

]