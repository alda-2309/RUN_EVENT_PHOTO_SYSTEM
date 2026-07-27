from django.urls import path
from . import views

urlpatterns = [

    path('', views.photo_list, name='photo_list'),

    path('upload/', views.photo_upload, name='photo_upload'),

     path(
        'delete/<int:photo_id>/',
        views.photo_delete,
        name='photo_delete'
    ),
]