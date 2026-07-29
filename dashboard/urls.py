from django.urls import path
from . import views

urlpatterns = [

    path(
        '',
        views.home_view,
        name='dashboard'
    ),

    path(
        'dasboart/',
        views.dasboart_view,
        name='dasboart'
    ),

    path(
        'search/',
        views.search_view,
        name='search'
    ),

    path(
        "tentang-kami/",
        views.tentang_kami_view,
        name="tentang_kami"
    ),

    path(
        "events/",
        views.events_view,
        name="events"
    ),

    # path(
    #     "kategori/",
    #     views.kategori_view,
    #     name="kategori"
    # ),

]
