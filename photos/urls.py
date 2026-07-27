from django.urls import path
from django.views.generic import TemplateView
from . import views


def lazy_face_search(request):
    from .face_views import face_search
    return face_search(request)


def lazy_bib_search(request):
    from .face_views import bib_search
    return bib_search(request)


urlpatterns = [
    path('', views.photo_list, name='photo_list'),
    path('upload/', views.photo_upload, name='photo_upload'),
    path('delete/<int:photo_id>/', views.photo_delete, name='photo_delete'),
    path('face-search/', lazy_face_search, name='face_search'),
    path('bib-search/', lazy_bib_search, name='bib_search'),
]