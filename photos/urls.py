from django.urls import path
from django.views.generic import TemplateView
from . import views


def lazy_face_search(request):
    from .face_views import face_search
    return face_search(request)


def lazy_bib_search(request):
    from .face_views import bib_search
    return bib_search(request)


def lazy_bib_search_api(request):
    from .face_views import bib_search_api
    return bib_search_api(request)


urlpatterns = [
    path('', views.photo_list, name='photo_list'),
    path('face-search/', lazy_face_search, name='face_search'),
    path('bib-search/', lazy_bib_search, name='bib_search'),
    path('bib-search-api/', lazy_bib_search_api, name='bib_search_api'),
]