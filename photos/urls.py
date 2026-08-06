from django.urls import path
from django.views.generic import TemplateView
from . import views


def lazy_face_search(request):
    # URL ini kini memakai pipeline BlazeFace (collection *_blaze),
    # sesuai keinginan user: /photos/face-search/ berfungsi seperti /test-ai-blaze/.
    from .face_views import face_search, test_ai_blaze
    return test_ai_blaze(request)


def lazy_bib_search(request):
    from .face_views import bib_search
    return bib_search(request)


def lazy_bib_search_api(request):
    from .face_views import bib_search_api
    return bib_search_api(request)


def lazy_bib_scan(request):
    from .face_views import bib_scan
    return bib_scan(request)


urlpatterns = [
    path('', views.photo_list, name='photo_list'),
    path('face-search/', lazy_face_search, name='face_search'),
    path('bib-search/', lazy_bib_search, name='bib_search'),
    path('bib-search-api/', lazy_bib_search_api, name='bib_search_api'),
    path('bib-scan/', lazy_bib_scan, name='bib_scan'),
]